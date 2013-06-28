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
import os
from oslo.config import cfg
import testtools

from os_collect_config import collect
from os_collect_config.tests import test_ec2


class TestCollect(testtools.TestCase):
    def setUp(self):
        super(TestCollect, self).setUp()
        self.useFixture(
            fixtures.MonkeyPatch(
                'os_collect_config.ec2.h', test_ec2.FakeHttp()))

    def tearDown(self):
        super(TestCollect, self).tearDown()
        cfg.CONF.reset()

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
        ]
        self.useFixture(
            fixtures.MonkeyPatch('sys.argv', fake_args))
        self.called_fake_call = False

        def fake_call(args, env):
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
            self.assertIn("local-ipv4", keys_found)
            self.assertIn("reservation-id", keys_found)

        self.useFixture(fixtures.MonkeyPatch('subprocess.call', fake_call))

        collect.__main__()

        self.assertTrue(self.called_fake_call)


class TestConf(testtools.TestCase):
    def test_setup_conf(self):
        collect.setup_conf()
        self.assertEquals('/var/run/os-collect-config', cfg.CONF.cachedir)


class TestCache(testtools.TestCase):
    def setUp(self):
        super(TestCache, self).setUp()
        cfg.CONF.reset()

    def tearDown(self):
        cfg.CONF.reset()
        super(TestCache, self).tearDown()

    def test_cache(self):
        cache_root = self.useFixture(fixtures.TempDir())
        cache_dir = os.path.join(cache_root.path, 'cache')
        collect.setup_conf()
        cfg.CONF(['--cachedir', cache_dir])
        (changed, path) = collect.cache('foo', {'a': 1})
        self.assertTrue(changed)
        self.assertTrue(os.path.exists(cache_dir))
        self.assertTrue(os.path.exists(path))
        orig_path = '%s.orig' % path
        self.assertTrue(os.path.exists(orig_path))

        (changed, path) = collect.cache('foo', {'a': 2})
        self.assertTrue(changed)
        orig_path = '%s.orig' % path
        with open(path) as now:
            with open(orig_path) as then:
                self.assertNotEquals(now.read(), then.read())

        collect.commit_cache('foo')
        (changed, path) = collect.cache('foo', {'a': 2})
        self.assertFalse(changed)
