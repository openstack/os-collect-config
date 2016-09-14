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

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

from oslo_config import cfg
from oslo_log import log

from os_collect_config import cache
from os_collect_config import cfn
from os_collect_config import ec2
from os_collect_config import exc
from os_collect_config import heat
from os_collect_config import heat_local
from os_collect_config import keystone
from os_collect_config import local
from os_collect_config import request
from os_collect_config import version
from os_collect_config import zaqar

DEFAULT_COLLECTORS = ['heat_local', 'ec2', 'cfn', 'heat', 'request', 'local',
                      'zaqar']

opts = [
    cfg.StrOpt('command', short='c',
               help='Command to run on metadata changes. If specified,'
                    ' os-collect-config will continue to run until killed. If'
                    ' not specified, os-collect-config will print the'
                    ' collected data as a json map and exit.'),
    cfg.StrOpt('cachedir',
               default='/var/lib/os-collect-config',
               help='Directory in which to store local cache of metadata'),
    cfg.StrOpt('backup-cachedir',
               default='/var/run/os-collect-config',
               help='Copy cache contents to this directory as well.'),
    cfg.MultiStrOpt(
        'collectors',
        positional=True,
        default=DEFAULT_COLLECTORS,
        help='List the collectors to use. When command is specified the'
             'collections will be emitted in the order given by this option.'
        ' (default: %s)' % ' '.join(DEFAULT_COLLECTORS)),
    cfg.BoolOpt('one-time',
                default=False,
                help='Pass this option to make os-collect-config exit after'
                ' one execution of command. This behavior is implied if no'
                ' command is specified.'),
    cfg.FloatOpt('polling-interval', short='i', default=30,
                 help='When running continuously, pause a maximum of this'
                      ' many seconds between collecting data. If changes'
                      ' are detected shorter sleeps intervals are gradually'
                      ' increased to this maximum polling interval.'),
    cfg.BoolOpt('print-cachedir',
                default=False,
                help='Print out the value of cachedir and exit immediately.'),
    cfg.BoolOpt('force',
                default=False,
                help='Pass this to force running the command even if nothing'
                ' has changed. Implies --one-time.'),
    cfg.BoolOpt('print', dest='print_only',
                default=False,
                help='Query normally, print the resulting configs as a json'
                ' map, and exit immediately without running command if it is'
                ' configured.'),
    cfg.MultiStrOpt('deployment-key',
                    default=['deployments'],
                    help='Key(s) to explode into multiple collected outputs. '
                    'Parsed according to the expected Metadata created by '
                    'OS::Heat::StructuredDeployment. Only Exploded if seen at '
                    'the root of the Metadata.')
]

CONF = cfg.CONF
logger = log.getLogger('os-collect-config')

COLLECTORS = {ec2.name: ec2,
              cfn.name: cfn,
              heat.name: heat,
              heat_local.name: heat_local,
              local.name: local,
              request.name: request,
              zaqar.name: zaqar}


def setup_conf():
    ec2_group = cfg.OptGroup(name='ec2',
                             title='EC2 Metadata options')

    cfn_group = cfg.OptGroup(name='cfn',
                             title='CloudFormation API Metadata options')

    heat_local_group = cfg.OptGroup(name='heat_local',
                                    title='Heat Local Metadata options')

    local_group = cfg.OptGroup(name='local',
                               title='Local Metadata options')

    heat_group = cfg.OptGroup(name='heat',
                              title='Heat Metadata options')

    zaqar_group = cfg.OptGroup(name='zaqar',
                               title='Zaqar queue options')

    request_group = cfg.OptGroup(name='request',
                                 title='Request Metadata options')

    keystone_group = cfg.OptGroup(name='keystone',
                                  title='Keystone auth options')

    CONF.register_group(ec2_group)
    CONF.register_group(cfn_group)
    CONF.register_group(heat_local_group)
    CONF.register_group(local_group)
    CONF.register_group(heat_group)
    CONF.register_group(request_group)
    CONF.register_group(keystone_group)
    CONF.register_group(zaqar_group)
    CONF.register_cli_opts(ec2.opts, group='ec2')
    CONF.register_cli_opts(cfn.opts, group='cfn')
    CONF.register_cli_opts(heat_local.opts, group='heat_local')
    CONF.register_cli_opts(local.opts, group='local')
    CONF.register_cli_opts(heat.opts, group='heat')
    CONF.register_cli_opts(request.opts, group='request')
    CONF.register_cli_opts(keystone.opts, group='keystone')
    CONF.register_cli_opts(zaqar.opts, group='zaqar')

    CONF.register_cli_opts(opts)
    log.register_options(CONF)


