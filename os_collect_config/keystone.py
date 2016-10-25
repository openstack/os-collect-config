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

import hashlib
import os

from dogpile import cache
from keystoneclient import discover as ks_discover
from keystoneclient import exceptions as ks_exc
from keystoneclient.v3 import client as ks_keystoneclient
from oslo_config import cfg

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
                 keystoneclient=None, discover_class=None):
        '''Initialize Keystone wrapper.

        @param string auth_url   auth_url for keystoneclient
        @param string user_id    user_id for keystoneclient
        @param string project_id project_id for keystoneclient
        @param object keystoneclient optional keystoneclient implementation.
                                     Uses keystoneclient.v3 if unspecified.
        @param object discover_class optional keystoneclient.discover.Discover
                                     class.
        '''
        self.keystoneclient = keystoneclient or ks_keystoneclient
        self.discover_class = discover_class or ks_discover.Discover
        self.user_id = user_id
        self.password = password
        self.project_id = project_id
        self._client = None
        try:
            auth_url_noneversion = auth_url.replace('/v2.0', '/')
            discover = self.discover_class(auth_url=auth_url_noneversion)
            v3_auth_url = discover.url_for('3.0')
            if v3_auth_url:
                self.auth_url = v3_auth_url
            else:
                self.auth_url = auth_url
        except ks_exc.ClientException:
            self.auth_url = auth_url.replace('/v2.0', '/v3')
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

    def _make_key(self, key):
        m = hashlib.sha256()
        m.update(self.auth_url.encode('utf-8'))
        m.update(self.user_id.encode('utf-8'))
        m.update(self.project_id.encode('utf-8'))
        m.update(key.encode('utf-8'))
        return m.hexdigest()

    @property
    def client(self):
        if not self._client:
            ref = self._get_auth_ref_from_cache()
            if ref:
                self._client = self.keystoneclient.Client(
                    auth_ref=ref)
            else:
                self._client = self.keystoneclient.Client(
                    auth_url=self.auth_url,
                    user_id=self.user_id,
                    password=self.password,
                    project_id=self.project_id)
        return self._client

    def _get_auth_ref_from_cache(self):
        if self.cache:
            key = self._make_key('auth_ref')
            return self.cache.get(key)

    @property
    def auth_ref(self):
        ref = self._get_auth_ref_from_cache()
        if not ref:
            ref = self.client.get_auth_ref()
            if self.cache:
                self.cache.set(self._make_key('auth_ref'), ref)
        return ref

    def invalidate_auth_ref(self):
        if self.cache:
            key = self._make_key('auth_ref')
            return self.cache.delete(key)

    @property
    def service_catalog(self):
        try:
            return self.client.service_catalog
        except ks_exc.AuthorizationFailure:
            self.invalidate_auth_ref()
            return self.client.service_catalog
