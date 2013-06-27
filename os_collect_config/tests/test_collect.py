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

import fixtures
import json
from oslo.config import cfg
import testtools
from testtools import matchers

from os_collect_config import collect
from os_collect_config.tests import test_ec2


class TestCollect(testtools.TestCase):
    def test_main(self):
        self.useFixture(
            fixtures.MonkeyPatch(
                'os_collect_config.ec2.h', test_ec2.FakeHttp()))
        out = self.useFixture(fixtures.ByteStream('stdout'))
        self.useFixture(fixtures.MonkeyPatch('sys.stdout', out.stream))
        collect.__main__()
        result = json.loads(out.stream.getvalue())
        self.assertIn("local-ipv4", result)
        self.assertIn("reservation-id", result)

    def test_setup_conf(self):
        conf = collect.setup_conf()
        self.assertThat(conf, matchers.IsInstance(cfg.ConfigOpts))
        self.assertEquals('/var/run/os-collect-config', conf.cachedir)
