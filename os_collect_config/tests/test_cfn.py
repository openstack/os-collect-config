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

import json
import tempfile

import fixtures
from lxml import etree
from oslo_config import cfg
import requests
import six.moves.urllib.parse as urlparse
import testtools
from testtools import content as test_content
from testtools import matchers

from os_collect_config import cfn
from os_collect_config import collect
from os_collect_config import exc


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
        },
        {
            u'inputs': [
                {
                    u'type': u'String',
                    u'name': u'input1',
                    u'value': u'value1'
                }
            ],
            u'group': 'os-apply-config',
            u'name': 'dep-name2',
            u'outputs': None,
            u'options': None,
            u'config': {
                u'config2': 'value2'
            }
        },
        {
            u'inputs': [
                {
                    u'type': u'String',
                    u'name': u'input1',
                    u'value': u'value1'
                }
            ],
            u'name': 'dep-name3',
            u'outputs': None,
            u'options': None,
            u'config': {
                u'config3': 'value3'
            }
        },
        {
            u'inputs': [],
            u'group': 'ignore_me',
            u'name': 'ignore_me_name',
            u'outputs': None,
            u'options': None,
            u'config': 'ignore_me_config'
        }
    ]
}


SOFTWARE_CONFIG_IMPOSTER_DATA = {
    u'old-style': u'value',
    u'deployments': {
        u"not": u"a list"
    }
}


class FakeResponse(dict):
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeReqSession(object):

    SESSION_META_DATA = META_DATA

    def __init__(self, testcase, expected_netloc):
        self._test = testcase
        self._expected_netloc = expected_netloc
        self.verify = False

    def get(self, url, params, headers, verify=None, timeout=None):
        self._test.addDetail('url', test_content.text_content(url))
        url = urlparse.urlparse(url)
        self._test.assertEqual(self._expected_netloc, url.netloc)
        self._test.assertEqual('/v1/', url.path)
        self._test.assertEqual('application/json',
                               headers['Content-Type'])
        self._test.assertIn('SignatureVersion', params)
        self._test.assertEqual('2', params['SignatureVersion'])
        self._test.assertIn('Signature', params)
        self._test.assertIn('Action', params)
        self._test.assertEqual('DescribeStackResource',
                               params['Action'])
        self._test.assertIn('LogicalResourceId', params)
        self._test.assertEqual('foo', params['LogicalResourceId'])
        self._test.assertEqual(10, timeout)
        root = etree.Element('DescribeStackResourceResponse')
        result = etree.SubElement(root, 'DescribeStackResourceResult')
        detail = etree.SubElement(result, 'StackResourceDetail')
        metadata = etree.SubElement(detail, 'Metadata')
        metadata.text = json.dumps(self.SESSION_META_DATA)
        if verify is not None:
            self.verify = True
        return FakeResponse(etree.tostring(root))


class FakeRequests(object):
    exceptions = requests.exceptions

    def __init__(self, testcase, expected_netloc='127.0.0.1:8000'):
        self._test = testcase
        self._expected_netloc = expected_netloc

    def Session(self):

        return FakeReqSession(self._test, self._expected_netloc)


class FakeReqSessionSoftwareConfig(FakeReqSession):

    SESSION_META_DATA = SOFTWARE_CONFIG_DATA


class FakeRequestsSoftwareConfig(FakeRequests):

    FAKE_SESSION = FakeReqSessionSoftwareConfig

    def Session(self):
        return self.FAKE_SESSION(self._test, self._expected_netloc)


class FakeReqSessionConfigImposter(FakeReqSession):

    SESSION_META_DATA = SOFTWARE_CONFIG_IMPOSTER_DATA


class FakeRequestsConfigImposter(FakeRequestsSoftwareConfig):

    FAKE_SESSION = FakeReqSessionConfigImposter


class FakeFailRequests(object):
    exceptions = requests.exceptions

    class Session(object):
        def get(self, url, params, headers, verify=None, timeout=None):
            raise requests.exceptions.HTTPError(403, 'Forbidden')


