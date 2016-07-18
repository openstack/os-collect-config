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
import os

from keystoneclient.contrib.ec2 import utils as ec2_utils
from lxml import etree
from oslo_config import cfg
from oslo_log import log
import six.moves.urllib.parse as urlparse

from os_collect_config import common
from os_collect_config import exc
from os_collect_config import merger

CONF = cfg.CONF
logger = log.getLogger(__name__)

opts = [
    cfg.StrOpt('metadata-url',
               help='URL to query for CloudFormation Metadata'),
    cfg.StrOpt('heat-metadata-hint',
               default='/var/lib/heat-cfntools/cfn-metadata-server',
               help='Local file to read for metadata url if not explicitly '
                    ' specified'),
    cfg.StrOpt('ca_certificate', help='CA Certificate path'),
    cfg.StrOpt('stack-name',
               help='Stack name to describe'),
    cfg.MultiStrOpt('path',
                    help='Path to Metadata'),
    cfg.StrOpt('secret-access-key',
               help='Secret Access Key'),
    cfg.StrOpt('access-key-id',
               help='Access Key ID'),
    cfg.MultiStrOpt('deployment-key',
                    default=['deployments'],
                    help='DEPRECATED, use global configuration option '
                         '"deployment-key"'),
    cfg.FloatOpt('timeout', default=10,
                 help='Seconds to wait for the connection and read request'
                      ' timeout.')
]
name = 'cfn'


class Collector(object):

    def __init__(self, requests_impl=common.requests):
        self._requests_impl = requests_impl
        self._session = requests_impl.Session()

    def collect(self):
        if CONF.cfn.metadata_url is None:
            if (CONF.cfn.heat_metadata_hint
                    and os.path.exists(CONF.cfn.heat_metadata_hint)):
                with open(CONF.cfn.heat_metadata_hint) as hint:
                    CONF.cfn.metadata_url = '%s/v1/' % hint.read().strip()
            else:
                logger.info('No metadata_url configured.')
                raise exc.CfnMetadataNotConfigured
        if CONF.cfn.access_key_id is None:
            logger.info('No Access Key ID configured.')
            raise exc.CfnMetadataNotConfigured
        if CONF.cfn.secret_access_key is None:
            logger.info('No Secret Access Key configured.')
            raise exc.CfnMetadataNotConfigured
        url = CONF.cfn.metadata_url
        stack_name = CONF.cfn.stack_name
        headers = {'Content-Type': 'application/json'}
        final_content = {}
        if CONF.cfn.path is None:
            logger.info('No path configured')
            raise exc.CfnMetadataNotConfigured

        signer = ec2_utils.Ec2Signer(secret_key=CONF.cfn.secret_access_key)
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
                      'StackName': stack_name,
                      'LogicalResourceId': resource,
                      'AWSAccessKeyId': CONF.cfn.access_key_id,
                      'SignatureVersion': '2'}
            parsed_url = urlparse.urlparse(url)
            credentials = {'params': params,
                           'verb': 'GET',
                           'host': parsed_url.netloc,
                           'path': parsed_url.path}
            params['Signature'] = signer.generate(credentials)
            try:
                content = self._session.get(
                    url, params=params, headers=headers,
                    verify=CONF.cfn.ca_certificate,
                    timeout=CONF.cfn.timeout)
                content.raise_for_status()
            except self._requests_impl.exceptions.RequestException as e:
                logger.warn(e)
                raise exc.CfnMetadataNotAvailable
            map_content = etree.fromstring(content.text)
            resource_detail = map_content.find(
                'DescribeStackResourceResult').find('StackResourceDetail')
            sub_element = resource_detail.find(field)
            if sub_element is None:
                logger.warn('Path %s does not exist.' % (path))
                raise exc.CfnMetadataNotAvailable
            try:
                value = json.loads(sub_element.text)
            except ValueError as e:
                logger.warn(
                    'Path %s failed to parse as json. (%s)' % (path, e))
                raise exc.CfnMetadataNotAvailable
            if sub_path:
                for subkey in sub_path.split('.'):
                    try:
                        value = value[subkey]
                    except KeyError:
                        logger.warn(
                            'Sub-key %s does not exist. (%s)' % (subkey, path))
                        raise exc.CfnMetadataNotAvailable
            final_content.update(value)
        final_list = merger.merged_list_from_content(
            final_content, cfg.CONF.cfn.deployment_key, name)
        return final_list
