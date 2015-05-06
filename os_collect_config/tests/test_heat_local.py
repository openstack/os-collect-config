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
import os.path
import tempfile

import fixtures
from oslo_config import cfg
import testtools
from testtools import matchers

from os_collect_config import collect
from os_collect_config import exc
from os_collect_config import heat_local


META_DATA = {u'localstrA': u'A',
             u'localint9': 9,
             u'localmap_xy': {
                 u'x': 42,
                 u'y': 'foo',
             }}


class TestHeatLocal(testtools.TestCase):
    def setUp(self):
        super(TestHeatLocal, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        collect.setup_conf()
        self.orig_cfg_CONF = cfg.CONF

    def tearDown(self):
        cfg.CONF = self.orig_cfg_CONF
        cfg.CONF.reset()
        super(TestHeatLocal, self).tearDown()

    def _call_collect(self, *temp_name):
        cfg.CONF.heat_local.path = list(temp_name)
        md = heat_local.Collector().collect()
        self.assertEqual('heat_local', md[0][0])
        return md[0][1]

    def test_collect_heat_local(self):
        with tempfile.NamedTemporaryFile() as md:
            md.write(json.dumps(META_DATA).encode('utf-8'))
            md.flush()
            local_md = self._call_collect(md.name)

        self.assertThat(local_md, matchers.IsInstance(dict))

        for k in ('localstrA', 'localint9', 'localmap_xy'):
            self.assertIn(k, local_md)
            self.assertEqual(local_md[k], META_DATA[k])

        self.assertEqual('', self.log.output)

    def test_collect_heat_local_twice(self):
        with tempfile.NamedTemporaryFile() as md:
            md.write(json.dumps(META_DATA).encode('utf-8'))
            md.flush()
            local_md = self._call_collect(md.name, md.name)

        self.assertThat(local_md, matchers.IsInstance(dict))

        for k in ('localstrA', 'localint9', 'localmap_xy'):
            self.assertIn(k, local_md)
            self.assertEqual(local_md[k], META_DATA[k])

        self.assertEqual('', self.log.output)

    def test_collect_heat_local_with_invalid_metadata(self):
        with tempfile.NamedTemporaryFile() as md:
            md.write("{'invalid' => 'INVALID'}".encode('utf-8'))
            md.flush()
            self.assertRaises(exc.HeatLocalMetadataNotAvailable,
                              self._call_collect, md.name)
            self.assertIn('Local metadata not found', self.log.output)

    def test_collect_ec2_nofile(self):
        tdir = self.useFixture(fixtures.TempDir())
        test_path = os.path.join(tdir.path, 'does-not-exist.json')
        self.assertRaises(exc.HeatLocalMetadataNotAvailable,
                          self._call_collect, test_path)
        self.assertIn('Local metadata not found', self.log.output)
