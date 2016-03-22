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

from oslo_config import cfg
from oslo_log import log

from os_collect_config import exc

HEAT_METADATA_PATH = ['/var/lib/heat-cfntools/cfn-init-data']
CONF = cfg.CONF

opts = [
    cfg.MultiStrOpt('path',
                    default=HEAT_METADATA_PATH,
                    help='Local path(s) to read for Metadata.')
]
name = 'heat_local'
logger = log.getLogger(__name__)


class Collector(object):
    def __init__(self, requests_impl=None):
        pass

    def collect(self):
        final_content = None
        for path in cfg.CONF.heat_local.path:
            if os.path.exists(path):
                with open(path) as metadata:
                    try:
                        value = json.loads(metadata.read())
                    except ValueError as e:
                        logger.info('%s is not valid JSON (%s)' % (path, e))
                        continue
                    if final_content:
                        final_content.update(value)
                    else:
                        final_content = value
        if not final_content:
            logger.info('Local metadata not found (%s)' %
                        cfg.CONF.heat_local.path)
            raise exc.HeatLocalMetadataNotAvailable
        return [('heat_local', final_content)]
