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

import testtools
from testtools import content

from os_apply_config import renderers

TEST_JSON = '{"a":{"b":[1,2,3,"foo"],"c": "the quick brown fox"}}'


class JsonRendererTestCase(testtools.TestCase):

    def test_json_renderer(self):
        context = json.loads(TEST_JSON)
        x = renderers.JsonRenderer()
        result = x.render('{{a.b}}', context)
        self.addDetail('result', content.text_content(result))
        result_structure = json.loads(result)
        desire_structure = json.loads('[1,2,3,"foo"]')
        self.assertEqual(desire_structure, result_structure)
        result = x.render('{{a.c}}', context)
        self.addDetail('result', content.text_content(result))
        self.assertEqual(u'the quick brown fox', result)
