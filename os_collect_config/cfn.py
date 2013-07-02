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

from oslo.config import cfg
import requests

from openstack.common import log
from os_collect_config import exc

EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'
CONF = cfg.CONF

opts = [
    cfg.StrOpt('metadata-url',
               help='URL to query for CloudFormation Metadata'),
    cfg.MultiStrOpt('path',
                    help='Path to Metadata'),
]


def _fetch_metadata(fetch_url, session):
    try:
        r = session.get(fetch_url)
        r.raise_for_status()
    except (requests.HTTPError,
            requests.ConnectionError,
            requests.Timeout) as e:
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
            new_content[subkey] = _fetch_metadata(sub_fetch_url, session)
        content = new_content
    return content


def collect():
    root_url = '%s/' % (CONF.ec2.metadata_url)
    session = requests.Session()
    return _fetch_metadata(root_url, session)
