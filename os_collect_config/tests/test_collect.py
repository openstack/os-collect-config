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
import json
import os
import signal
import sys
import tempfile
from unittest import mock

import extras
import fixtures
from oslo_config import cfg
import testtools
from testtools import matchers

from os_collect_config import cache
from os_collect_config import collect
from os_collect_config import config_drive
from os_collect_config import exc
from os_collect_config.tests import test_cfn
from os_collect_config.tests import test_ec2
from os_collect_config.tests import test_heat
from os_collect_config.tests import test_heat_local
from os_collect_config.tests import test_local
from os_collect_config.tests import test_request
from os_collect_config.tests import test_zaqar


def _setup_heat_local_metadata(test_case):
    test_case.useFixture(fixtures.NestedTempfile())
    local_md = tempfile.NamedTemporaryFile(delete=False)
    local_md.write(json.dumps(test_heat_local.META_DATA).encode('utf-8'))
    local_md.flush()
    return local_md.name


def _setup_local_metadata(test_case):
    tmpdir = fixtures.TempDir()
    test_case.useFixture(tmpdir)
    local_data_path = tmpdir.path + '/local'
    with open(local_data_path, 'w') as local_data:
        json.dump(test_local.META_DATA, local_data)
    return tmpdir.path


class TestCollect(testtools.TestCase):

    def setUp(self):
        super(TestCollect, self).setUp()
        self.useFixture(fixtures.FakeLogger())
        collect.setup_conf()
        self.addCleanup(cfg.CONF.reset)

    def _call_main(self, fake_args):
        # make sure we don't run forever!
        if '--one-time' not in fake_args:
            fake_args.append('--one-time')
        collector_kwargs_map = {
            'ec2': {'requests_impl': test_ec2.FakeRequests},
            'cfn': {'requests_impl': test_cfn.FakeRequests(self)},
            'heat': {
                'keystoneclient': test_heat.FakeKeystoneClient(self),
                'heatclient': test_heat.FakeHeatClient(self),
                'discover_class': test_heat.FakeKeystoneDiscover
            },
            'request': {'requests_impl': test_request.FakeRequests},
            'zaqar': {
                'keystoneclient': test_zaqar.FakeKeystoneClient(self),
                'zaqarclient': test_zaqar.FakeZaqarClient(self),
                'discover_class': test_heat.FakeKeystoneDiscover
            },
        }
        with mock.patch.object(config_drive, 'get_metadata') as gm:
            gm.return_value = {}
            return collect.__main__(args=fake_args,
                                    collector_kwargs_map=collector_kwargs_map)

    def _fake_popen_call_main(self, occ_args):
        calls = []

        def capture_popen(proc_args):
            calls.append(proc_args)
            return dict(returncode=0)
        self.useFixture(fixtures.FakePopen(capture_popen))
        self.assertEqual(0, self._call_main(occ_args))
        return calls

    def test_main(self):
        expected_cmd = self.getUniqueString()
        cache_dir = self.useFixture(fixtures.TempDir())
        backup_cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_heat_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--command',
            expected_cmd,
            '--cachedir',
            cache_dir.path,
            '--backup-cachedir',
            backup_cache_dir.path,
            '--config-file',
            '/dev/null',
            '--cfn-metadata-url',
            'http://192.0.2.1:8000/v1/',
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
            '--heat-user-id',
            'FEDCBA9876543210',
            '--heat-password',
            '0123456789ABCDEF',
            '--heat-project-id',
            '9f6b09df-4d7f-4a33-8ec3-9924d8f46f10',
            '--heat-auth-url',
            'http://192.0.2.1:5000/v3',
            '--heat-stack-id',
            'a/c482680f-7238-403d-8f76-36acf0c8e0aa',
            '--heat-resource-name',
            'server'
        ]
        calls = self._fake_popen_call_main(occ_args)
        # The Python 3 platform module makes a popen call, filter this out
        proc_calls = [call for call in calls if call['args'] == expected_cmd]
        self.assertEqual(len(proc_calls), 1)
        proc_args = proc_calls[0]
        for test_dir in (cache_dir, backup_cache_dir):
            list_path = os.path.join(test_dir.path, 'os_config_files.json')
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

    def test_main_just_local(self):
        fake_md = _setup_heat_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--print',
            '--local-path', os.path.dirname(fake_md),
            'local',
        ]
        self._call_main(occ_args)

    def test_main_force_command(self):
        cache_dir = self.useFixture(fixtures.TempDir())
        backup_cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_heat_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--command', 'foo',
            '--cachedir', cache_dir.path,
            '--backup-cachedir', backup_cache_dir.path,
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
        backup_cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_heat_local_metadata(self)
        occ_args = [
            'os-collect-config',
            '--command',
            'foo',
            '--cachedir',
            cache_dir.path,
            '--backup-cachedir',
            backup_cache_dir.path,
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
        self.assertEqual(1, self._call_main(occ_args))
        for test_dir in (cache_dir, backup_cache_dir):
            cache_contents = os.listdir(test_dir.path)
            last_files = [n for n in cache_contents if n.endswith('last')]
            self.assertEqual([], last_files)

    def test_main_no_command(self):
        fake_args = [
            'os-collect-config',
            '--config-file',
            '/dev/null',
            '--cfn-metadata-url',
            'http://192.0.2.1:8000/v1/',
            '--cfn-stack-name',
            'foo',
            '--cfn-path',
            'foo.Metadata',
            '--cfn-access-key-id',
            '0123456789ABCDEF',
            '--cfn-secret-access-key',
            'FEDCBA9876543210',
        ]
        fake_metadata = _setup_heat_local_metadata(self)
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
        backup_cache_dir = self.useFixture(fixtures.TempDir())
        fake_metadata = _setup_heat_local_metadata(self)
        args = [
            'os-collect-config',
            '--command', 'bar',
            '--cachedir', cache_dir.path,
            '--backup-cachedir', backup_cache_dir.path,
            '--config-file', '/dev/null',
            '--print',
            '--cfn-metadata-url',
            'http://192.0.2.1:8000/v1/',
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
            if sleep_time == 10:
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

    def test_main_min_polling_interval(self):
        class ExpectedException(Exception):
            pass

        def fake_sleep(sleep_time):
            if sleep_time == 20:
                raise ExpectedException

        self.useFixture(fixtures.MonkeyPatch('time.sleep', fake_sleep))
        self.assertRaises(ExpectedException, collect.__main__,
                          ['os-collect-config', 'heat_local', '-i', '10',
                           '--min-polling-interval', '20', '-c', 'true'])

    @mock.patch('time.sleep')
    @mock.patch('random.randrange')
    def test_main_with_splay(self, randrange_mock, sleep_mock):
        randrange_mock.return_value = 4
        collect.__main__(args=['os-collect-config', 'heat_local', '-i', '10',
                               '--min-polling-interval', '20', '-c', 'true',
                               '--print', '--splay', '29'])
        randrange_mock.assert_called_with(0, 29)
        sleep_mock.assert_called_with(4)


class TestCollectAll(testtools.TestCase):

    def setUp(self):
        super(TestCollectAll, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())
        collect.setup_conf()
        self.cache_dir = self.useFixture(fixtures.TempDir())
        self.backup_cache_dir = self.useFixture(fixtures.TempDir())
        self.clean_conf = copy.copy(cfg.CONF)

        def restore_copy():
            cfg.CONF = self.clean_conf
        self.addCleanup(restore_copy)

        cfg.CONF.cachedir = self.cache_dir.path
        cfg.CONF.backup_cachedir = self.backup_cache_dir.path
        cfg.CONF.cfn.metadata_url = 'http://192.0.2.1:8000/v1/'
        cfg.CONF.cfn.stack_name = 'foo'
        cfg.CONF.cfn.path = ['foo.Metadata']
        cfg.CONF.cfn.access_key_id = '0123456789ABCDEF'
        cfg.CONF.cfn.secret_access_key = 'FEDCBA9876543210'
        cfg.CONF.heat_local.path = [_setup_heat_local_metadata(self)]
        cfg.CONF.heat.auth_url = 'http://192.0.2.1:5000/v3'
        cfg.CONF.heat.user_id = '0123456789ABCDEF'
        cfg.CONF.heat.password = 'FEDCBA9876543210'
        cfg.CONF.heat.project_id = '9f6b09df-4d7f-4a33-8ec3-9924d8f46f10'
        cfg.CONF.heat.stack_id = 'a/c482680f-7238-403d-8f76-36acf0c8e0aa'
        cfg.CONF.heat.resource_name = 'server'
        cfg.CONF.local.path = [_setup_local_metadata(self)]
        cfg.CONF.request.metadata_url = 'http://192.0.2.1:8000/my_metadata/'
        cfg.CONF.zaqar.auth_url = 'http://192.0.2.1:5000/v3'
        cfg.CONF.zaqar.user_id = '0123456789ABCDEF'
        cfg.CONF.zaqar.password = 'FEDCBA9876543210'
        cfg.CONF.zaqar.project_id = '9f6b09df-4d7f-4a33-8ec3-9924d8f46f10'
        cfg.CONF.zaqar.queue_id = '4f3f46d3-09f1-42a7-8c13-f91a5457192c'

    def _call_collect_all(self, store, collector_kwargs_map=None,
                          collectors=None):
        if collector_kwargs_map is None:
            collector_kwargs_map = {
                'ec2': {'requests_impl': test_ec2.FakeRequests},
                'cfn': {'requests_impl': test_cfn.FakeRequests(self)},
                'heat': {
                    'keystoneclient': test_heat.FakeKeystoneClient(self),
                    'heatclient': test_heat.FakeHeatClient(self),
                    'discover_class': test_heat.FakeKeystoneDiscover
                },
                'request': {'requests_impl': test_request.FakeRequests},
                'zaqar': {
                    'keystoneclient': test_zaqar.FakeKeystoneClient(self),
                    'zaqarclient': test_zaqar.FakeZaqarClient(self),
                    'discover_class': test_heat.FakeKeystoneDiscover
                },
            }
        if collectors is None:
            collectors = cfg.CONF.collectors
        with mock.patch.object(config_drive, 'get_metadata') as gm:
            gm.return_value = {}
            return collect.collect_all(
                collectors,
                store=store,
                collector_kwargs_map=collector_kwargs_map)

    def _test_collect_all_store(self, collector_kwargs_map=None,
                                expected_changed=None):
        (changed_keys, paths) = self._call_collect_all(
            store=True, collector_kwargs_map=collector_kwargs_map)
        if expected_changed is None:
            expected_changed = set(['heat_local', 'cfn', 'ec2',
                                    'heat', 'local', 'request', 'zaqar'])
        self.assertEqual(expected_changed, changed_keys)
        self.assertThat(paths, matchers.IsInstance(list))
        for path in paths:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.exists('%s.orig' % path))

    def test_collect_all_store(self):
        self._test_collect_all_store()

    def test_collect_all_store_softwareconfig(self):
        soft_config_map = {
            'ec2': {'requests_impl': test_ec2.FakeRequests},
            'cfn': {
                'requests_impl': test_cfn.FakeRequestsSoftwareConfig(self)},
            'heat': {
                'keystoneclient': test_heat.FakeKeystoneClient(self),
                'heatclient': test_heat.FakeHeatClient(self),
                'discover_class': test_heat.FakeKeystoneDiscover
            },
            'request': {'requests_impl': test_request.FakeRequests},
            'zaqar': {
                'keystoneclient': test_zaqar.FakeKeystoneClient(self),
                'zaqarclient': test_zaqar.FakeZaqarClient(self),
                'discover_class': test_heat.FakeKeystoneDiscover
            },
        }
        expected_changed = set((
            'heat_local', 'ec2', 'cfn', 'heat', 'local', 'request',
            'dep-name1', 'dep-name2', 'dep-name3', 'zaqar'))
        self._test_collect_all_store(collector_kwargs_map=soft_config_map,
                                     expected_changed=expected_changed)

    def test_collect_all_store_alt_order(self):
        # Ensure different than default
        new_list = list(reversed(cfg.CONF.collectors))
        (changed_keys, paths) = self._call_collect_all(
            store=True, collectors=new_list)
        self.assertEqual(set(cfg.CONF.collectors), changed_keys)
        self.assertThat(paths, matchers.IsInstance(list))
        expected_paths = [
            os.path.join(self.cache_dir.path, '%s.json' % collector)
            for collector in new_list]
        self.assertEqual(expected_paths, paths)

    def test_collect_all_no_change(self):
        (changed_keys, paths) = self._call_collect_all(store=True)
        self.assertEqual(set(cfg.CONF.collectors), changed_keys)
        # Commit
        for changed in changed_keys:
            cache.commit(changed)
        (changed_keys, paths2) = self._call_collect_all(store=True)
        self.assertEqual(set(), changed_keys)
        self.assertEqual(paths, paths2)

    def test_collect_all_no_change_softwareconfig(self):
        soft_config_map = {
            'ec2': {'requests_impl': test_ec2.FakeRequests},
            'cfn': {
                'requests_impl': test_cfn.FakeRequestsSoftwareConfig(self)},
            'heat': {
                'keystoneclient': test_heat.FakeKeystoneClient(self),
                'heatclient': test_heat.FakeHeatClient(self),
                'discover_class': test_heat.FakeKeystoneDiscover
            },
            'request': {'requests_impl': test_request.FakeRequests},
            'zaqar': {
                'keystoneclient': test_zaqar.FakeKeystoneClient(self),
                'zaqarclient': test_zaqar.FakeZaqarClient(self),
                'discover_class': test_heat.FakeKeystoneDiscover
            },
        }
        (changed_keys, paths) = self._call_collect_all(
            store=True, collector_kwargs_map=soft_config_map)
        expected_changed = set(cfg.CONF.collectors)
        expected_changed.add('dep-name1')
        expected_changed.add('dep-name2')
        expected_changed.add('dep-name3')
        self.assertEqual(expected_changed, changed_keys)
        # Commit
        for changed in changed_keys:
            cache.commit(changed)

        # Replace the ec2 requests with a failing one to simulate a transient
        # network failure
        soft_config_map['ec2'] = {'requests_impl': test_ec2.FakeFailRequests}
        (changed_keys, paths2) = self._call_collect_all(
            store=True, collector_kwargs_map=soft_config_map)
        self.assertEqual(set(), changed_keys)

        # check the second collect includes cached ec2 data despite network
        # failure
        self.assertEqual(paths, paths2)

    def test_collect_all_nostore(self):
        (changed_keys, content) = self._call_collect_all(store=False)
        self.assertEqual(set(), changed_keys)
        self.assertThat(content, matchers.IsInstance(dict))
        for collector in cfg.CONF.collectors:
            self.assertIn(collector, content)
            self.assertThat(content[collector], matchers.IsInstance(dict))

    def test_collect_all_ec2_unavailable(self):
        collector_kwargs_map = {
            'ec2': {'requests_impl': test_ec2.FakeFailRequests},
            'cfn': {'requests_impl': test_cfn.FakeRequests(self)}
        }
        (changed_keys, content) = self._call_collect_all(
            store=False, collector_kwargs_map=collector_kwargs_map,
            collectors=['ec2', 'cfn'])
        self.assertEqual(set(), changed_keys)
        self.assertThat(content, matchers.IsInstance(dict))
        self.assertNotIn('ec2', content)

    def test_collect_all_cfn_unconfigured(self):
        collector_kwargs_map = {
            'cfn': {'requests_impl': test_cfn.FakeRequests(self)}
        }
        cfg.CONF.cfn.metadata_url = None
        (changed_keys, content) = self._call_collect_all(
            store=False, collector_kwargs_map=collector_kwargs_map,
            collectors=['heat_local', 'cfn'])
        self.assertIn('No metadata_url configured', self.log.output)
        self.assertNotIn('cfn', content)
        self.assertIn('heat_local', content)
        self.assertEqual(test_heat_local.META_DATA, content['heat_local'])


class TestConf(testtools.TestCase):

    def test_setup_conf(self):
        collect.setup_conf()
        self.assertEqual('/var/lib/os-collect-config', cfg.CONF.cachedir)
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
