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
import os
from unittest import mock
import uuid

import fixtures
from oslo_config import cfg
import requests
import six.moves.urllib.parse as urlparse
import testtools

from os_collect_config import collect
from os_collect_config import config_drive
from os_collect_config import ec2
from os_collect_config import exc


META_DATA = {
    'local-ipv4': '192.0.2.1',
    'reservation-id': str(uuid.uuid1()),
    'local-hostname': 'foo',
    'ami-launch-index': '0',
    'public-hostname': 'foo',
    'hostname': 'foo',
    'ami-id': str(uuid.uuid1()),
    'instance-action': 'none',
    'public-ipv4': '192.0.2.1',
    'instance-type': 'flavor.small',
    'placement/': 'availability-zone',
    'placement/availability-zone': 'foo-az',
    'mpi/': 'foo-keypair',
    'mpi/foo-keypair': '192.0.2.1 slots=1',
    'block-device-mapping/': "ami\nroot\nephemeral0",
    'block-device-mapping/ami': 'vda',
    'block-device-mapping/root': '/dev/vda',
    'block-device-mapping/ephemeral0': '/dev/vdb',
    'public-keys/': '0=foo-keypair',
    'public-keys/0': 'openssh-key',
    'public-keys/0/': 'openssh-key',
    'public-keys/0/openssh-key': 'ssh-rsa AAAAAAAAABBBBBBBBCCCCCCCC',
    'instance-id': str(uuid.uuid1())
}


META_DATA_RESOLVED = {
    'local-ipv4': '192.0.2.1',
    'reservation-id': META_DATA['reservation-id'],
    'local-hostname': 'foo',
    'ami-launch-index': '0',
    'public-hostname': 'foo',
    'hostname': 'foo',
    'ami-id': META_DATA['ami-id'],
    'instance-action': 'none',
    'public-ipv4': '192.0.2.1',
    'instance-type': 'flavor.small',
    'placement': {'availability-zone': 'foo-az'},
    'mpi': {'foo-keypair': '192.0.2.1 slots=1'},
    'public-keys': {'0': {'openssh-key': 'ssh-rsa AAAAAAAAABBBBBBBBCCCCCCCC'}},
    'block-device-mapping': {'ami': 'vda',
                             'ephemeral0': '/dev/vdb',
                             'root': '/dev/vda'},
    'instance-id': META_DATA['instance-id']
}


class FakeResponse(dict):
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeRequests(object):
    exceptions = requests.exceptions

    class Session(object):
        def get(self, url, timeout=None):
            url = urlparse.urlparse(url)

            if url.path == '/latest/meta-data/':
                # Remove keys which have anything after /
                ks = [x for x in META_DATA.keys() if (
                    '/' not in x or not len(x.split('/')[1]))]
                return FakeResponse("\n".join(ks))

            path = url.path
            path = path.replace('/latest/meta-data/', '')
            return FakeResponse(META_DATA[path])


class FakeFailRequests(object):
    exceptions = requests.exceptions

    class Session(object):
        def get(self, url, timeout=None):
            raise requests.exceptions.HTTPError(403, 'Forbidden')


class TestEc2(testtools.TestCase):
    def setUp(self):
        super(TestEc2, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())

    @mock.patch.object(config_drive, 'config_drive')
    def test_collect_ec2(self, cd):
        cd.return_value = None
        collect.setup_conf()
        ec2_md = ec2.Collector(requests_impl=FakeRequests).collect()
        self.assertEqual([('ec2', META_DATA_RESOLVED)], ec2_md)
        self.assertEqual('', self.log.output)

    @mock.patch.object(config_drive, 'config_drive')
    def test_collect_ec2_fail(self, cd):
        cd.return_value = None
        collect.setup_conf()
        collect_ec2 = ec2.Collector(requests_impl=FakeFailRequests)
        self.assertRaises(exc.Ec2MetadataNotAvailable, collect_ec2.collect)
        self.assertIn('Forbidden', self.log.output)

    @mock.patch.object(config_drive, 'config_drive')
    def test_collect_ec2_invalid_cache(self, cd):
        cd.return_value = None
        collect.setup_conf()
        cache_dir = self.useFixture(fixtures.TempDir())
        self.addCleanup(cfg.CONF.reset)
        cfg.CONF.set_override('cachedir', cache_dir.path)
        ec2_path = os.path.join(cache_dir.path, 'ec2.json')
        with open(ec2_path, 'w') as f:
            f.write('')

        ec2_md = ec2.Collector(requests_impl=FakeRequests).collect()
        self.assertEqual([('ec2', META_DATA_RESOLVED)], ec2_md)

    @mock.patch.object(config_drive, 'config_drive')
    def test_collect_ec2_collected(self, cd):
        cd.return_value = None
        collect.setup_conf()
        cache_dir = self.useFixture(fixtures.TempDir())
        self.addCleanup(cfg.CONF.reset)
        cfg.CONF.set_override('cachedir', cache_dir.path)
        ec2_path = os.path.join(cache_dir.path, 'ec2.json')
        with open(ec2_path, 'w') as f:
            json.dump(META_DATA, f)

        collect_ec2 = ec2.Collector(requests_impl=FakeFailRequests)
        self.assertEqual([('ec2', META_DATA)], collect_ec2.collect())

    @mock.patch.object(config_drive, 'config_drive')
    def test_collect_config_drive(self, cd):
        cd.return_value.get_metadata.return_value = META_DATA_RESOLVED
        collect.setup_conf()
        ec2_md = ec2.Collector(requests_impl=FakeFailRequests).collect()
        self.assertEqual([('ec2', META_DATA_RESOLVED)], ec2_md)
        self.assertEqual('', self.log.output)
