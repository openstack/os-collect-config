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

from oslo_config import cfg
from oslo_log import log

from os_collect_config import common
from os_collect_config import exc

EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'
CONF = cfg.CONF

opts = [
    cfg.StrOpt('metadata-url',
               default=EC2_METADATA_URL,
               help='URL to query for EC2 Metadata'),
    cfg.FloatOpt('timeout', default=10,
                 help='Seconds to wait for the connection and read request'
                      ' timeout.')
]
name = 'ec2'


class Collector(object):
    def __init__(self, requests_impl=common.requests):
        self._requests_impl = requests_impl
        self.session = requests_impl.Session()

    def _fetch_metadata(self, fetch_url, timeout):
        try:
            r = self.session.get(fetch_url, timeout=timeout)
            r.raise_for_status()
        except self._requests_impl.exceptions.RequestException as e:
            log.getLogger(__name__).warn(e)
            raise exc.Ec2MetadataNotAvailable
        content = r.text
        if fetch_url[-1] == '/':
            new_content = {}
            for subkey in content.split("\n"):
                if '=' in subkey:
                    subkey = subkey[:subkey.index('=')] + '/'
                sub_fetch_url = fetch_url + subkey
                if subkey[-1] == '/':
                    subkey = subkey[:-1]
                new_content[subkey] = self._fetch_metadata(
                    sub_fetch_url, timeout)
            content = new_content
        return content

    def collect(self):
        root_url = '%s/' % (CONF.ec2.metadata_url)
        return [('ec2', self._fetch_metadata(root_url, CONF.ec2.timeout))]
