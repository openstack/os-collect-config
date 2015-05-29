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
from keystoneclient import discover as ks_discover
from keystoneclient import exceptions as ks_exc
import mock
from oslo_config import cfg
import testtools

from os_collect_config import collect
from os_collect_config import keystone
from os_collect_config.tests import test_heat


class FakeKeystoneClient(object):
    def __init__(self, *args, **kwargs):
        pass

    def Client(self, *args, **kwargs):
        return self

    @property
    def service_catalog(self):
        return {}


class FakeFailGetAuthRef(FakeKeystoneClient):
    def get_auth_ref(self):
        raise ks_exc.AuthorizationFailed('Should not be called')


class KeystoneTest(testtools.TestCase):
    def setUp(self):
        super(KeystoneTest, self).setUp()
        self.addCleanup(cfg.CONF.reset)
        collect.setup_conf()
        self.useFixture(fixtures.NestedTempfile())
        self.cachedir = tempfile.mkdtemp()
        cfg.CONF.set_override('cache_dir', self.cachedir, group='keystone')

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_discover_fail(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.side_effect = ks_exc.DiscoveryFailure()
        ks = keystone.Keystone(
            'http://server.test:5000/v2.0', 'auser', 'apassword', 'aproject',
            test_heat.FakeKeystoneClient(self))
        self.assertEqual(ks.auth_url, 'http://server.test:5000/v3')

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_discover_v3_unsupported(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = None
        ks = keystone.Keystone(
            'http://server.test:5000/v2.0', 'auser', 'apassword', 'aproject',
            test_heat.FakeKeystoneClient(self))
        self.assertEqual(ks.auth_url, 'http://server.test:5000/v2.0')
        mock___init__.assert_called_with(auth_url='http://server.test:5000/')

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_cache_is_created(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = 'http://server.test:5000/'
        ks = keystone.Keystone(
            'http://server.test:5000/', 'auser', 'apassword', 'aproject',
            test_heat.FakeKeystoneClient(self))
        self.assertIsNotNone(ks.cache)

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def _make_ks(self, client, mock_url_for, mock___init__):
        class Configs(object):
            auth_url = 'http://server.test:5000/'
            user_id = 'auser'
            password = 'apassword'
            project_id = 'aproject'

        mock___init__.return_value = None
        mock_url_for.return_value = Configs.auth_url
        return keystone.Keystone(
            'http://server.test:5000/', 'auser', 'apassword', 'aproject',
            client(self, Configs))

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

    def test_service_catalog(self):
        ks = self._make_ks(FakeKeystoneClient)
        service_catalog = ks.service_catalog
        ks2 = self._make_ks(FakeKeystoneClient)
        service_catalog2 = ks2.service_catalog
        self.assertEqual(service_catalog, service_catalog2)
        ks2.invalidate_auth_ref()
        service_catalog3 = ks.service_catalog
        self.assertEqual(service_catalog, service_catalog3)
