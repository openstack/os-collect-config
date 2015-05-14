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

import testtools

from os_collect_config import merger


META_DATA = {u'int1': 1,
             u'strfoo': u'foo',
             u'map_ab': {
                 u'a': 'apple',
                 u'b': 'banana',
             }}


SOFTWARE_CONFIG_DATA = {
    u'old-style': u'value',
    u'deployments': [
        {
            u'inputs': [
                {
                    u'type': u'String',
                    u'name': u'input1',
                    u'value': u'value1'
                }
            ],
            u'group': 'Heat::Ungrouped',
            u'name': 'dep-name1',
            u'outputs': None,
            u'options': None,
            u'config': {
                u'config1': 'value1'
            }
        },
        {
            u'inputs': [
                {
                    u'type': u'String',
                    u'name': u'input1',
                    u'value': u'value1'
                }
            ],
            u'group': 'os-apply-config',
            u'name': 'dep-name2',
            u'outputs': None,
            u'options': None,
            u'config': {
                u'config2': 'value2'
            }
        },
        {
            u'inputs': [
                {
                    u'type': u'String',
                    u'name': u'input1',
                    u'value': u'value1'
                }
            ],
            u'name': 'dep-name3',
            u'outputs': None,
            u'options': None,
            u'config': {
                u'config3': 'value3'
            }
        },
        {
            u'inputs': [],
            u'group': 'ignore_me',
            u'name': 'ignore_me_name',
            u'outputs': None,
            u'options': None,
            u'config': 'ignore_me_config'
        },
        {
            u'inputs': [],  # to test missing name
        }
    ]
}


class TestMerger(testtools.TestCase):

    def test_merged_list_from_content(self):
        req_md = merger.merged_list_from_content(
            SOFTWARE_CONFIG_DATA,
            ['deployments'],
            'collectme')
        self.assertEqual(4, len(req_md))
        self.assertEqual(
            SOFTWARE_CONFIG_DATA['deployments'], req_md[0][1]['deployments'])
        self.assertEqual(
            ('dep-name1', {'config1': 'value1'}), req_md[1])
        self.assertEqual(
            ('dep-name2', {'config2': 'value2'}), req_md[2])
        self.assertEqual(
            ('dep-name3', {'config3': 'value3'}), req_md[3])
