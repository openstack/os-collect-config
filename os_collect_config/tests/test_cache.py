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
import os

import fixtures
import testtools
from testtools import matchers

from os_collect_config import cache


class DummyConf(object):
    def __init__(self, cachedir):
        class CONFobj(object):
            def __init__(self, cachedir):
                self.cachedir = cachedir
        self.CONF = CONFobj(cachedir)


class TestCache(testtools.TestCase):
    def setUp(self):
        super(TestCache, self).setUp()
        cache_root = self.useFixture(fixtures.TempDir())
        self.cache_dir = os.path.join(cache_root.path, 'cache')
        self.useFixture(fixtures.MonkeyPatch('os_collect_config.cache.cfg',
                                             DummyConf(self.cache_dir)))

    def tearDown(self):
        super(TestCache, self).tearDown()

    def test_cache(self):
        # Never seen, so changed is expected.
        (changed, path) = cache.store('foo', {'a': 1})
        self.assertTrue(changed)
        self.assertTrue(os.path.exists(self.cache_dir))
        self.assertTrue(os.path.exists(path))
        orig_path = '%s.orig' % path
        self.assertTrue(os.path.exists(orig_path))
        last_path = '%s.last' % path
        self.assertFalse(os.path.exists(last_path))

        # .orig exists now but not .last so this will shortcut to changed
        (changed, path) = cache.store('foo', {'a': 2})
        self.assertTrue(changed)
        orig_path = '%s.orig' % path
        with open(path) as now:
            with open(orig_path) as then:
                self.assertNotEqual(now.read(), then.read())

        # Saves the current copy as .last
        cache.commit('foo')
        last_path = '%s.last' % path
        self.assertTrue(os.path.exists(last_path))

        # We committed this already, so we should have no changes
        (changed, path) = cache.store('foo', {'a': 2})
        self.assertFalse(changed)

        cache.commit('foo')
        # Fully exercising the line-by-line matching now that a .last exists
        (changed, path) = cache.store('foo', {'a': 3})
        self.assertTrue(changed)
        self.assertTrue(os.path.exists(path))

        # And the meta list
        list_path = cache.store_meta_list('foo_list', ['foo'])
        self.assertTrue(os.path.exists(list_path))
        with open(list_path) as list_file:
            list_list = json.loads(list_file.read())
        self.assertThat(list_list, matchers.IsInstance(list))
        self.assertIn(path, list_list)

    def test_cache_ignores_json_inequality(self):
        content1 = u'{"a": "value-a", "b": "value-b"}'
        content2 = u'{"b": "value-b", "a": "value-a"}'
        value1 = json.loads(content1)
        value2 = json.loads(content2)
        self.assertEqual(value1, value2)
        (changed, path) = cache.store('content', value1)
        self.assertTrue(changed)
        cache.commit('content')
        (changed, path) = cache.store('content', value1)
        self.assertFalse(changed)
        (changed, path) = cache.store('content', value2)
        self.assertFalse(changed)

    def test_commit_no_cache(self):
        self.assertIsNone(cache.commit('neversaved'))
