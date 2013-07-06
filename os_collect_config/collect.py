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
import sys

from openstack.common import log
from os_collect_config import cache
from os_collect_config import cfn
from os_collect_config import common
from os_collect_config import ec2
from os_collect_config import exc
from os_collect_config import heat_local
from oslo.config import cfg

DEFAULT_COLLECTORS = ['ec2', 'cfn', 'heat_local']
opts = [
    cfg.StrOpt('command',
               short='c',
               help='Command to run on metadata changes.'),
    cfg.StrOpt('cachedir',
               default='/var/run/os-collect-config',
               help='Directory in which to store local cache of metadata'),
    cfg.MultiStrOpt(
        'collectors',
        positional=True,
        default=DEFAULT_COLLECTORS,
        help='List the collectors to use. When command is specified the'
             'collections will be emitted in the order given by this option.'
        ' (default: %s)' % ' '.join(DEFAULT_COLLECTORS)),
]

CONF = cfg.CONF
logger = log.getLogger('os-collect-config')

COLLECTORS = {ec2.name: ec2,
              cfn.name: cfn,
              heat_local.name: heat_local}


def setup_conf():
    ec2_group = cfg.OptGroup(name='ec2',
                             title='EC2 Metadata options')

    cfn_group = cfg.OptGroup(name='cfn',
                             title='CloudFormation API Metadata options')

    heat_local_group = cfg.OptGroup(name='heat_local',
                                    title='Heat Local Metadata options')

    CONF.register_group(ec2_group)
    CONF.register_group(cfn_group)
    CONF.register_group(heat_local_group)
    CONF.register_cli_opts(ec2.opts, group='ec2')
    CONF.register_cli_opts(cfn.opts, group='cfn')
    CONF.register_cli_opts(heat_local.opts, group='heat_local')

    CONF.register_cli_opts(opts)


def collect_all(collectors, store=False, requests_impl_map=None):
    any_changed = False
    if store:
        paths_or_content = []
    else:
        paths_or_content = {}

    for collector in collectors:
        module = COLLECTORS[collector]
        if requests_impl_map and collector in requests_impl_map:
            requests_impl = requests_impl_map[collector]
        else:
            requests_impl = common.requests

        try:
            content = module.Collector(
                requests_impl=requests_impl).collect()
        except exc.SourceNotAvailable:
            logger.warn('Source [%s] Unavailable.' % collector)
            continue

        if store:
            (changed, path) = cache.store(collector, content)
            any_changed |= changed
            paths_or_content.append(path)
        else:
            paths_or_content[collector] = content

    return (any_changed, paths_or_content)


def __main__(args=sys.argv, requests_impl_map=None):
    setup_conf()
    CONF(args=args[1:], prog="os-collect-config")
    log.setup("os-collect-config")

    (any_changed, content) = collect_all(cfg.CONF.collectors,
                                         store=bool(CONF.command),
                                         requests_impl_map=requests_impl_map)
    if CONF.command:
        if any_changed:
            env = dict(os.environ)
            env["OS_CONFIG_FILES"] = ':'.join(content)
            logger.info("Executing %s" % CONF.command)
            subprocess.call(CONF.command, env=env, shell=True)
            for collector in cfg.CONF.collectors:
                cache.commit(collector)
        else:
            logger.debug("No changes detected.")
    else:
        print json.dumps(content, indent=1)


if __name__ == '__main__':
    __main__()