def collect_all(collectors, store=False, collector_kwargs_map=None):
    changed_keys = set()
    all_keys = list()
    if store:
        paths_or_content = []
    else:
        paths_or_content = {}

    for collector in collectors:
        module = COLLECTORS[collector]
        if collector_kwargs_map and collector in collector_kwargs_map:
            collector_kwargs = collector_kwargs_map[collector]
        else:
            collector_kwargs = {}

        try:
            content = module.Collector(**collector_kwargs).collect()
        except exc.SourceNotAvailable:
            logger.warn('Source [%s] Unavailable.' % collector)
            continue
        except exc.SourceNotConfigured:
            logger.debug('Source [%s] Not configured.' % collector)
            continue

        if store:
            for output_key, output_content in content:
                all_keys.append(output_key)
                (changed, path) = cache.store(output_key, output_content)
                if changed:
                    changed_keys.add(output_key)
                paths_or_content.append(path)
        else:
            paths_or_content.update(content)

    if changed_keys:
        cache.store_meta_list('os_config_files', all_keys)
        if os.path.exists(CONF.backup_cachedir):
            shutil.rmtree(CONF.backup_cachedir)
        if os.path.exists(CONF.cachedir):
            shutil.copytree(CONF.cachedir, CONF.backup_cachedir)
    return (changed_keys, paths_or_content)


def reexec_self(signal=None, frame=None):
    if signal:
        logger.info('Signal received. Re-executing %s' % sys.argv)
    # Close all but stdin/stdout/stderr
    os.closerange(3, 255)
    os.execv(sys.argv[0], sys.argv)


def call_command(files, command):
    env = dict(os.environ)
    env["OS_CONFIG_FILES"] = ':'.join(files)
    logger.info("Executing %s with OS_CONFIG_FILES=%s" %
                (command, env["OS_CONFIG_FILES"]))
    subprocess.check_call(CONF.command, env=env, shell=True)


def getfilehash(files):
    """Calculates the md5sum of the contents of a list of files.

    For each readable file in the provided list returns the md5sum of the
    concatenation of each file
    :param files: a list of files to be read
    :returns: string -- resulting md5sum
    """
    m = hashlib.md5()
    for filename in files:
        try:
            with open(filename) as fp:
                data = fp.read()
            m.update(data.encode('utf-8'))
        except IOError:
            pass
    return m.hexdigest()


def __main__(args=sys.argv, collector_kwargs_map=None):
    signal.signal(signal.SIGHUP, reexec_self)
    setup_conf()
    CONF(args=args[1:], prog="os-collect-config",
         version=version.version_info.version_string())

    # This resets the logging infrastructure which prevents capturing log
    # output in tests cleanly, so should only be called if there isn't already
    # handlers defined i.e. not in unit tests
    if not log.getLogger(None).logger.handlers:
        log.setup(CONF, "os-collect-config")

    if CONF.print_cachedir:
        print(CONF.cachedir)
        return

    unknown_collectors = set(CONF.collectors) - set(COLLECTORS.keys())
    if unknown_collectors:
        raise exc.InvalidArguments(
            'Unknown collectors %s. Valid collectors are: %s' %
            (list(unknown_collectors), DEFAULT_COLLECTORS))

    if CONF.force:
        CONF.set_override('one_time', True)

    exitval = 0
    config_files = CONF.config_file
    config_hash = getfilehash(config_files)
    sleep_time = 1
    while True:
        store_and_run = bool(CONF.command and not CONF.print_only)
        (changed_keys, content) = collect_all(
            cfg.CONF.collectors,
            store=store_and_run,
            collector_kwargs_map=collector_kwargs_map)
        if store_and_run:
            if changed_keys or CONF.force:
                # shorter sleeps while changes are detected allows for faster
                # software deployment dependency processing
                sleep_time = 1
                # ignore HUP now since we will reexec after commit anyway
                signal.signal(signal.SIGHUP, signal.SIG_IGN)
                try:
                    call_command(content, CONF.command)
                except subprocess.CalledProcessError as e:
                    exitval = e.returncode
                    logger.error('Command failed, will not cache new data. %s'
                                 % e)
                    if not CONF.one_time:
                        new_config_hash = getfilehash(config_files)
                        if config_hash == new_config_hash:
                            logger.warn(
                                'Sleeping %.2f seconds before re-exec.' %
                                sleep_time
                            )
                            time.sleep(sleep_time)
                        else:
                            # The command failed but the config file has
                            # changed re-exec now as the config file change
                            # may have fixed things.
                            logger.warn('Config changed, re-execing now')
                            config_hash = new_config_hash
                else:
                    for changed in changed_keys:
                        cache.commit(changed)
                if not CONF.one_time:
                    reexec_self()
            else:
                logger.debug("No changes detected.")
            if CONF.one_time:
                break
            else:
                logger.info("Sleeping %.2f seconds.", sleep_time)
                time.sleep(sleep_time)

            sleep_time *= 2
            if sleep_time > CONF.polling_interval:
                sleep_time = CONF.polling_interval
        else:
            print(json.dumps(content, indent=1))
            break
    return exitval


if __name__ == '__main__':
    sys.exit(__main__())
