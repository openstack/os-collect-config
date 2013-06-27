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
import shutil
import subprocess
import tempfile

from openstack.common import log
from os_collect_config import ec2
from oslo.config import cfg

opts = [
    cfg.StrOpt('command',
               short='c',
               help='Command to run on metadata changes.'),
    cfg.StrOpt('cachedir',
               default='/var/run/os-collect-config',
               help='Directory in which to store local cache of metadata'),
]

CONF = cfg.CONF


def setup_conf():
    ec2_group = cfg.OptGroup(name='ec2',
                             title='EC2 Metadata options')

    CONF.register_group(ec2_group)
    CONF.register_cli_opts(ec2.opts, group='ec2')

    CONF.register_cli_opts(opts)


def cache(name, content):
    if not os.path.exists(CONF.cachedir):
        os.mkdir(CONF.cachedir)

    changed = False
    dest_path = os.path.join(CONF.cachedir, '%s.json' % name)
    orig_path = '%s.orig' % dest_path

    with tempfile.NamedTemporaryFile(dir=CONF.cachedir, delete=False) as new:
        new.write(json.dumps(content, indent=1))
        new.flush()
        if not os.path.exists(orig_path):
            shutil.copy(new.name, orig_path)
            changed = True
        os.rename(new.name, dest_path)

    if not changed:
        with open(dest_path) as now:
            with open(orig_path) as then:
                for now_line in now:
                    then_line = then.next()
                    if then_line != now_line:
                        changed = True
                        break
    return (changed, dest_path)


def __main__():
    setup_conf()
    CONF(prog="os-collect-config")
    log.setup("os-collect-config")
    ec2_content = ec2.collect()

    if CONF.command:
        (changed, ec2_path) = cache('ec2', ec2_content)
        if changed:
            paths = [ec2_path]
            env = dict(os.environ)
            env["OS_CONFIG_FILES"] = ':'.join(paths)
            subprocess.call(CONF.command, env=env)


if __name__ == '__main__':
    __main__()
