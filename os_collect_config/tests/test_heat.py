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

import fixtures
from keystoneclient import discover as ks_discover
from keystoneclient import exceptions as ks_exc
import mock
from oslo_config import cfg
import testtools
from testtools import matchers

from os_collect_config import collect
from os_collect_config import exc
from os_collect_config import heat


META_DATA = {u'int1': 1,
             u'strfoo': u'foo',
             u'map_ab': {
                 u'a': 'apple',
                 u'b': 'banana',
             }}


SOFTWARE_CONFIG_DATA = {
    u'old-style': u'value',
    u'deployments': [
        {
            u'inputs': [
                {
                    u'type': u'String',
                    u'name': u'input1',
                    u'value': u'value1'
                }
            ],
            u'group': 'Heat::Ungrouped',
            u'name': 'dep-name1',
            u'outputs': None,
            u'options': None,
            u'config': {
                u'config1': 'value1'
            }
        }
    ]
}


SOFTWARE_CONFIG_IMPOSTER_DATA = {
    u'old-style': u'value',
    u'deployments': {
        u"not": u"a list"
    }
}


class FakeKeystoneClient(object):

    def __init__(self, testcase, configs=None):
        self._test = testcase
        self.service_catalog = self
        self.auth_token = 'atoken'
        if configs is None:
            configs = cfg.CONF.heat
        self.configs = configs

    def Client(self, auth_url, user_id, password, project_id):
        self._test.assertEqual(self.configs.auth_url, auth_url)
        self._test.assertEqual(self.configs.user_id, user_id)
        self._test.assertEqual(self.configs.password, password)
        self._test.assertEqual(self.configs.project_id, project_id)
        return self

    def url_for(self, service_type, endpoint_type):
        self._test.assertEqual('orchestration', service_type)
        self._test.assertEqual('publicURL', endpoint_type)
        return 'http://127.0.0.1:8004/v1'

    def get_auth_ref(self):
        return 'this is an auth_ref'


class FakeFailKeystoneClient(FakeKeystoneClient):

    def Client(self, auth_url, user_id, password, project_id):
        raise ks_exc.AuthorizationFailure('Forbidden')


class FakeHeatClient(object):
    def __init__(self, testcase):
        self._test = testcase
        self.resources = self

    def Client(self, version, endpoint, token):
        self._test.assertEqual('1', version)
        self._test.assertEqual('http://127.0.0.1:8004/v1', endpoint)
        self._test.assertEqual('atoken', token)
        return self

    def metadata(self, stack_id, resource_name):
        self._test.assertEqual(cfg.CONF.heat.stack_id, stack_id)
        self._test.assertEqual(cfg.CONF.heat.resource_name, resource_name)
        return META_DATA


class FakeHeatClientSoftwareConfig(FakeHeatClient):

    def metadata(self, stack_id, resource_name):
        return SOFTWARE_CONFIG_DATA


class TestHeatBase(testtools.TestCase):
    def setUp(self):
        super(TestHeatBase, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        self.useFixture(fixtures.NestedTempfile())
        collect.setup_conf()
        cfg.CONF.heat.auth_url = 'http://127.0.0.1:5000/v3'
        cfg.CONF.heat.user_id = '0123456789ABCDEF'
        cfg.CONF.heat.password = 'FEDCBA9876543210'
        cfg.CONF.heat.project_id = '9f6b09df-4d7f-4a33-8ec3-9924d8f46f10'
        cfg.CONF.heat.stack_id = 'a/c482680f-7238-403d-8f76-36acf0c8e0aa'
        cfg.CONF.heat.resource_name = 'server'


class TestHeat(TestHeatBase):
    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_heat(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.heat.auth_url
        heat_md = heat.Collector(keystoneclient=FakeKeystoneClient(self),
                                 heatclient=FakeHeatClient(self)).collect()
        self.assertThat(heat_md, matchers.IsInstance(list))
        self.assertEqual('heat', heat_md[0][0])
        heat_md = heat_md[0][1]

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, heat_md)
            self.assertEqual(heat_md[k], META_DATA[k])

        # FIXME(yanyanhu): Temporary hack to deal with possible log
        # level setting for urllib3.connectionpool.
        self.assertTrue(
            self.log.output == '' or
            self.log.output == 'Starting new HTTP connection (1): 127.0.0.1\n')

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_heat_fail(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.heat.auth_url
        heat_collect = heat.Collector(
            keystoneclient=FakeFailKeystoneClient(self),
            heatclient=FakeHeatClient(self))
        self.assertRaises(exc.HeatMetadataNotAvailable, heat_collect.collect)
        self.assertIn('Forbidden', self.log.output)

    def test_collect_heat_no_auth_url(self):
        cfg.CONF.heat.auth_url = None
        heat_collect = heat.Collector()
        self.assertRaises(exc.HeatMetadataNotConfigured, heat_collect.collect)
        self.assertIn('No auth_url configured', self.log.output)

    def test_collect_heat_no_password(self):
        cfg.CONF.heat.password = None
        heat_collect = heat.Collector()
        self.assertRaises(exc.HeatMetadataNotConfigured, heat_collect.collect)
        self.assertIn('No password configured', self.log.output)

    def test_collect_heat_no_project_id(self):
        cfg.CONF.heat.project_id = None
        heat_collect = heat.Collector()
        self.assertRaises(exc.HeatMetadataNotConfigured, heat_collect.collect)
        self.assertIn('No project_id configured', self.log.output)

    def test_collect_heat_no_user_id(self):
        cfg.CONF.heat.user_id = None
        heat_collect = heat.Collector()
        self.assertRaises(exc.HeatMetadataNotConfigured, heat_collect.collect)
        self.assertIn('No user_id configured', self.log.output)

    def test_collect_heat_no_stack_id(self):
        cfg.CONF.heat.stack_id = None
        heat_collect = heat.Collector()
        self.assertRaises(exc.HeatMetadataNotConfigured, heat_collect.collect)
        self.assertIn('No stack_id configured', self.log.output)

    def test_collect_heat_no_resource_name(self):
        cfg.CONF.heat.resource_name = None
        heat_collect = heat.Collector()
        self.assertRaises(exc.HeatMetadataNotConfigured, heat_collect.collect)
        self.assertIn('No resource_name configured', self.log.output)


class TestHeatSoftwareConfig(TestHeatBase):
    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_heat(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.heat.auth_url
        heat_md = heat.Collector(
            keystoneclient=FakeKeystoneClient(self),
            heatclient=FakeHeatClientSoftwareConfig(self)).collect()
        self.assertThat(heat_md, matchers.IsInstance(list))
        self.assertEqual(2, len(heat_md))
        self.assertEqual('heat', heat_md[0][0])
        self.assertEqual(
            SOFTWARE_CONFIG_DATA['deployments'], heat_md[0][1]['deployments'])
        self.assertEqual(
            ('dep-name1', {'config1': 'value1'}), heat_md[1])
