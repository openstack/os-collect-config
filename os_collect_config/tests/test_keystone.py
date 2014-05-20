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

import tempfile

import fixtures
from oslo.config import cfg
import testtools

from os_collect_config import collect
from os_collect_config import keystone
from os_collect_config.tests import test_heat


class KeystoneTest(testtools.TestCase):
    def setUp(self):
        super(KeystoneTest, self).setUp()
        self.addCleanup(cfg.CONF.reset)
        collect.setup_conf()

    def test_cache_is_created(self):
        self.useFixture(fixtures.NestedTempfile())
        cachedir = tempfile.mkdtemp()
        cfg.CONF.set_override('cache_dir', cachedir, group='keystone')
        ks = keystone.Keystone(None, None, None, None,
                               test_heat.FakeKeystoneClient(self))
        self.assertIsNotNone(ks.cache)
