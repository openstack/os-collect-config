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

from os_apply_config import config_exception
from os_apply_config import value_types


class ValueTypeTestCase(testtools.TestCase):

    def test_unknown_type(self):
        self.assertRaises(
            ValueError, value_types.ensure_type, "foo", "badtype")

    def test_int(self):
        self.assertEqual("123", value_types.ensure_type("123", "int"))

    def test_default(self):
        self.assertEqual("foobar",
                         value_types.ensure_type("foobar", "default"))
        self.assertEqual("x86_64",
                         value_types.ensure_type("x86_64", "default"))

    def test_default_bad(self):
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type, "foo\nbar", "default")

    def test_default_empty(self):
        self.assertEqual('',
                         value_types.ensure_type('', 'default'))

    def test_raw_empty(self):
        self.assertEqual('',
                         value_types.ensure_type('', 'raw'))

    def test_net_address_ipv4(self):
        self.assertEqual('192.0.2.1', value_types.ensure_type('192.0.2.1',
                                                              'netaddress'))

    def test_net_address_cidr(self):
        self.assertEqual('192.0.2.0/24',
                         value_types.ensure_type('192.0.2.0/24', 'netaddress'))

    def test_ent_address_ipv6(self):
        self.assertEqual('::', value_types.ensure_type('::', 'netaddress'))
        self.assertEqual('2001:db8::2:1', value_types.ensure_type(
            '2001:db8::2:1', 'netaddress'))

    def test_net_address_dns(self):
        self.assertEqual('host.0domain-name.test',
                         value_types.ensure_type('host.0domain-name.test',
                                                 'netaddress'))

    def test_net_address_bad(self):
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type, "192.0.2.1;DROP TABLE foo")
