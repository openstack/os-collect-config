# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
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
from oslo.config import cfg

from openstack.common import log
from os_collect_config import common
from os_collect_config import exc

EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'
CONF = cfg.CONF
logger = log.getLogger(__name__)

opts = [
    cfg.StrOpt('metadata-url',
               help='URL to query for CloudFormation Metadata'),
    cfg.StrOpt('stack-name',
               help='Stack name to describe'),
    cfg.MultiStrOpt('path',
                    help='Path to Metadata'),
]


class CollectCfn(object):
    def __init__(self, requests_impl=common.requests):
        self._requests_impl = requests_impl
        self._session = requests_impl.Session()

    def collect(self):
        if CONF.cfn.metadata_url is None:
            logger.warn('No metadata_url configured.')
            raise exc.CfnMetadataNotConfigured
        url = CONF.cfn.metadata_url
        stack_name = CONF.cfn.stack_name
        headers = {'Content-Type': 'application/json'}
        final_content = {}
        if CONF.cfn.path is None:
            logger.warn('No path configured')
            raise exc.CfnMetadataNotConfigured

        for path in CONF.cfn.path:
            if '.' not in path:
                logger.error('Path not in format resource.field[.x.y] (%s)' %
                             path)
                raise exc.CfnMetadataNotConfigured
            resource, field = path.split('.', 1)
            if '.' in field:
                field, sub_path = field.split('.', 1)
            else:
                sub_path = ''
            params = {'Action': 'DescribeStackResource',
                      'Stackname': stack_name,
                      'LogicalResourceId': resource}
            try:
                content = self._session.get(
                    url, params=params, headers=headers)
                content.raise_for_status()
            except self._requests_impl.exceptions.RequestException as e:
                logger.warn(e)
                raise exc.CfnMetadataNotAvailable
            map_content = json.loads(content.text)
            if sub_path:
                if sub_path not in map_content:
                    logger.warn('Sub-path could not be found for Resource (%s)'
                                % path)
                    raise exc.CfnMetadataNotConfigured
                map_content = map_content[sub_path]

            final_content.update(map_content)
        return final_content
