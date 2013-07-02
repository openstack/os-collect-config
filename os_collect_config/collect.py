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
import subprocess

from openstack.common import log
from os_collect_config import cache
from os_collect_config import cfn
from os_collect_config import common
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
logger = log.getLogger('os-collect-config')

COLLECTORS = (ec2, cfn)


def setup_conf():
    ec2_group = cfg.OptGroup(name='ec2',
                             title='EC2 Metadata options')

    cfn_group = cfg.OptGroup(name='cfn',
                             title='CloudFormation API Metadata options')

    CONF.register_group(ec2_group)
    CONF.register_group(cfn_group)
    CONF.register_cli_opts(ec2.opts, group='ec2')
    CONF.register_cli_opts(cfn.opts, group='cfn')

    CONF.register_cli_opts(opts)


def __main__(requests_impl_map=None):
    setup_conf()
    CONF(prog="os-collect-config")
    log.setup("os-collect-config")

    final_content = {}
    paths = []
    for collector in COLLECTORS:
        if requests_impl_map and collector.name in requests_impl_map:
            requests_impl = requests_impl_map[collector.name]
        else:
            requests_impl = common.requests
        content = collector.Collector(requests_impl=requests_impl).collect()

        any_changed = False
        if CONF.command:
            (changed, path) = cache.store(collector.name, content)
            any_changed |= changed
            paths.append(path)
        else:
            final_content[collector.name] = content

    if CONF.command:
        if any_changed:
            env = dict(os.environ)
            env["OS_CONFIG_FILES"] = ':'.join(paths)
            logger.info("Executing %s" % CONF.command)
            subprocess.call(CONF.command, env=env, shell=True)
            for collector in COLLECTORS:
                cache.commit(collector.name)
        else:
            logger.debug("No changes detected.")
    else:
        print json.dumps(final_content, indent=1)


if __name__ == '__main__':
    __main__()
