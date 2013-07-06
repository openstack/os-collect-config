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

import copy
import extras
import fixtures
import json
import os
from oslo.config import cfg
import tempfile
import testtools
from testtools import matchers

from os_collect_config import collect
from os_collect_config.tests import test_cfn
from os_collect_config.tests import test_ec2
from os_collect_config.tests import test_heat_local


def _setup_local_metadata(test_case):
    test_case.useFixture(fixtures.NestedTempfile())
    local_md = tempfile.NamedTemporaryFile(delete=False)
    local_md.write(json.dumps(test_heat_local.META_DATA))
    local_md.flush()
    return local_md.name


class TestCollect(testtools.TestCase):
    def tearDown(self):
        super(TestCollect, self).tearDown()
        cfg.CONF.reset()

    def _call_main(self, fake_args):
        requests_impl_map = {'ec2': test_ec2.FakeRequests,
                             'cfn': test_cfn.FakeRequests(self)}
        collect.__main__(args=fake_args, requests_impl_map=requests_impl_map)

    def test_main(self):
        expected_cmd = self.getUniqueString()
        cache_dir = self.useFixture(fixtures.TempDir())
        fake_args = [
            'os-collect-config',
            '--command',
            expected_cmd,
            '--cachedir',
            cache_dir.path,
            '--config-file',
            '/dev/null',
            '--cfn-metadata-url',
            'http://127.0.0.1:8000/',
            '--cfn-stack-name',
            'foo',
            '--cfn-path',
            'foo.Metadata',
            '--cfn-access-key-id',
            '0123456789ABCDEF',
            '--cfn-secret-access-key',
            'FEDCBA9876543210',
        ]
        fake_metadata = _setup_local_metadata(self)
        fake_args.append('--heat_local-path')
        fake_args.append(fake_metadata)
        self.called_fake_call = False

        def fake_call(args, env, shell):
            self.called_fake_call = True
            self.assertEquals(expected_cmd, args)
            self.assertIn('OS_CONFIG_FILES', env)
            self.assertTrue(len(env.keys()) > 0)
            keys_found = set()
            for path in env['OS_CONFIG_FILES'].split(':'):
                self.assertTrue(os.path.exists(path))
                with open(path) as cfg_file:
                    contents = json.loads(cfg_file.read())
                    keys_found.update(set(contents.keys()))
            # From test_ec2.FakeRequests
            self.assertIn("local-ipv4", keys_found)
            self.assertIn("reservation-id", keys_found)
            # From test_cfn.FakeRequests
            self.assertIn("int1", keys_found)
            self.assertIn("map_ab", keys_found)

        self.useFixture(fixtures.MonkeyPatch('subprocess.call', fake_call))

        self._call_main(fake_args)

        self.assertTrue(self.called_fake_call)

    def test_main_no_command(self):
        fake_args = [
            'os-collect-config',
            '--config-file',
            '/dev/null',
            '--cfn-metadata-url',
            'http://127.0.0.1:8000/',
            '--cfn-stack-name',
            'foo',
            '--cfn-path',
            'foo.Metadata',
            '--cfn-access-key-id',
            '0123456789ABCDEF',
            '--cfn-secret-access-key',
            'FEDCBA9876543210',
        ]
        fake_metadata = _setup_local_metadata(self)
        fake_args.append('--heat_local-path')
        fake_args.append(fake_metadata)
        output = self.useFixture(fixtures.ByteStream('stdout'))
        self.useFixture(
            fixtures.MonkeyPatch('sys.stdout', output.stream))
        self._call_main(fake_args)
        out_struct = json.loads(output.stream.getvalue())
        self.assertThat(out_struct, matchers.IsInstance(dict))
        self.assertIn('ec2', out_struct)
        self.assertIn('cfn', out_struct)


class TestCollectAll(testtools.TestCase):
    def setUp(self):
        super(TestCollectAll, self).setUp()
        self.useFixture(fixtures.FakeLogger())
        collect.setup_conf()
        self.cache_dir = self.useFixture(fixtures.TempDir())
        self.clean_conf = copy.copy(cfg.CONF)

        def restore_copy():
            cfg.CONF = self.clean_conf
        self.addCleanup(restore_copy)

        cfg.CONF.cachedir = self.cache_dir.path
        cfg.CONF.cfn.metadata_url = 'http://127.0.0.1:8000/'
        cfg.CONF.cfn.stack_name = 'foo'
        cfg.CONF.cfn.path = ['foo.Metadata']
        cfg.CONF.cfn.access_key_id = '0123456789ABCDEF'
        cfg.CONF.cfn.secret_access_key = 'FEDCBA9876543210'
        cfg.CONF.heat_local.path = [_setup_local_metadata(self)]

    def _call_collect_all(
            self, store, requests_impl_map=None, collectors=None):
        if requests_impl_map is None:
            requests_impl_map = {'ec2': test_ec2.FakeRequests,
                                 'cfn': test_cfn.FakeRequests(self)}
        if collectors is None:
            collectors = cfg.CONF.collectors
        return collect.collect_all(
            collectors,
            store=store,
            requests_impl_map=requests_impl_map)

    def test_collect_all_store(self):
        (any_changed, paths) = self._call_collect_all(store=True)
        self.assertTrue(any_changed)
        self.assertThat(paths, matchers.IsInstance(list))
        for collector in cfg.CONF.collectors:
            self.assertIn(os.path.join(self.cache_dir.path, '%s.json' %
                                                            collector),
                          paths)
            self.assertTrue(any_changed)

    def test_collect_all_store_alt_order(self):
        # Ensure different than default
        new_list = list(reversed(cfg.CONF.collectors))
        (any_changed, paths) = self._call_collect_all(store=True,
                                                      collectors=new_list)
        self.assertTrue(any_changed)
        self.assertThat(paths, matchers.IsInstance(list))
        expected_paths = [
            os.path.join(self.cache_dir.path, '%s.json' % collector)
            for collector in new_list]
        self.assertEquals(expected_paths, paths)

    def test_collect_all_nostore(self):
        (any_changed, content) = self._call_collect_all(store=False)
        self.assertFalse(any_changed)
        self.assertThat(content, matchers.IsInstance(dict))
        for collector in cfg.CONF.collectors:
            self.assertIn(collector, content)
            self.assertThat(content[collector], matchers.IsInstance(dict))

    def test_collect_all_ec2_unavailable(self):
        requests_impl_map = {'ec2': test_ec2.FakeFailRequests,
                             'cfn': test_cfn.FakeRequests(self)}
        (any_changed, content) = self._call_collect_all(
            store=False, requests_impl_map=requests_impl_map)
        self.assertFalse(any_changed)
        self.assertThat(content, matchers.IsInstance(dict))
        self.assertNotIn('ec2', content)


class TestConf(testtools.TestCase):
    def test_setup_conf(self):
        collect.setup_conf()
        self.assertEquals('/var/run/os-collect-config', cfg.CONF.cachedir)
        self.assertTrue(extras.safe_hasattr(cfg.CONF, 'ec2'))
        self.assertTrue(extras.safe_hasattr(cfg.CONF, 'cfn'))
