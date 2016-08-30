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

from keystoneclient.v3 import client as keystoneclient
from oslo_config import cfg
from oslo_log import log
import six
from zaqarclient.queues.v1 import client as zaqarclient

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
]
name = 'zaqar'


class Collector(object):
    def __init__(self,
                 keystoneclient=keystoneclient,
                 zaqarclient=zaqarclient):
        self.keystoneclient = keystoneclient
        self.zaqarclient = zaqarclient

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

        try:
            ks = keystone.Keystone(
                auth_url=CONF.zaqar.auth_url,
                user_id=CONF.zaqar.user_id,
                password=CONF.zaqar.password,
                project_id=CONF.zaqar.project_id,
                keystoneclient=self.keystoneclient).client
            endpoint = ks.service_catalog.url_for(
                service_type='messaging', endpoint_type='publicURL')
            logger.debug('Fetching metadata from %s' % endpoint)
            conf = {
                'auth_opts': {
                    'backend': 'keystone',
                    'options': {
                        'os_auth_token': ks.auth_token,
                        'os_project_id': CONF.zaqar.project_id
                    }
                }
            }

            zaqar = self.zaqarclient.Client(endpoint, conf=conf, version=1.1)

            queue = zaqar.queue(CONF.zaqar.queue_id)
            r = six.next(queue.pop())

            final_list = merger.merged_list_from_content(
                r.body, cfg.CONF.deployment_key, name)
            return final_list

        except Exception as e:
            logger.warn(str(e))
            raise exc.ZaqarMetadataNotAvailable()
