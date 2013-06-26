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


EC2_METADATA_URL = 'http://169.254.169.254/latest/meta-data'


def _fetch_metadata(sub_url):
    h = httplib2.Http()
    (resp, content) = h.request('%s%s' % (EC2_METADATA_URL, sub_url))
    if resp.status != 200:
        raise Exception('Error fetching %s' % sub_url)
    return content


def collect_ec2():
    ec2_metadata = {}
    root_list = _fetch_metadata('/')
    for item in root_list.split("\n"):
        ec2_metadata[item] = _fetch_metadata('/%s' % item)
    return ec2_metadata


def __main__():
    print json.dumps(collect_ec2())


if __name__ == '__main__':
    __main__()
