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

import json
from unittest import mock

import fixtures
from keystoneclient import discover as ks_discover
from oslo_config import cfg
from oslo_config import fixture as config_fixture
import testtools
from testtools import matchers
from zaqarclient.queues.v1 import message
from zaqarclient import transport
from zaqarclient.transport import response

from os_collect_config import collect
from os_collect_config import exc
from os_collect_config.tests import test_heat
from os_collect_config import zaqar


class FakeKeystoneClient(test_heat.FakeKeystoneClient):

    def url_for(self, service_type, endpoint_type):
        self._test.assertEqual('messaging', service_type)
        self._test.assertEqual('publicURL', endpoint_type)
        return 'http://192.0.2.1:8888/'


class FakeKeystoneClientWebsocket(test_heat.FakeKeystoneClient):

    def url_for(self, service_type, endpoint_type):
        self._test.assertEqual('messaging-websocket', service_type)
        self._test.assertEqual('publicURL', endpoint_type)
        return 'ws://127.0.0.1:9000/'


class FakeZaqarClient(object):

    def __init__(self, testcase):
        self._test = testcase

    def Client(self, endpoint, conf, version):
        self._test.assertEqual(1.1, version)
        self._test.assertEqual('http://192.0.2.1:8888/', endpoint)
        return self

    def queue(self, queue_id):
        self._test.assertEqual(
            '4f3f46d3-09f1-42a7-8c13-f91a5457192c', queue_id)
        return FakeQueue()


class FakeZaqarWebsocketClient(object):

    def __init__(self, options, messages=None, testcase=None):
        self._messages = messages
        self._test = testcase

    def send(self, request):
        self._test.assertEqual('ws://127.0.0.1:9000/', request.endpoint)
        if request.operation == 'message_list':
            body = json.loads(request.content)
            self._test.assertEqual(
                '4f3f46d3-09f1-42a7-8c13-f91a5457192c', body['queue_name'])
        return response.Response(request, content=json.dumps(self._messages),
                                 status_code=200)

    def recv(self):
        return {'body': test_heat.META_DATA}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


class FakeQueue(object):

    def pop(self):
        return iter([message.Message(
            queue=self, ttl=10, age=10, body=test_heat.META_DATA, href='')])


class FakeZaqarClientSoftwareConfig(object):

    def __init__(self, testcase):
        self._test = testcase

    def Client(self, endpoint, conf, version):
        self._test.assertEqual(1.1, version)
        self._test.assertEqual('http://192.0.2.1:8888/', endpoint)
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

        conf = config_fixture.Config()
        self.useFixture(conf)
        conf.config(group='zaqar', use_websockets=False)
        conf.config(group='zaqar', auth_url='http://192.0.2.1:5000/v3')
        conf.config(group='zaqar', user_id='0123456789ABCDEF')
        conf.config(group='zaqar', password='FEDCBA9876543210')
        conf.config(group='zaqar',
                    project_id='9f6b09df-4d7f-4a33-8ec3-9924d8f46f10')
        conf.config(group='zaqar',
                    queue_id='4f3f46d3-09f1-42a7-8c13-f91a5457192c')
        conf.config(group='zaqar', ssl_certificate_validation=True)
        conf.config(group='zaqar', ca_file='/foo/bar')

    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_zaqar(self, mock_url_for, mock___init__):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.zaqar.auth_url
        zaqar_md = zaqar.Collector(
            keystoneclient=FakeKeystoneClient(self, cfg.CONF.zaqar),
            zaqarclient=FakeZaqarClient(self),
            discover_class=test_heat.FakeKeystoneDiscover).collect()
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
            zaqarclient=FakeZaqarClientSoftwareConfig(self),
            discover_class=test_heat.FakeKeystoneDiscover).collect()
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
            zaqarclient=FakeZaqarClient(self),
            discover_class=test_heat.FakeKeystoneDiscover)
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

    def test_collect_zaqar_no_ca_file(self):
        cfg.CONF.zaqar.ssl_certificate_validation = True
        cfg.CONF.zaqar.ca_file = None
        zaqar_collect = zaqar.Collector()
        self.assertRaises(
            exc.ZaqarMetadataNotConfigured, zaqar_collect.collect)
        expected = ('No CA file configured when flag ssl certificate '
                    'validation is on.')
        self.assertIn(expected, self.log.output)

    @mock.patch.object(transport, 'get_transport_for')
    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_zaqar_websocket(self, mock_url_for, mock___init__,
                                     mock_transport):

        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.zaqar.auth_url
        conf = config_fixture.Config()
        self.useFixture(conf)
        conf.config(group='zaqar', use_websockets=True)
        messages = {'messages': [{'body': test_heat.META_DATA, 'id': 1}]}
        ws = FakeZaqarWebsocketClient({}, messages=messages, testcase=self)
        mock_transport.return_value = ws
        zaqar_md = zaqar.Collector(
            keystoneclient=FakeKeystoneClientWebsocket(self, cfg.CONF.zaqar)
        ).collect()
        self.assertThat(zaqar_md, matchers.IsInstance(list))
        self.assertEqual('zaqar', zaqar_md[0][0])
        zaqar_md = zaqar_md[0][1]

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, zaqar_md)
            self.assertEqual(zaqar_md[k], test_heat.META_DATA[k])

    @mock.patch.object(transport, 'get_transport_for')
    @mock.patch.object(ks_discover.Discover, '__init__')
    @mock.patch.object(ks_discover.Discover, 'url_for')
    def test_collect_zaqar_websocket_recv(self, mock_url_for, mock___init__,
                                          mock_transport):
        mock___init__.return_value = None
        mock_url_for.return_value = cfg.CONF.zaqar.auth_url
        ws = FakeZaqarWebsocketClient({}, messages={}, testcase=self)
        mock_transport.return_value = ws
        conf = config_fixture.Config()
        self.useFixture(conf)
        conf.config(group='zaqar', use_websockets=True)
        zaqar_md = zaqar.Collector(
            keystoneclient=FakeKeystoneClientWebsocket(self, cfg.CONF.zaqar),
        ).collect()
        self.assertThat(zaqar_md, matchers.IsInstance(list))
        self.assertEqual('zaqar', zaqar_md[0][0])
        zaqar_md = zaqar_md[0][1]

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, zaqar_md)
            self.assertEqual(zaqar_md[k], test_heat.META_DATA[k])
