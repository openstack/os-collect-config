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

import tempfile

import fixtures
from keystoneclient import exceptions as ks_exc
from oslo_config import cfg
import testtools

from os_collect_config import collect
from os_collect_config import keystone
from os_collect_config.tests import test_heat


class FakeKeystoneDiscoverNone(test_heat.FakeKeystoneDiscover):

    def url_for(self, version):
        return None


class FakeKeystoneDiscoverError(test_heat.FakeKeystoneDiscover):

    def url_for(self, version):
        raise ks_exc.DiscoveryFailure()


class FakeKeystoneDiscoverBase(test_heat.FakeKeystoneDiscover):

    def url_for(self, version):
        return 'http://192.0.2.1:5000/'


class KeystoneTest(testtools.TestCase):
    def setUp(self):
        super(KeystoneTest, self).setUp()
        self.addCleanup(cfg.CONF.reset)
        collect.setup_conf()
        self.useFixture(fixtures.NestedTempfile())
        self.cachedir = tempfile.mkdtemp()
        cfg.CONF.set_override('cache_dir', self.cachedir, group='keystone')

    def test_discover_fail(self):
        ks = keystone.Keystone(
            'http://192.0.2.1:5000/v2.0', 'auser', 'apassword', 'aproject',
            test_heat.FakeKeystoneClient(self),
            FakeKeystoneDiscoverError)
        self.assertEqual(ks.auth_url, 'http://192.0.2.1:5000/v3')

    def test_discover_v3_unsupported(self):
        ks = keystone.Keystone(
            'http://192.0.2.1:5000/v2.0', 'auser', 'apassword', 'aproject',
            test_heat.FakeKeystoneClient(self),
            FakeKeystoneDiscoverNone)
        self.assertEqual(ks.auth_url, 'http://192.0.2.1:5000/v2.0')

    def test_cache_is_created(self):
        ks = keystone.Keystone(
            'http://192.0.2.1:5000/', 'auser', 'apassword', 'aproject',
            test_heat.FakeKeystoneClient(self),
            test_heat.FakeKeystoneDiscover)
        self.assertIsNotNone(ks.cache)

    def _make_ks(self, client):
        class Configs(object):
            auth_url = 'http://192.0.2.1:5000/'
            user_id = 'auser'
            password = 'apassword'
            project_id = 'aproject'

        return keystone.Keystone(
            'http://192.0.2.1:5000/', 'auser', 'apassword', 'aproject',
            client(self, Configs),
            FakeKeystoneDiscoverBase)

    def test_cache_auth_ref(self):
        ks = self._make_ks(test_heat.FakeKeystoneClient)
        auth_ref = ks.auth_ref
        # Client must fail now - we should make no client calls
        ks2 = self._make_ks(test_heat.FakeFailKeystoneClient)
        auth_ref2 = ks2.auth_ref
        self.assertEqual(auth_ref, auth_ref2)
        # And can we invalidate
        ks2.invalidate_auth_ref()
        # Can't use assertRaises because it is a @property
        try:
            ks2.auth_ref
            self.assertTrue(False, 'auth_ref should have failed.')
        except ks_exc.AuthorizationFailure:
            pass
