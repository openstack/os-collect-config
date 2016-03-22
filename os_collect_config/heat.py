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

from heatclient import client as heatclient
from keystoneclient.v3 import client as keystoneclient
from oslo_config import cfg
from oslo_log import log

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
    cfg.StrOpt('stack-id',
               help='ID of the stack this deployment belongs to'),
    cfg.StrOpt('resource-name',
               help='Name of resource in the stack to be polled'),
]
name = 'heat'


class Collector(object):
    def __init__(self,
                 keystoneclient=keystoneclient,
                 heatclient=heatclient):
        self.keystoneclient = keystoneclient
        self.heatclient = heatclient

    def collect(self):
        if CONF.heat.auth_url is None:
            logger.info('No auth_url configured.')
            raise exc.HeatMetadataNotConfigured
        if CONF.heat.password is None:
            logger.info('No password configured.')
            raise exc.HeatMetadataNotConfigured
        if CONF.heat.project_id is None:
            logger.info('No project_id configured.')
            raise exc.HeatMetadataNotConfigured
        if CONF.heat.user_id is None:
            logger.info('No user_id configured.')
            raise exc.HeatMetadataNotConfigured
        if CONF.heat.stack_id is None:
            logger.info('No stack_id configured.')
            raise exc.HeatMetadataNotConfigured
        if CONF.heat.resource_name is None:
            logger.info('No resource_name configured.')
            raise exc.HeatMetadataNotConfigured

        try:
            ks = keystone.Keystone(
                auth_url=CONF.heat.auth_url,
                user_id=CONF.heat.user_id,
                password=CONF.heat.password,
                project_id=CONF.heat.project_id,
                keystoneclient=self.keystoneclient).client
            endpoint = ks.service_catalog.url_for(
                service_type='orchestration', endpoint_type='publicURL')
            logger.debug('Fetching metadata from %s' % endpoint)
            heat = self.heatclient.Client(
                '1', endpoint, token=ks.auth_token)
            r = heat.resources.metadata(CONF.heat.stack_id,
                                        CONF.heat.resource_name)

            final_list = merger.merged_list_from_content(
                r, cfg.CONF.deployment_key, name)
            return final_list

        except Exception as e:
            logger.warn(str(e))
            raise exc.HeatMetadataNotAvailable
