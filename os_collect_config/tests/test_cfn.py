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


class FakeSession(object):
    def get(self, url):
        url = urlparse.urlparse(url)
        params = urlparse.parse_qsl(url.query)
        # TODO(clint-fewbar) Refactor usage of requests to a factory
        if 'Action' not in params:
            raise Exception('No Action')
        if params['Action'] != 'DescribeStackResources':
            raise Exception('Wrong Action (%s)' % params['Action'])
        return FakeResponse(json.dumps(META_DATA))


class FakeFailSession(object):
    def get(self, url):
        raise requests.exceptions.HTTPError(403, 'Forbidden')


class TestCfn(testtools.TestCase):
    def setUp(self):
        super(TestCfn, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())

    def test_collect_cfn(self):
        self.useFixture(
            fixtures.MonkeyPatch('requests.Session', FakeSession))
        collect.setup_conf()
        cfn_md = cfn.collect()
        self.assertThat(cfn_md, matchers.IsInstance(dict))

        for k in ('int1', 'strfoo', 'mapab'):
            self.assertIn(k, cfn_md)
            self.assertEquals(cfn_md[k], META_DATA[k])

        self.assertEquals(cfn_md['block-device-mapping']['ami'], 'vda')

        self.assertEquals('', self.log.output)

    def test_collect_cfn_fail(self):
        self.useFixture(
            fixtures.MonkeyPatch(
                'requests.Session', FakeFailSession))
        collect.setup_conf()
        self.assertRaises(exc.CfnMetadataNotAvailable, cfn.collect)
        self.assertIn('Forbidden', self.log.output)
