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
import signal
import sys
import tempfile

from oslo.config import cfg
import testtools
from testtools import matchers

from os_collect_config import collect
from os_collect_config import exc
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

    def setUp(self):
        super(TestCollect, self).setUp()
        self.useFixture(fixtures.FakeLogger())
        self.addCleanup(cfg.CONF.reset)

    def _call_main(self, fake_args):
        # make sure we don't run forever!
        if '--one-time' not in fake_args:
            fake_args.append('--one-time')
        requests_impl_map = {'ec2': test_ec2.FakeRequests,
                             'cfn': test_cfn.FakeRequests(self)}
        collect.__main__(args=fake_args, requests_impl_map=requests_impl_map)

    def _fake_popen_call_main(self, occ_args):
        calls = []

        def capture_popen(proc_args):
            calls.append(proc_args)
            return dict(returncode=0)
        self.useFixture(fixtures.FakePopen(capture_popen))
        self._call_main(occ_args)
        return calls

    def test_main(self):
        expected_cmd = self.getUniqueString()
        cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--command',
            expected_cmd,
            '--cachedir',
            cache_dir.path,
            '--config-file',
            '/dev/null',
            '--cfn-metadata-url',
            'http://127.0.0.1:8000/v1/',
            '--cfn-stack-name',
            'foo',
            '--cfn-path',
            'foo.Metadata',
            '--cfn-access-key-id',
            '0123456789ABCDEF',
            '--cfn-secret-access-key',
            'FEDCBA9876543210',
            '--heat_local-path',
            fake_metadata,
        ]
        calls = self._fake_popen_call_main(occ_args)
        proc_args = calls[0]
        self.assertEqual(expected_cmd, proc_args['args'])
        list_path = os.path.join(cache_dir.path, 'os_config_files.json')
        with open(list_path) as list_file:
            config_list = json.loads(list_file.read())
        self.assertThat(config_list, matchers.IsInstance(list))
        env_config_list = proc_args['env']['OS_CONFIG_FILES'].split(':')
        self.assertEqual(env_config_list, config_list)
        keys_found = set()
        for path in env_config_list:
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

    def test_main_force_command(self):
        cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--command', 'foo',
            '--cachedir', cache_dir.path,
            '--config-file', '/dev/null',
            '--heat_local-path', fake_metadata,
            '--force',
        ]
        calls = self._fake_popen_call_main(occ_args)
        self.assertIn('OS_CONFIG_FILES', calls[0]['env'])
        cfg.CONF.reset()
        # First time caches data, run again, make sure we run command again
        calls = self._fake_popen_call_main(occ_args)
        self.assertIn('OS_CONFIG_FILES', calls[0]['env'])

    def test_main_command_failed_no_caching(self):
        cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--command',
            'foo',
            '--cachedir',
            cache_dir.path,
            '--config-file',
            '/dev/null',
            '--heat_local-path',
            fake_metadata,
        ]
        calls = []

        def capture_popen(proc_args):
            calls.append(proc_args)
            return dict(returncode=1)
        self.useFixture(fixtures.FakePopen(capture_popen))
        self._call_main(occ_args)
        cache_contents = os.listdir(cache_dir.path)
        last_files = [name for name in cache_contents if name.endswith('last')]
        self.assertEqual([], last_files)

    def test_main_no_command(self):
        fake_args = [
            'os-collect-config',
            '--config-file',
            '/dev/null',
            '--cfn-metadata-url',
            'http://127.0.0.1:8000/v1/',
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
        output = self.useFixture(fixtures.StringStream('stdout'))
        self.useFixture(
            fixtures.MonkeyPatch('sys.stdout', output.stream))
        self._call_main(fake_args)
        out_struct = json.loads(output.getDetails()['stdout'].as_text())
        self.assertThat(out_struct, matchers.IsInstance(dict))
        self.assertIn('ec2', out_struct)
        self.assertIn('cfn', out_struct)

    def test_main_print_cachedir(self):
        fake_cachedir = self.useFixture(fixtures.TempDir())
        fake_args = [
            'os-collect-config',
            '--cachedir', fake_cachedir.path,
            '--config-file', '/dev/null',
            '--print-cachedir',
        ]

        output = self.useFixture(fixtures.StringStream('stdout'))
        self.useFixture(
            fixtures.MonkeyPatch('sys.stdout', output.stream))
        self._call_main(fake_args)
        cache_dir = output.getDetails()['stdout'].as_text().strip()
        self.assertEqual(fake_cachedir.path, cache_dir)

    def test_main_print_only(self):
        cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_local_metadata(self)
        args = [
            'os-collect-config',
            '--command', 'bar',
            '--cachedir', cache_dir.path,
            '--config-file', '/dev/null',
            '--print',
            '--cfn-metadata-url',
            'http://127.0.0.1:8000/v1/',
            '--cfn-stack-name',
            'foo',
            '--cfn-path',
            'foo.Metadata',
            '--cfn-access-key-id',
            '0123456789ABCDEF',
            '--cfn-secret-access-key',
            'FEDCBA9876543210',
            '--heat_local-path', fake_metadata,
        ]

        def fake_popen(args):
            self.fail('Called command instead of printing')
        self.useFixture(fixtures.FakePopen(fake_popen))
        output = self.useFixture(fixtures.StringStream('stdout'))
        self.useFixture(
            fixtures.MonkeyPatch('sys.stdout', output.stream))
        self._call_main(args)
        out_struct = json.loads(output.getDetails()['stdout'].as_text())
        self.assertThat(out_struct, matchers.IsInstance(dict))
        self.assertIn('cfn', out_struct)
        self.assertIn('heat_local', out_struct)
        self.assertIn('ec2', out_struct)

    def test_main_invalid_collector(self):
        fake_args = ['os-collect-config', 'invalid']
        self.assertRaises(exc.InvalidArguments, self._call_main, fake_args)

    def test_main_sleep(self):
        class ExpectedException(Exception):
            pass

        def fake_sleep(sleep_time):
            self.assertEqual(10, sleep_time)
            raise ExpectedException

        self.useFixture(fixtures.MonkeyPatch('time.sleep', fake_sleep))
        try:
            collect.__main__(['os-collect-config', 'heat_local', '-i', '10',
                              '-c', 'true'])
        except ExpectedException:
            pass

    def test_main_no_sleep_with_no_command(self):
        def fake_sleep(sleep_time):
            raise Exception(cfg.CONF.command)

        self.useFixture(fixtures.MonkeyPatch('time.sleep', fake_sleep))
        collect.__main__(['os-collect-config', 'heat_local', '--config-file',
                          '/dev/null', '-i', '10'])


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
        cfg.CONF.cfn.metadata_url = 'http://127.0.0.1:8000/v1/'
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
        self.assertEqual(expected_paths, paths)

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
        self.assertEqual('/var/run/os-collect-config', cfg.CONF.cachedir)
        self.assertTrue(extras.safe_hasattr(cfg.CONF, 'ec2'))
        self.assertTrue(extras.safe_hasattr(cfg.CONF, 'cfn'))


class TestHup(testtools.TestCase):

    def setUp(self):
        super(TestHup, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())

        def fake_closerange(low, high):
            self.assertEqual(3, low)
            self.assertEqual(255, high)

        def fake_execv(path, args):
            self.assertEqual(sys.argv[0], path)
            self.assertEqual(sys.argv, args)

        self.useFixture(fixtures.MonkeyPatch('os.execv', fake_execv))
        self.useFixture(fixtures.MonkeyPatch('os.closerange', fake_closerange))

    def test_reexec_self_signal(self):
        collect.reexec_self(signal.SIGHUP, None)
        self.assertIn('Signal received', self.log.output)

    def test_reexec_self(self):
        collect.reexec_self()
        self.assertNotIn('Signal received', self.log.output)


class TestFileHash(testtools.TestCase):
    def setUp(self):
        super(TestFileHash, self).setUp()

        # Deletes tempfiles during teardown
        self.useFixture(fixtures.NestedTempfile())

        self.file_1 = tempfile.mkstemp()[1]
        with open(self.file_1, "w") as fp:
            fp.write("test string")

        self.file_2 = tempfile.mkstemp()[1]
        with open(self.file_2, "w") as fp:
            fp.write("test string2")

    def test_getfilehash_nofile(self):
        h = collect.getfilehash([])
        self.assertEqual(h, "d41d8cd98f00b204e9800998ecf8427e")

    def test_getfilehash_onefile(self):
        h = collect.getfilehash([self.file_1])
        self.assertEqual(h, "6f8db599de986fab7a21625b7916589c")

    def test_getfilehash_twofiles(self):
        h = collect.getfilehash([self.file_1, self.file_2])
        self.assertEqual(h, "a8e1b2b743037b1ec17b5d4b49369872")

    def test_getfilehash_filenotfound(self):
        self.assertEqual(
            collect.getfilehash([self.file_1, self.file_2]),
            collect.getfilehash([self.file_1, "/i/dont/exist", self.file_2])
        )
