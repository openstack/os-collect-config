import json

from nose.tools import assert_equals
from os_config_applier.renderers import JsonRenderer

TEST_JSON = '{"a":{"b":[1,2,3,"foo"],"c": "the quick brown fox"}}'


def test_json_renderer():
    context = json.loads(TEST_JSON)
    x = JsonRenderer()
    result = x.render('{{a.b}}', context)
    print result
    result_structure = json.loads(result)
    desire_structure = json.loads('[1,2,3,"foo"]')
    assert_equals(desire_structure, result_structure)
    result = x.render('{{a.c}}', context)
    print result
    assert_equals(u'the quick brown fox', result)
