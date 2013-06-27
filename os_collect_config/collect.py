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

import httplib2
import json

from openstack.common import log
from os_collect_config import exc
from oslo.config import cfg


EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'

h = httplib2.Http()

ec2_opts = [
    cfg.StrOpt('metadata_url',
               default=EC2_METADATA_URL,
               help='URL to query for EC2 Metadata')
]


def _fetch_metadata(fetch_url):
    global h
    try:
        (resp, content) = h.request(fetch_url)
    except httplib2.socks.HTTPError as e:
        log.getLogger().warn(e)
        raise exc.Ec2MetadataNotAvailable
    if fetch_url[-1] == '/':
        new_content = {}
        for subkey in content.split("\n"):
            if '=' in subkey:
                subkey = subkey[:subkey.index('=')] + '/'
            sub_fetch_url = fetch_url + subkey
            if subkey[-1] == '/':
                subkey = subkey[:-1]
            new_content[subkey] = _fetch_metadata(sub_fetch_url)
        content = new_content
    return content


def collect_ec2(ec2_url):
    root_url = '%s/' % (ec2_url)
    return _fetch_metadata(root_url)


def __main__():
    ec2_group = cfg.OptGroup(name='ec2',
                             title='EC2 Metadata options')

    conf = cfg.ConfigOpts()
    conf.register_group(ec2_group)
    conf.register_opts(ec2_opts, group='ec2')

    log.setup("os-collect-config")
    print json.dumps(collect_ec2(conf.ec2.metadata_url), indent=1)


if __name__ == '__main__':
    __main__()
