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
import subprocess
import tempfile

from oslo_log import log


logger = log.getLogger('os-collect-config')


PROC_MOUNTS_PATH = '/proc/mounts'


class BlockDevice(object):

    devname = None

    type = None

    label = None

    mountpoint = None

    unmount = False

    ATTR_MAP = {
        'DEVNAME': 'devname',
        'TYPE': 'type',
        'LABEL': 'label'
    }

    @staticmethod
    def parse_shell_var(line):
        # parse shell-style KEY=value
        try:
            ieq = line.index('=')
        except (ValueError, AttributeError):
            return None, None
        value = line[ieq + 1:]
        # unescape backslash escaped spaces
        value = value.replace('\\ ', ' ')
        return line[:ieq], value

    @classmethod
    def from_blkid_export(cls, export_str):
        '''Construct BlockDevice from export formatted blkid output.'''
        bd = cls()
        for line in export_str.splitlines():
            var, value = cls.parse_shell_var(line)
            if var in cls.ATTR_MAP:
                setattr(bd, cls.ATTR_MAP[var], value)
        return bd

    def config_drive_candidate(self):
        '''Whether this block device is a v2 config-drive.'''
        return self.label == 'config-2' and self.type in (
            'vfat', 'iso9660')

    def ensure_mounted(self):
        '''Finds an existing mountpoint or mounts to a temp directory.'''
        self.unmount = False
        # check if already mounted, if so use that
        with open(PROC_MOUNTS_PATH, 'r') as f:
            for line in f.read().splitlines():
                values = line.split()
                if values[0] == self.devname:
                    self.mountpoint = values[1]
                    logger.debug('Found existing mounted config-drive: %s' %
                                 self.mountpoint)
                    return

        # otherwise mount readonly to a temp directory
        self.mountpoint = tempfile.mkdtemp(prefix='config-2-')
        cmd = ['mount', self.devname, self.mountpoint, '-o', 'ro']
        logger.debug('Mounting %s at : %s' % (self.devname, self.mountpoint))
        try:
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            logger.error('Problem running "%s": %s', ' '.join(cmd), e)
            os.rmdir(self.mountpoint)
            self.mountpoint = None
        else:
            self.unmount = True

    def cleanup(self):
        '''Unmounts device if mounted by ensure_mounted.'''
        if not self.unmount:
            self.mountpoint = None
            return
        if not self.mountpoint:
            self.unmount = False
            return

        cmd = ['umount', '-l', self.mountpoint]
        logger.debug('Unmounting: %s' % self.mountpoint)
        try:
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            logger.error('Problem running "%s": %s', ' '.join(cmd), e)
        else:
            os.rmdir(self.mountpoint)
            self.mountpoint = None
            self.unmount = False

    def get_metadata(self):
        '''Load and return ec2/latest/meta-data.json from config drive.'''
        try:
            self.ensure_mounted()
            if not self.mountpoint:
                return {}

            md_path = os.path.join(self.mountpoint,
                                   'ec2', 'latest', 'meta-data.json')
            if not os.path.isfile(md_path):
                logger.warn('No expected file at path: %s' % md_path)
                return {}
            with open(md_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error('Problem getting metadata: %s', e)
            return {}
        finally:
            self.cleanup()

    def __repr__(self):
        return '%s: TYPE="%s" LABEL="%s"' % (self.devname,
                                             self.type,
                                             self.label)


def all_block_devices():
    '''Run blkid and yield a BlockDevice for all devices.'''
    try:
        cmd = ['blkid', '-o', 'export']
        out = subprocess.check_output(cmd, universal_newlines=True)
    except Exception as e:
        logger.error('Problem running "%s": %s', ' '.join(cmd), e)
    else:
        # with -o export, devices are separated by a blank line
        for device in out.split('\n\n'):
            yield BlockDevice.from_blkid_export(device)


def config_drive():
    """Return the first device expected to contain a v2 config drive.

    Disk needs to be:
    * either vfat or iso9660 formated
    * labeled with 'config-2'
    """
    for bd in all_block_devices():
        if bd.config_drive_candidate():
            return bd


def get_metadata():
    """Return discovered config drive metadata, or an empty dict."""
    bd = config_drive()
    if bd:
        return bd.get_metadata()
    return {}
