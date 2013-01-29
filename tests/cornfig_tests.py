from nose.tools import *
from cornfig.cornfig import *
import os

TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')
TEMPLATE_PATHS = ["/etc/keystone/keystone.conf"]

def setup():
  pass

def teardown():
  pass

def test_template_paths():
  expected = map(lambda p: (os.path.join(TEMPLATES, p[1:]), p), TEMPLATE_PATHS)
  assert template_paths(TEMPLATES) == expected

@raises(Exception)
def test_read_config_bad_json():
  with tempfile.TemporaryFile() as t:
    t.write("{{{{")
    read_config(t.path)

@raises(Exception)
def test_read_config_no_file():
  read_config("/nosuchfile")