class TestCfnBase(testtools.TestCase):
    def setUp(self):
        super(TestCfnBase, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        self.useFixture(fixtures.NestedTempfile())
        self.hint_file = tempfile.NamedTemporaryFile()
        self.hint_file.write(u'http://127.0.0.1:8000'.encode('utf-8'))
        self.hint_file.flush()
        self.addCleanup(self.hint_file.close)
        collect.setup_conf()
        cfg.CONF.cfn.heat_metadata_hint = self.hint_file.name
        cfg.CONF.cfn.metadata_url = None
        cfg.CONF.cfn.path = ['foo.Metadata']
        cfg.CONF.cfn.access_key_id = '0123456789ABCDEF'
        cfg.CONF.cfn.secret_access_key = 'FEDCBA9876543210'


class TestCfn(TestCfnBase):
    def test_collect_cfn(self):
        cfn_md = cfn.Collector(requests_impl=FakeRequests(self)).collect()
        self.assertThat(cfn_md, matchers.IsInstance(list))
        self.assertEqual('cfn', cfn_md[0][0])
        cfn_md = cfn_md[0][1]

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, cfn_md)
            self.assertEqual(cfn_md[k], META_DATA[k])

        self.assertEqual('', self.log.output)

    def test_collect_with_ca_cert(self):
        cfn.CONF.cfn.ca_certificate = "foo"
        collector = cfn.Collector(requests_impl=FakeRequests(self))
        collector.collect()
        self.assertTrue(collector._session.verify)

    def test_collect_cfn_fail(self):
        cfn_collect = cfn.Collector(requests_impl=FakeFailRequests)
        self.assertRaises(exc.CfnMetadataNotAvailable, cfn_collect.collect)
        self.assertIn('Forbidden', self.log.output)

    def test_collect_cfn_no_path(self):
        cfg.CONF.cfn.path = None
        cfn_collect = cfn.Collector(requests_impl=FakeRequests(self))
        self.assertRaises(exc.CfnMetadataNotConfigured, cfn_collect.collect)
        self.assertIn('No path configured', self.log.output)

    def test_collect_cfn_bad_path(self):
        cfg.CONF.cfn.path = ['foo']
        cfn_collect = cfn.Collector(requests_impl=FakeRequests(self))
        self.assertRaises(exc.CfnMetadataNotConfigured, cfn_collect.collect)
        self.assertIn('Path not in format', self.log.output)

    def test_collect_cfn_no_metadata_url(self):
        cfg.CONF.cfn.heat_metadata_hint = None
        cfn_collect = cfn.Collector(requests_impl=FakeRequests(self))
        self.assertRaises(exc.CfnMetadataNotConfigured, cfn_collect.collect)
        self.assertIn('No metadata_url configured', self.log.output)

    def test_collect_cfn_missing_sub_path(self):
        cfg.CONF.cfn.path = ['foo.Metadata.not_there']
        cfn_collect = cfn.Collector(requests_impl=FakeRequests(self))
        self.assertRaises(exc.CfnMetadataNotAvailable, cfn_collect.collect)
        self.assertIn('Sub-key not_there does not exist', self.log.output)

    def test_collect_cfn_sub_path(self):
        cfg.CONF.cfn.path = ['foo.Metadata.map_ab']
        cfn_collect = cfn.Collector(requests_impl=FakeRequests(self))
        content = cfn_collect.collect()
        self.assertThat(content, matchers.IsInstance(list))
        self.assertEqual('cfn', content[0][0])
        content = content[0][1]
        self.assertIn(u'b', content)
        self.assertEqual(u'banana', content[u'b'])

    def test_collect_cfn_metadata_url_overrides_hint(self):
        cfg.CONF.cfn.metadata_url = 'http://127.0.1.1:8000/v1/'
        cfn_collect = cfn.Collector(
            requests_impl=FakeRequests(self,
                                       expected_netloc='127.0.1.1:8000'))
        cfn_collect.collect()


class TestCfnSoftwareConfig(TestCfnBase):
    def test_collect_cfn_software_config(self):
        cfn_md = cfn.Collector(
            requests_impl=FakeRequestsSoftwareConfig(self)).collect()
        self.assertThat(cfn_md, matchers.IsInstance(list))
        self.assertEqual('cfn', cfn_md[0][0])
        cfn_config = cfn_md[0][1]
        self.assertThat(cfn_config, matchers.IsInstance(dict))
        self.assertEqual(set(['old-style', 'deployments']),
                         set(cfn_config.keys()))
        self.assertIn('deployments', cfn_config)
        self.assertThat(cfn_config['deployments'], matchers.IsInstance(list))
        self.assertEqual(4, len(cfn_config['deployments']))
        deployment = cfn_config['deployments'][0]
        self.assertIn('inputs', deployment)
        self.assertThat(deployment['inputs'], matchers.IsInstance(list))
        self.assertEqual(1, len(deployment['inputs']))
        self.assertEqual('dep-name1', cfn_md[1][0])
        self.assertEqual('value1', cfn_md[1][1]['config1'])
        self.assertEqual('dep-name2', cfn_md[2][0])
        self.assertEqual('value2', cfn_md[2][1]['config2'])

    def test_collect_cfn_deployments_not_list(self):
        cfn_md = cfn.Collector(
            requests_impl=FakeRequestsConfigImposter(self)).collect()
        self.assertEqual(1, len(cfn_md))
        self.assertEqual('cfn', cfn_md[0][0])
        self.assertIn('not', cfn_md[0][1]['deployments'])
        self.assertEqual('a list', cfn_md[0][1]['deployments']['not'])
