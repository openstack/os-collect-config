from nose.tools import *
from os_config_applier.os_config_applier import *
from os_config_applier.config_exception import *
from os_config_applier.value_types import *

@raises(ValueError)
def test_unknown_type():
  ensure_type("foo", "badtype")

def test_int():
  assert_equals("123", ensure_type("123", "int"))

def test_defualt():
  assert_equals("foobar", ensure_type("foobar", "default"))

@raises(ConfigException)
def test_default_bad():
  ensure_type("foo\nbar", "default")
