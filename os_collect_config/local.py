# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
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
import locale
import os
import stat

from oslo_config import cfg
from oslo_log import log

from os_collect_config import exc

LOCAL_DEFAULT_PATHS = ['/var/lib/os-collect-config/local-data']
CONF = cfg.CONF

opts = [
    cfg.MultiStrOpt('path',
                    default=LOCAL_DEFAULT_PATHS,
                    help='Local directory to scan for Metadata files.')
]
name = 'local'
logger = log.getLogger(__name__)


def _dest_looks_insecure(local_path):
    '''We allow group writable so owner can let others write.'''
    looks_insecure = False
    uid = os.getuid()
    st = os.stat(local_path)
    if uid != st[stat.ST_UID]:
        logger.error('%s is owned by another user. This is a'
                     ' security risk.' % local_path)
        looks_insecure = True
    if st.st_mode & stat.S_IWOTH:
        logger.error('%s is world writable. This is a security risk.'
                     % local_path)
        looks_insecure = True
    return looks_insecure


class Collector(object):
    def __init__(self, requests_impl=None):
        pass

    def collect(self):
        if len(cfg.CONF.local.path) == 0:
            raise exc.LocalMetadataNotAvailable
        final_content = []
        for local_path in cfg.CONF.local.path:
            try:
                os.stat(local_path)
            except OSError:
                logger.warn("%s not found. Skipping", local_path)
                continue
            if _dest_looks_insecure(local_path):
                raise exc.LocalMetadataNotAvailable
            for data_file in os.listdir(local_path):
                if data_file.startswith('.'):
                    continue
                data_file = os.path.join(local_path, data_file)
                if os.path.isdir(data_file):
                    continue
                st = os.stat(data_file)
                if st.st_mode & stat.S_IWOTH:
                    logger.error(
                        '%s is world writable. This is a security risk.' %
                        data_file)
                    raise exc.LocalMetadataNotAvailable
                with open(data_file) as metadata:
                    try:
                        value = json.loads(metadata.read())
                    except ValueError as e:
                        logger.error(
                            '%s is not valid JSON (%s)' % (data_file, e))
                        raise exc.LocalMetadataNotAvailable
                    basename = os.path.basename(data_file)
                    final_content.append((basename, value))
        if not final_content:
            logger.info('No local metadata found (%s)' %
                        cfg.CONF.local.path)

        # Now sort specifically by C locale
        def locale_aware_by_first_item(data):
            return locale.strxfrm(data[0])
        save_locale = locale.getdefaultlocale()
        locale.setlocale(locale.LC_ALL, 'C')
        sorted_content = sorted(final_content, key=locale_aware_by_first_item)
        locale.setlocale(locale.LC_ALL, save_locale)
        return sorted_content
