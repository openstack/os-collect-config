#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from keystoneclient.v3 import client as keystoneclient
from oslo_config import cfg
from oslo_log import log
import six
from zaqarclient.queues.v1 import client as zaqarclient
from zaqarclient import transport
from zaqarclient.transport import request

from os_collect_config import exc
from os_collect_config import keystone
from os_collect_config import merger

CONF = cfg.CONF
logger = log.getLogger(__name__)

opts = [
    cfg.StrOpt('user-id',
               help='User ID for API authentication'),
    cfg.StrOpt('password',
               help='Password for API authentication'),
    cfg.StrOpt('project-id',
               help='ID of project for API authentication'),
    cfg.StrOpt('auth-url',
               help='URL for API authentication'),
    cfg.StrOpt('queue-id',
               help='ID of the queue to be checked'),
    cfg.BoolOpt('use-websockets',
                default=False,
                help='Use the websocket transport to connect to Zaqar.'),
    cfg.StrOpt('region-name',
               help='Region Name for extracting Zaqar endpoint'),
    cfg.BoolOpt('ssl-certificate-validation',
                help='ssl certificat validation flag for connect to Zaqar',
                default=False),
    cfg.StrOpt('ca-file',
               help='CA Cert file for connect to Zaqar'),
]
name = 'zaqar'


class Collector(object):
    def __init__(self,
                 keystoneclient=keystoneclient,
                 zaqarclient=zaqarclient,
                 discover_class=None,
                 transport=transport):
        self.keystoneclient = keystoneclient
        self.zaqarclient = zaqarclient
        self.discover_class = discover_class
        self.transport = transport

    def get_data_wsgi(self, ks, conf):
        kwargs = {'service_type': 'messaging', 'endpoint_type': 'publicURL'}
        if CONF.zaqar.region_name:
            kwargs['region_name'] = CONF.zaqar.region_name
        endpoint = ks.service_catalog.url_for(**kwargs)
        logger.debug('Fetching metadata from %s' % endpoint)
        zaqar = self.zaqarclient.Client(endpoint, conf=conf, version=1.1)

        queue = zaqar.queue(CONF.zaqar.queue_id)
        r = six.next(queue.pop())
        return r.body

    def _create_req(self, endpoint, action, body):
        return request.Request(endpoint, action, content=json.dumps(body))

    def get_data_websocket(self, ks, conf):
        kwargs = {'service_type': 'messaging-websocket',
                  'endpoint_type': 'publicURL'}
        if CONF.zaqar.region_name:
            kwargs['region_name'] = CONF.zaqar.region_name
        endpoint = ks.service_catalog.url_for(**kwargs)

        logger.debug('Fetching metadata from %s' % endpoint)

        with self.transport.get_transport_for(endpoint, options=conf) as ws:
            # create queue
            req = self._create_req(endpoint, 'queue_create',
                                   {'queue_name': CONF.zaqar.queue_id})
            ws.send(req)
            # subscribe to queue messages
            req = self._create_req(endpoint, 'subscription_create',
                                   {'queue_name': CONF.zaqar.queue_id,
                                    'ttl': 10000})
            ws.send(req)

            # check for pre-existing messages
            req = self._create_req(endpoint, 'message_delete_many',
                                   {'queue_name': CONF.zaqar.queue_id,
                                    'pop': 1})
            resp = ws.send(req)
            messages = json.loads(resp.content).get('messages', [])

            if len(messages) > 0:
                # NOTE(dprince) In this case we are checking for queue
                # messages that arrived before we subscribed.
                logger.debug('Websocket message found...')
                msg_0 = messages[0]
                data = msg_0['body']

            else:
                # NOTE(dprince) This will block until there is data available
                # or the socket times out. Because we subscribe to the queue
                # it will allow us to process data immediately.
                logger.debug('websocket recv()')
                data = ws.recv()['body']

        return data

    def collect(self):
        if CONF.zaqar.auth_url is None:
            logger.warn('No auth_url configured.')
            raise exc.ZaqarMetadataNotConfigured()
        if CONF.zaqar.password is None:
            logger.warn('No password configured.')
            raise exc.ZaqarMetadataNotConfigured()
        if CONF.zaqar.project_id is None:
            logger.warn('No project_id configured.')
            raise exc.ZaqarMetadataNotConfigured()
        if CONF.zaqar.user_id is None:
            logger.warn('No user_id configured.')
            raise exc.ZaqarMetadataNotConfigured()
        if CONF.zaqar.queue_id is None:
            logger.warn('No queue_id configured.')
            raise exc.ZaqarMetadataNotConfigured()
        if CONF.zaqar.ssl_certificate_validation is True and (
                CONF.zaqar.ca_file is None):
            logger.warn('No CA file configured when flag ssl certificate '
                        'validation is on.')
            raise exc.ZaqarMetadataNotConfigured()
        # NOTE(flwang): To be compatible with old versions, we won't throw
        # error here if there is no region name.

        try:
            ks = keystone.Keystone(
                auth_url=CONF.zaqar.auth_url,
                user_id=CONF.zaqar.user_id,
                password=CONF.zaqar.password,
                project_id=CONF.zaqar.project_id,
                keystoneclient=self.keystoneclient,
                discover_class=self.discover_class).client

            conf = {
                'auth_opts': {
                    'backend': 'keystone',
                    'options': {
                        'os_auth_token': ks.auth_token,
                        'os_project_id': CONF.zaqar.project_id,
                        'insecure': not CONF.zaqar.ssl_certificate_validation,
                        'cacert': CONF.zaqar.ca_file
                    }
                }
            }

            if CONF.zaqar.use_websockets:
                data = self.get_data_websocket(ks, conf)
            else:
                data = self.get_data_wsgi(ks, conf)

            final_list = merger.merged_list_from_content(
                data, cfg.CONF.deployment_key, name)
            return final_list

        except Exception as e:
            logger.warn(str(e))
            raise exc.ZaqarMetadataNotAvailable()
