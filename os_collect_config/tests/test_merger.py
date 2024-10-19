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


META_DATA = {'int1': 1,
             'strfoo': 'foo',
             'map_ab': {
                 'a': 'apple',
                 'b': 'banana',
             }}


SOFTWARE_CONFIG_DATA = {
    'old-style': 'value',
    'deployments': [
        {
            'inputs': [
                {
                    'type': 'String',
                    'name': 'input1',
                    'value': 'value1'
                }
            ],
            'group': 'Heat::Ungrouped',
            'name': 'dep-name1',
            'outputs': None,
            'options': None,
            'config': {
                'config1': 'value1'
            }
        },
        {
            'inputs': [
                {
                    'type': 'String',
                    'name': 'input1',
                    'value': 'value1'
                }
            ],
            'group': 'os-apply-config',
            'name': 'dep-name2',
            'outputs': None,
            'options': None,
            'config': {
                'config2': 'value2'
            }
        },
        {
            'inputs': [
                {
                    'type': 'String',
                    'name': 'input1',
                    'value': 'value1'
                }
            ],
            'name': 'dep-name3',
            'outputs': None,
            'options': None,
            'config': {
                'config3': 'value3'
            }
        },
        {
            'inputs': [],
            'group': 'ignore_me',
            'name': 'ignore_me_name',
            'outputs': None,
            'options': None,
            'config': 'ignore_me_config'
        },
        {
            'inputs': [],  # to test missing name
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
