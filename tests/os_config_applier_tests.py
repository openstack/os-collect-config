import json
import os
import subprocess
import tempfile
from StringIO import StringIO
from nose.tools import *
from os_config_applier.config_exception import *
from os_config_applier.os_config_applier import *

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

# expected output for example tree
OUTPUT = {
  "/etc/glance/script.conf": "foo\n",
  "/etc/keystone/keystone.conf": "[foo]\ndatabase = sqlite:///blah\n"
}

def setup():
  pass

def teardown():
  pass

def main_path():
  return os.path.dirname(os.path.realpath(__file__)) + '/../os_config_applier/os_config_applier.py'

def template(relpath):
  return os.path.join(TEMPLATES, relpath[1:])

def test_install_config():
  t = tempfile.NamedTemporaryFile()
  t.write(json.dumps(CONFIG))
  t.flush()
  tmpdir = tempfile.mkdtemp()
  install_config(t.name, TEMPLATES, tmpdir, False)
  for path, contents in OUTPUT.items():
    full_path = os.path.join(tmpdir, path[1:])
    assert os.path.exists(full_path)
    assert_equal( open(full_path).read(), contents )

def test_print_key():
  t = tempfile.NamedTemporaryFile()
  t.write(json.dumps(CONFIG))
  t.flush()
  out = subprocess.check_output([main_path(), '--metadata', t.name, '--key', 'database.url', '--type', 'raw'])
  assert_equals(CONFIG['database']['url'], out.rstrip())

@raises(subprocess.CalledProcessError)
def test_print_key_missing():
  t = tempfile.NamedTemporaryFile()
  t.write(json.dumps(CONFIG))
  t.flush()
  out = subprocess.check_output([main_path(), '--metadata', t.name, '--key', 'does.not.exist'])

@raises(subprocess.CalledProcessError)
def test_print_key_wrong_type():
  t = tempfile.NamedTemporaryFile()
  t.write(json.dumps(CONFIG))
  t.flush()
  out = subprocess.check_output([main_path(), '--metadata', t.name, '--key', 'x', '--type', 'int'])


def test_build_tree():
  assert_equals( build_tree(template_paths(TEMPLATES), CONFIG), OUTPUT )

def test_render_template():
  # execute executable files, moustache non-executables
  assert render_template(template("/etc/glance/script.conf"), {"x": "abc"}) == "abc\n"
  assert_raises(ConfigException, render_template, template("/etc/glance/script.conf"), {})

def test_render_moustache():
  assert_equals( render_moustache("ab{{x.a}}cd", {"x": {"a": "123"}}), "ab123cd" )

@raises(Exception)
def test_render_moustache_bad_key():
  render_moustache("{{badkey}}", {})

def test_render_executable():
  params = {"x": "foo"}
  assert render_executable(template("/etc/glance/script.conf"), params) == "foo\n"

@raises(ConfigException)
def test_render_executable_failure():
  render_executable(template("/etc/glance/script.conf"), {})

def test_template_paths():
  expected = map(lambda p: (template(p), p), TEMPLATE_PATHS)
  actual = template_paths(TEMPLATES)
  expected.sort(key=lambda tup: tup[1])
  actual.sort(key=lambda tup: tup[1])
  assert_equals( actual , expected)

def test_read_config():
  with tempfile.NamedTemporaryFile() as t:
    d = {"a": {"b": ["c", "d"] } }
    t.write(json.dumps(d))
    t.flush()
    assert_equals( read_config(t.name), d )

@raises(ConfigException)
def test_read_config_bad_json():
  with tempfile.NamedTemporaryFile() as t:
    t.write("{{{{")
    t.flush()
    read_config(t.name)

@raises(Exception)
def test_read_config_no_file():
  read_config("/nosuchfile")

def test_strip_hash():
  h = {'a': {'b': {'x': 'y'} }, "c": [1, 2, 3] }
  assert_equals( strip_hash(h, 'a.b'), {'x': 'y'})
  assert_raises(ConfigException, strip_hash, h, 'a.nonexistent')
  assert_raises(ConfigException, strip_hash, h, 'a.c')

def test_print_templates():
    save_stdout = sys.stdout
    output = StringIO()
    sys.stdout = output
    main(['os-config-applier', '--print-templates'])
    sys.stdout = save_stdout
    assert_equals(output.getvalue().strip(), TEMPLATES_DIR)
