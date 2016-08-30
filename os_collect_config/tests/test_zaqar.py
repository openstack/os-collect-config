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
import mock
from oslo_config import cfg
import testtools
from testtools import matchers
from zaqarclient.queues.v1 import message

from os_collect_config import collect
from os_collect_config import exc
from os_collect_config.tests import test_heat
from os_collect_config import zaqar


class FakeKeystoneClient(test_heat.FakeKeystoneClient):

    def url_for(self, service_type, endpoint_type):
        self._test.assertEqual('messaging', service_type)
        self._test.assertEqual('publicURL', endpoint_type)
        return 'http://127.0.0.1:8888/'


class FakeZaqarClient(object):

    def __init__(self, testcase):
        self._test = testcase

    def Client(self, endpoint, conf, version):
        self._test.assertEqual(1.1, version)
        self._test.assertEqual('http://127.0.0.1:8888/', endpoint)
        return self

    def queue(self, queue_id):
        self._test.assertEqual(
            '4f3f46d3-09f1-42a7-8c13-f91a5457192c', queue_id)
        return FakeQueue()


class FakeQueue(object):

    def pop(self):
        return iter([message.Message(
            queue=self, ttl=10, age=10, body=test_heat.META_DATA, href='')])


class FakeZaqarClientSoftwareConfig(object):

    def __init__(self, testcase):
        self._test = testcase

    def Client(self, endpoint, conf, version):
        self._test.assertEqual(1.1, version)
        self._test.assertEqual('http://127.0.0.1:8888/', endpoint)
        return self

    def queue(self, queue_id):
        self._test.assertEqual(
            '4f3f46d3-09f1-42a7-8c13-f91a5457192c', queue_id)
        return FakeQueueSoftwareConfig()


class FakeQueueSoftwareConfig(object):

    def pop(self):
        return iter([message.Message(
            queue=self, ttl=10, age=10, body=test_heat.SOFTWARE_CONFIG_DATA,
            href='')])


class TestZaqar(testtools.TestCase):
    def setUp(self):
        super(TestZaqar, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        self.useFixture(fixtures.NestedTempfile())
        collect.setup_conf()
        cfg.CONF.zaqar.auth_url = 'http://127.0.0.1:5000/v3'
        cfg.CONF.zaqar.user_id = '0123456789ABCDEF'
        cfg.CONF.zaqar.password = 'FEDCBA9876543210'
        cfg.CONF.zaqar.project_id = '9f6b09df-4d7f-4a33-8ec3-9924d8f46f10'
        cfg.CONF.zaqar.queue_id = '4f3f46d3-09f1-42a7-8c13-f91a5457192c'

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_zaqar(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.zaqar.auth_url
        zaqar_md = zaqar.Collector(
            keystoneclient=FakeKeystoneClient(self, cfg.CONF.zaqar),
            zaqarclient=FakeZaqarClient(self)).collect()
        self.assertThat(zaqar_md, matchers.IsInstance(list))
        self.assertEqual('zaqar', zaqar_md[0][0])
        zaqar_md = zaqar_md[0][1]

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, zaqar_md)
            self.assertEqual(zaqar_md[k], test_heat.META_DATA[k])

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_zaqar_deployments(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.zaqar.auth_url
        zaqar_md = zaqar.Collector(
            keystoneclient=FakeKeystoneClient(self, cfg.CONF.zaqar),
            zaqarclient=FakeZaqarClientSoftwareConfig(self)).collect()
        self.assertThat(zaqar_md, matchers.IsInstance(list))
        self.assertEqual('zaqar', zaqar_md[0][0])
        self.assertEqual(2, len(zaqar_md))
        self.assertEqual('zaqar', zaqar_md[0][0])
        self.assertEqual(
            test_heat.SOFTWARE_CONFIG_DATA['deployments'],
            zaqar_md[0][1]['deployments'])
        self.assertEqual(
            ('dep-name1', {'config1': 'value1'}), zaqar_md[1])

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_zaqar_fail(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.zaqar.auth_url
        zaqar_collect = zaqar.Collector(
            keystoneclient=test_heat.FakeFailKeystoneClient(
                self, cfg.CONF.zaqar),
            zaqarclient=FakeZaqarClient(self))
        self.assertRaises(exc.ZaqarMetadataNotAvailable, zaqar_collect.collect)
        self.assertIn('Forbidden', self.log.output)

    def test_collect_zaqar_no_auth_url(self):
        cfg.CONF.zaqar.auth_url = None
        zaqar_collect = zaqar.Collector()
        self.assertRaises(
            exc.ZaqarMetadataNotConfigured, zaqar_collect.collect)
        self.assertIn('No auth_url configured', self.log.output)

    def test_collect_zaqar_no_password(self):
        cfg.CONF.zaqar.password = None
        zaqar_collect = zaqar.Collector()
        self.assertRaises(
            exc.ZaqarMetadataNotConfigured, zaqar_collect.collect)
        self.assertIn('No password configured', self.log.output)

    def test_collect_zaqar_no_project_id(self):
        cfg.CONF.zaqar.project_id = None
        zaqar_collect = zaqar.Collector()
        self.assertRaises(
            exc.ZaqarMetadataNotConfigured, zaqar_collect.collect)
        self.assertIn('No project_id configured', self.log.output)

    def test_collect_zaqar_no_user_id(self):
        cfg.CONF.zaqar.user_id = None
        zaqar_collect = zaqar.Collector()
        self.assertRaises(
            exc.ZaqarMetadataNotConfigured, zaqar_collect.collect)
        self.assertIn('No user_id configured', self.log.output)

    def test_collect_zaqar_no_queue_id(self):
        cfg.CONF.zaqar.queue_id = None
        zaqar_collect = zaqar.Collector()
        self.assertRaises(
            exc.ZaqarMetadataNotConfigured, zaqar_collect.collect)
        self.assertIn('No queue_id configured', self.log.output)
