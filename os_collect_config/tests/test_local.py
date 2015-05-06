# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
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
import locale
import os
import tempfile

import fixtures
from oslo_config import cfg
import testtools
from testtools import matchers

from os_collect_config import collect
from os_collect_config import exc
from os_collect_config import local


META_DATA = {u'localstrA': u'A',
             u'localint9': 9,
             u'localmap_xy': {
                 u'x': 42,
                 u'y': 'foo',
             }}
META_DATA2 = {u'localstrA': u'Z',
              u'localint9': 9}


class TestLocal(testtools.TestCase):
    def setUp(self):
        super(TestLocal, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        self.useFixture(fixtures.NestedTempfile())
        self.tdir = tempfile.mkdtemp()
        collect.setup_conf()
        self.addCleanup(cfg.CONF.reset)
        cfg.CONF.register_cli_opts(local.opts, group='local')
        cfg.CONF.set_override(name='path',
                              override=[self.tdir],
                              group='local')

    def _call_collect(self):
        md = local.Collector().collect()
        return md

    def _setup_test_json(self, data, md_base='test.json'):
        md_name = os.path.join(self.tdir, md_base)
        with open(md_name, 'w') as md:
            md.write(json.dumps(data))
        return md_name

    def test_collect_local(self):
        self._setup_test_json(META_DATA)
        local_md = self._call_collect()

        self.assertThat(local_md, matchers.IsInstance(list))
        self.assertEqual(1, len(local_md))
        self.assertThat(local_md[0], matchers.IsInstance(tuple))
        self.assertEqual(2, len(local_md[0]))
        self.assertEqual('test.json', local_md[0][0])

        only_md = local_md[0][1]
        self.assertThat(only_md, matchers.IsInstance(dict))

        for k in ('localstrA', 'localint9', 'localmap_xy'):
            self.assertIn(k, only_md)
            self.assertEqual(only_md[k], META_DATA[k])

        self.assertEqual('', self.log.output)

    def test_collect_local_world_writable(self):
        md_name = self._setup_test_json(META_DATA)
        os.chmod(md_name, 0o666)
        self.assertRaises(exc.LocalMetadataNotAvailable, self._call_collect)
        self.assertIn('%s is world writable. This is a security risk.' %
                      md_name, self.log.output)

    def test_collect_local_world_writable_dir(self):
        self._setup_test_json(META_DATA)
        os.chmod(self.tdir, 0o666)
        self.assertRaises(exc.LocalMetadataNotAvailable, self._call_collect)
        self.assertIn('%s is world writable. This is a security risk.' %
                      self.tdir, self.log.output)

    def test_collect_local_owner_not_uid(self):
        self._setup_test_json(META_DATA)
        real_getuid = os.getuid

        def fake_getuid():
            return real_getuid() + 1
        self.useFixture(fixtures.MonkeyPatch('os.getuid', fake_getuid))
        self.assertRaises(exc.LocalMetadataNotAvailable, self._call_collect)
        self.assertIn('%s is owned by another user. This is a security risk.' %
                      self.tdir, self.log.output)

    def test_collect_local_orders_multiple(self):
        self._setup_test_json(META_DATA, '00test.json')
        self._setup_test_json(META_DATA2, '99test.json')

        # Monkey Patch os.listdir so it _always_ returns the wrong sort
        unpatched_listdir = os.listdir

        def wrong_sort_listdir(path):
            ret = unpatched_listdir(path)
            save_locale = locale.getdefaultlocale()
            locale.setlocale(locale.LC_ALL, 'C')
            bad_sort = sorted(ret, reverse=True)
            locale.setlocale(locale.LC_ALL, save_locale)
            return bad_sort
        self.useFixture(fixtures.MonkeyPatch('os.listdir', wrong_sort_listdir))
        local_md = self._call_collect()

        self.assertThat(local_md, matchers.IsInstance(list))
        self.assertEqual(2, len(local_md))
        self.assertThat(local_md[0], matchers.IsInstance(tuple))

        self.assertEqual('00test.json', local_md[0][0])
        md1 = local_md[0][1]
        self.assertEqual(META_DATA, md1)

        self.assertEqual('99test.json', local_md[1][0])
        md2 = local_md[1][1]
        self.assertEqual(META_DATA2, md2)

    def test_collect_invalid_json_fail(self):
        self._setup_test_json(META_DATA)
        with open(os.path.join(self.tdir, 'bad.json'), 'w') as badjson:
            badjson.write('{')
        self.assertRaises(exc.LocalMetadataNotAvailable, self._call_collect)
        self.assertIn('is not valid JSON', self.log.output)

    def test_collect_local_path_nonexist(self):
        cfg.CONF.set_override(name='path',
                              override=['/this/doesnt/exist'],
                              group='local')
        local_md = self._call_collect()
        self.assertThat(local_md, matchers.IsInstance(list))
        self.assertEqual(0, len(local_md))
