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

import os

from dogpile import cache
from keystoneclient.v3 import client as ks_keystoneclient
from oslo.config import cfg

CONF = cfg.CONF

opts = [
    cfg.StrOpt('cache_dir',
               help='A directory to store keystone auth tokens.'),
    cfg.IntOpt('cache_ttl',
               default=1800,
               help='Seconds to store auth references in the cache'),
]


class Keystone(object):
    '''A keystone wrapper class.

    This wrapper is used to encapsulate any keystone related operations
    os-collect-config may need to perform. Includes a dogpile cache to
    support memoization so we can reuse auth references stored on disk
    in subsequent invocations of os-collect-config.
    '''
    def __init__(self, auth_url, user_id, password, project_id,
                 keystoneclient=None):
        '''Initialize Keystone wrapper.

        @param string auth_url   auth_url for keystoneclient
        @param string user_id    user_id for keystoneclient
        @param string project_id project_id for keystoneclient
        @param object keystoneclient optional keystoneclient implementation.
                                     Uses keystoneclient.v3 if unspecified.
        '''
        self.keystoneclient = keystoneclient or ks_keystoneclient
        self.auth_url = auth_url
        self.user_id = user_id
        self.password = password
        self.project_id = project_id
        self._client = None
        if CONF.keystone.cache_dir:
            if not os.path.isdir(CONF.keystone.cache_dir):
                os.makedirs(CONF.keystone.cache_dir, mode=0o700)

            dbm_path = os.path.join(CONF.keystone.cache_dir, 'keystone.db')
            self.cache = cache.make_region().configure(
                'dogpile.cache.dbm',
                expiration_time=CONF.keystone.cache_ttl,
                arguments={"filename": dbm_path})
        else:
            self.cache = None

    @property
    def client(self):
        if not self._client:
            self._client = self.keystoneclient.Client(
                auth_url=self.auth_url,
                user_id=self.user_id,
                password=self.password,
                project_id=self.project_id)
        return self._client
