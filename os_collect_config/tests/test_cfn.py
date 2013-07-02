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

import fixtures
import json
from oslo.config import cfg
import requests
import testtools
from testtools import matchers
import urlparse

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

    def __init__(self, testcase):
        self._test = testcase

    def Session(self):
        class FakeReqSession(object):
            def __init__(self, testcase):
                self._test = testcase

            def get(self, url, params, headers):
                url = urlparse.urlparse(url)
                self._test.assertEquals('/', url.path)
                self._test.assertEquals('application/json',
                                        headers['Content-Type'])
                # TODO(clint-fewbar) Refactor usage of requests to a factory
                self._test.assertIn('Action', params)
                self._test.assertEquals('DescribeStackResource',
                                        params['Action'])
                self._test.assertIn('LogicalResourceId', params)
                self._test.assertEquals('foo', params['LogicalResourceId'])
                return FakeResponse(json.dumps(META_DATA))
        return FakeReqSession(self._test)


class FakeFailRequests(object):
    exceptions = requests.exceptions

    class Session(object):
        def get(self, url, params, headers):
            raise requests.exceptions.HTTPError(403, 'Forbidden')


class TestCfn(testtools.TestCase):
    def setUp(self):
        super(TestCfn, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        collect.setup_conf()
        cfg.CONF.cfn.metadata_url = 'http://127.0.0.1:8000/'
        cfg.CONF.cfn.path = ['foo.Metadata']

    def test_collect_cfn(self):
        cfn_md = cfn.CollectCfn(requests_impl=FakeRequests(self)).collect()
        self.assertThat(cfn_md, matchers.IsInstance(dict))

        for k in ('int1', 'strfoo', 'map_ab'):
            self.assertIn(k, cfn_md)
            self.assertEquals(cfn_md[k], META_DATA[k])

        self.assertEquals('', self.log.output)

    def test_collect_cfn_fail(self):
        cfn_collect = cfn.CollectCfn(requests_impl=FakeFailRequests)
        self.assertRaises(exc.CfnMetadataNotAvailable, cfn_collect.collect)
        self.assertIn('Forbidden', self.log.output)

    def test_collect_cfn_no_path(self):
        cfg.CONF.cfn.path = None
        cfn_collect = cfn.CollectCfn(requests_impl=FakeRequests(self))
        self.assertRaises(exc.CfnMetadataNotConfigured, cfn_collect.collect)
        self.assertIn('No path configured', self.log.output)

    def test_collect_cfn_no_metadata_url(self):
        cfg.CONF.cfn.metadata_url = None
        cfn_collect = cfn.CollectCfn(requests_impl=FakeRequests(self))
        self.assertRaises(exc.CfnMetadataNotConfigured, cfn_collect.collect)
        self.assertIn('No metadata_url configured', self.log.output)
