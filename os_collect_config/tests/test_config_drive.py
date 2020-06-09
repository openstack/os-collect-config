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
import subprocess
from unittest import mock

import fixtures
import testtools

from os_collect_config import config_drive
from os_collect_config.tests import test_ec2

BLKID_CONFIG_DRIVE = '''DEVNAME=/dev/sr0
UUID=2016-09-12-02-14-09-00
LABEL=config-2
TYPE=iso9660'''

BLKID_RESPONSE = BLKID_CONFIG_DRIVE + '''

DEVNAME=/dev/block/253:1
UUID=f13d84b4-c756-4d89-9d5e-6b534397aa14
TYPE=xfs
'''


class TestConfigDrive(testtools.TestCase):

    def setUp(self):
        super(TestConfigDrive, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())

    @mock.patch.object(subprocess, 'check_output')
    def test_all_devices(self, co):
        co.return_value = BLKID_RESPONSE
        bds = list(config_drive.all_block_devices())
        self.assertEqual(2, len(bds))

        self.assertEqual('/dev/sr0', bds[0].devname)
        self.assertEqual('iso9660', bds[0].type)
        self.assertEqual('config-2', bds[0].label)
        self.assertTrue(bds[0].config_drive_candidate())
        self.assertEqual('/dev/sr0: TYPE="iso9660" LABEL="config-2"',
                         str(bds[0]))

        self.assertEqual('/dev/block/253:1', bds[1].devname)
        self.assertEqual('xfs', bds[1].type)
        self.assertIsNone(bds[1].label)
        self.assertFalse(bds[1].config_drive_candidate())
        self.assertEqual('/dev/block/253:1: TYPE="xfs" LABEL="None"',
                         str(bds[1]))

    @mock.patch.object(subprocess, 'check_output')
    def test_config_drive(self, co):
        co.return_value = BLKID_RESPONSE
        bd = config_drive.config_drive()
        self.assertTrue(bd.config_drive_candidate())
        self.assertEqual('/dev/sr0: TYPE="iso9660" LABEL="config-2"',
                         str(bd))

    def test_parse_shell_var(self):
        psv = config_drive.BlockDevice.parse_shell_var
        self.assertEqual(('foo', 'bar'), psv('foo=bar'))
        self.assertEqual(('foo', 'bar=baz'), psv('foo=bar=baz'))
        self.assertEqual(('foo', 'bar baz'), psv('foo=bar baz'))
        self.assertEqual(('foo', 'bar baz'), psv('foo=bar\ baz'))
        self.assertEqual(('foo', ''), psv('foo='))
        self.assertEqual((None, None), psv('foo'))
        self.assertEqual((None, None), psv(None))

    @mock.patch.object(subprocess, 'check_output')
    def test_ensure_mounted(self, co):
        bd = config_drive.BlockDevice.from_blkid_export(BLKID_CONFIG_DRIVE)
        self.assertTrue(bd.config_drive_candidate())
        proc = self.useFixture(fixtures.TempDir())
        config_drive.PROC_MOUNTS_PATH = os.path.join(proc.path, 'mount')
        with open(config_drive.PROC_MOUNTS_PATH, 'w') as md:
            md.write('')

        self.assertIsNone(bd.mountpoint)
        self.assertFalse(bd.unmount)

        bd.ensure_mounted()
        mountpoint = bd.mountpoint
        self.assertIsNotNone(mountpoint)
        self.assertTrue(bd.unmount)
        self.assertTrue(os.path.isdir(mountpoint))
        co.assert_called_with([
            'mount', '/dev/sr0', mountpoint, '-o', 'ro'
        ])

        bd.cleanup()
        self.assertIsNone(bd.mountpoint)
        self.assertFalse(bd.unmount)
        self.assertFalse(os.path.isdir(mountpoint))
        co.assert_called_with([
            'umount', '-l', mountpoint
        ])

    @mock.patch.object(subprocess, 'check_output')
    def test_already_mounted(self, co):
        bd = config_drive.BlockDevice.from_blkid_export(BLKID_CONFIG_DRIVE)
        self.assertTrue(bd.config_drive_candidate())
        proc = self.useFixture(fixtures.TempDir())
        mountpoint = self.useFixture(fixtures.TempDir()).path
        config_drive.PROC_MOUNTS_PATH = os.path.join(proc.path, 'mount')
        with open(config_drive.PROC_MOUNTS_PATH, 'w') as md:
            md.write('%s %s r 0 0\n' % (bd.devname, mountpoint))

        self.assertIsNone(bd.mountpoint)
        self.assertFalse(bd.unmount)

        bd.ensure_mounted()
        self.assertEqual(mountpoint, bd.mountpoint)
        self.assertFalse(bd.unmount)
        co.assert_not_called()

        bd.cleanup()
        self.assertIsNone(bd.mountpoint)
        self.assertFalse(bd.unmount)
        co.assert_not_called()

    @mock.patch.object(config_drive.BlockDevice, 'ensure_mounted')
    @mock.patch.object(config_drive.BlockDevice, 'cleanup')
    def test_get_metadata(self, cleanup, ensure_mounted):
        bd = config_drive.BlockDevice.from_blkid_export(BLKID_CONFIG_DRIVE)
        bd.mountpoint = self.useFixture(fixtures.TempDir()).path

        md = bd.get_metadata()
        self.assertEqual({}, md)

        md_dir = os.path.join(bd.mountpoint, 'ec2', 'latest')
        os.makedirs(md_dir)
        md_path = os.path.join(md_dir, 'meta-data.json')
        with open(md_path, 'w') as md:
            json.dump(test_ec2.META_DATA_RESOLVED, md)

        md = bd.get_metadata()
        self.assertEqual(test_ec2.META_DATA_RESOLVED, md)
