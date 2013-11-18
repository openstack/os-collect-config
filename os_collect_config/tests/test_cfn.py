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
import urlparse

import fixtures
from lxml import etree
from oslo.config import cfg
import requests
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


class FakeResponse(dict):
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeRequests(object):
    exceptions = requests.exceptions

    def __init__(self, testcase, expected_netloc='127.0.0.1:8000'):
        self._test = testcase
        self._expected_netloc = expected_netloc

    def Session(self):
        class FakeReqSession(object):
            def __init__(self, testcase, expected_netloc):
                self._test = testcase
                self._expected_netloc = expected_netloc

            def get(self, url, params, headers):
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
                root = etree.Element('DescribeStackResourceResponse')
                result = etree.SubElement(root, 'DescribeStackResourceResult')
                detail = etree.SubElement(result, 'StackResourceDetail')
                metadata = etree.SubElement(detail, 'Metadata')
                metadata.text = json.dumps(META_DATA)
                return FakeResponse(etree.tostring(root))
        return FakeReqSession(self._test, self._expected_netloc)


class FakeFailRequests(object):
    exceptions = requests.exceptions

    class Session(object):
        def get(self, url, params, headers):
            raise requests.exceptions.HTTPError(403, 'Forbidden')


class TestCfn(testtools.TestCase):
    def setUp(self):
        super(TestCfn, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        self.useFixture(fixtures.NestedTempfile())
        self.hint_file = tempfile.NamedTemporaryFile()
        self.hint_file.write('http://127.0.0.1:8000')
        self.hint_file.flush()
        self.addCleanup(self.hint_file.close)
        collect.setup_conf()
        cfg.CONF.cfn.heat_metadata_hint = self.hint_file.name
        cfg.CONF.cfn.metadata_url = None
        cfg.CONF.cfn.path = ['foo.Metadata']
        cfg.CONF.cfn.access_key_id = '0123456789ABCDEF'
        cfg.CONF.cfn.secret_access_key = 'FEDCBA9876543210'

    def test_collect_cfn(self):
        cfn_md = cfn.Collector(requests_impl=FakeRequests(self)).collect()
        self.assertThat(cfn_md, matchers.IsInstance(dict))

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, cfn_md)
            self.assertEqual(cfn_md[k], META_DATA[k])

        self.assertEqual('', self.log.output)

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
        self.assertThat(content, matchers.IsInstance(dict))
        self.assertIn(u'b', content)
        self.assertEqual(u'banana', content[u'b'])

    def test_collect_cfn_metadata_url_overrides_hint(self):
        cfg.CONF.cfn.metadata_url = 'http://127.0.1.1:8000/v1/'
        cfn_collect = cfn.Collector(
            requests_impl=FakeRequests(self,
                                       expected_netloc='127.0.1.1:8000'))
        cfn_collect.collect()
