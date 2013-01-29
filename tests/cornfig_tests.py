import json
import os
import tempfile
from nose.tools import *
from cornfig.cornfig import *

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

def template(relpath):
  return os.path.join(TEMPLATES, relpath[1:])


def test_install_cornfig():
  t = tempfile.NamedTemporaryFile()
  t.write(json.dumps(CONFIG))
  t.flush()
  tmpdir = tempfile.mkdtemp()
  install_cornfig(t.name, TEMPLATES, output_path=tmpdir)
  for path, contents in OUTPUT.items():
    full_path = os.path.join(tmpdir, path[1:])
    assert os.path.exists(full_path)
    assert_equal( open(full_path).read(), contents )

def test_build_tree():
  assert_equals( build_tree(template_paths(TEMPLATES), CONFIG), OUTPUT )

def test_flatten():
  assert_equals( flatten({"x": {"a": "b", "c": "d"}, "y": "z"}), {"x.a": "b", "x.c": "d", "y": "z"} )

def test_render_template():
  # execute executable files, moustache non-executables
  assert render_template(template("/etc/glance/script.conf"), {"x": "abc"}) == "abc\n"
  assert_raises(CornfigException, render_template, template("/etc/glance/script.conf"), {})

def test_render_moustache():
  assert_equals( render_moustache("ab{{x.a}}cd", {"x": {"a": "123"}}), "ab123cd" )

@raises(KeyNotFoundError)
def test_render_moustache_bad_key():
  render_moustache("{{badkey}}", {})

def test_render_executable():
  params = {"x": "foo"}
  assert render_executable(template("/etc/glance/script.conf"), params) == "foo\n"

@raises(CornfigException)
def test_render_executable_failure():
  render_executable(template("/etc/glance/script.conf"), {})

def test_template_paths():
  expected = map(lambda p: (template(p), p), TEMPLATE_PATHS)
  assert_equals( template_paths(TEMPLATES), expected)

def test_read_config():
  with tempfile.NamedTemporaryFile() as t:
    d = {"a": {"b": ["c", "d"] } }
    t.write(json.dumps(d))
    t.flush()
    assert_equals( read_config(t.name), d )

@raises(ValueError)
def test_read_config_bad_json():
  with tempfile.NamedTemporaryFile() as t:
    t.write("{{{{")
    t.flush()
    read_config(t.name)

@raises(Exception)
def test_read_config_no_file():
  read_config("/nosuchfile")
