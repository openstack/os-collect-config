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
import tempfile

import fixtures
import testtools

from os_apply_config import config_exception
from os_apply_config import os_apply_config as oca

# example template tree
TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')
TEMPLATE_PATHS = [
    "/etc/glance/script.conf",
    "/etc/keystone/keystone.conf"
]

# config for example tree
CONFIG = {
    "x": "foo",
    "database": {
    "url": "sqlite:///blah"
    }
}

# config for example tree - with subhash
CONFIG_SUBHASH = {
    "OpenStack::Config": {
    "x": "foo",
    "database": {
        "url": "sqlite:///blah"
    }
    }
}

# expected output for example tree
OUTPUT = {
    "/etc/glance/script.conf": "foo\n",
    "/etc/keystone/keystone.conf": "[foo]\ndatabase = sqlite:///blah\n"
}


def main_path():
    return (
        os.path.dirname(os.path.realpath(__file__)) +
        '/../os_apply_config.py')


def template(relpath):
    return os.path.join(TEMPLATES, relpath[1:])


class TestRunOSConfigApplier(testtools.TestCase):

    def setUp(self):
        super(TestRunOSConfigApplier, self).setUp()
        self.useFixture(fixtures.NestedTempfile())
        self.stdout = self.useFixture(fixtures.StringStream('stdout')).stream
        self.useFixture(fixtures.MonkeyPatch('sys.stdout', self.stdout))
        stderr = self.useFixture(fixtures.StringStream('stderr')).stream
        self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))
        self.logger = self.useFixture(
            fixtures.FakeLogger(name="os-apply-config"))
        fd, self.path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG))
            t.flush()

    def test_print_key(self):
        self.assertEqual(0, oca.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'database.url', '--type', 'raw']))
        self.stdout.seek(0)
        self.assertEqual(CONFIG['database']['url'],
                         self.stdout.read().strip())
        self.assertEqual('', self.logger.output)

    def test_print_key_missing(self):
        self.assertEqual(1, oca.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'does.not.exist']))
        self.assertIn('does not exist', self.logger.output)

    def test_print_key_missing_default(self):
        self.assertEqual(0, oca.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'does.not.exist', '--key-default', '']))
        self.stdout.seek(0)
        self.assertEqual('', self.stdout.read().strip())
        self.assertEqual('', self.logger.output)

    def test_print_key_wrong_type(self):
        self.assertEqual(1, oca.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'x', '--type', 'int']))
        self.assertIn('cannot interpret value', self.logger.output)

    def test_print_templates(self):
        oca.main(['os-apply-config', '--print-templates'])
        self.stdout.seek(0)
        self.assertEqual(self.stdout.read().strip(), oca.TEMPLATES_DIR)
        self.assertEqual('', self.logger.output)


class OSConfigApplierTestCase(testtools.TestCase):

    def setUp(self):
        super(OSConfigApplierTestCase, self).setUp()
        self.useFixture(fixtures.FakeLogger('os-apply-config'))
        self.useFixture(fixtures.NestedTempfile())

    def test_install_config(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG))
            t.flush()
        tmpdir = tempfile.mkdtemp()
        oca.install_config([path], TEMPLATES, tmpdir, False)
        for path, contents in OUTPUT.items():
            full_path = os.path.join(tmpdir, path[1:])
            assert os.path.exists(full_path)
            self.assertEqual(open(full_path).read(), contents)

    def test_install_config_subhash(self):
        fd, tpath = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG_SUBHASH))
            t.flush()
        tmpdir = tempfile.mkdtemp()
        oca.install_config(
            [tpath], TEMPLATES, tmpdir, False, 'OpenStack::Config')
        for path, contents in OUTPUT.items():
            full_path = os.path.join(tmpdir, path[1:])
            assert os.path.exists(full_path)
            self.assertEqual(open(full_path).read(), contents)

    def test_build_tree(self):
        self.assertEqual(oca.build_tree(
            oca.template_paths(TEMPLATES), CONFIG), OUTPUT)

    def test_render_template(self):
        # execute executable files, moustache non-executables
        self.assertEqual(oca.render_template(template(
            "/etc/glance/script.conf"), {"x": "abc"}), "abc\n")
        self.assertRaises(
            config_exception.ConfigException, oca.render_template, template(
                "/etc/glance/script.conf"), {})

    def test_render_moustache(self):
        self.assertEqual(oca.render_moustache("ab{{x.a}}cd", {
                         "x": {"a": "123"}}), "ab123cd")

    def test_render_moustache_bad_key(self):
        self.assertEqual(oca.render_moustache("{{badkey}}", {}), u'')

    def test_render_executable(self):
        params = {"x": "foo"}
        self.assertEqual(oca.render_executable(template(
            "/etc/glance/script.conf"), params), "foo\n")

    def test_render_executable_failure(self):
        self.assertRaises(
            config_exception.ConfigException,
            oca.render_executable, template("/etc/glance/script.conf"), {})

    def test_template_paths(self):
        expected = map(lambda p: (template(p), p), TEMPLATE_PATHS)
        actual = oca.template_paths(TEMPLATES)
        expected.sort(key=lambda tup: tup[1])
        actual.sort(key=lambda tup: tup[1])
        self.assertEqual(actual, expected)

    def test_read_config(self):
        with tempfile.NamedTemporaryFile() as t:
            d = {"a": {"b": ["c", "d"]}}
            t.write(json.dumps(d))
            t.flush()
            self.assertEqual(oca.read_config([t.name]), d)

    def test_read_config_bad_json(self):
        with tempfile.NamedTemporaryFile() as t:
            t.write("{{{{")
            t.flush()
            self.assertRaises(config_exception.ConfigException,
                              oca.read_config, [t.name])

    def test_read_config_no_file(self):
        self.assertRaises(config_exception.ConfigException,
                          oca.read_config, ["/nosuchfile"])

    def test_read_config_multi(self):
        with tempfile.NamedTemporaryFile(mode='wb') as t1:
            with tempfile.NamedTemporaryFile(mode='wb') as t2:
                d1 = {"a": {"b": [1, 2]}}
                d2 = {"x": {"y": [8, 9]}}
                t1.write(json.dumps(d1))
                t1.flush()
                t2.write(json.dumps(d2))
                t2.flush()
                result = oca.read_config([t1.name, t2.name])
                self.assertEqual(d1, result)

    def test_read_config_multi_missing1(self):
        with tempfile.NamedTemporaryFile(mode='wb') as t1:
            pass
        with tempfile.NamedTemporaryFile(mode='wb') as t2:
            d2 = {"x": {"y": [8, 9]}}
            t2.write(json.dumps(d2))
            t2.flush()
            result = oca.read_config([t1.name, t2.name])
            self.assertEqual(d2, result)

    def test_read_config_multi_missing_bad1(self):
        with tempfile.NamedTemporaryFile(mode='wb') as t1:
            t1.write('{{{')
            t1.flush()
            with tempfile.NamedTemporaryFile(mode='wb') as t2:
                pass
                d2 = {"x": {"y": [8, 9]}}
                t2.write(json.dumps(d2))
                t2.flush()
                self.assertRaises(config_exception.ConfigException,
                                  oca.read_config, [t1.name, t2.name])

    def test_read_config_multi_missing_all(self):
        with tempfile.NamedTemporaryFile(mode='wb') as t1:
            pass
        with tempfile.NamedTemporaryFile(mode='wb') as t2:
            pass
        self.assertRaises(config_exception.ConfigException,
                          oca.read_config, [t1.name, t2.name])

    def test_strip_hash(self):
        h = {'a': {'b': {'x': 'y'}}, "c": [1, 2, 3]}
        self.assertEqual(oca.strip_hash(h, 'a.b'), {'x': 'y'})
        self.assertRaises(config_exception.ConfigException,
                          oca.strip_hash, h, 'a.nonexistent')
        self.assertRaises(config_exception.ConfigException,
                          oca.strip_hash, h, 'a.c')
