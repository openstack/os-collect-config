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

"""Metadata cache.

Files within the cache as passed to hook commands invoked by
os-collect-command.

The cache also stores the last version of a file in order to detect changes
that occur - hook commands are only automatically invoked when one or more
metadata sources have changed things.

The last version of a file is available under $FILENAME.last.
"""

import json
import os
import shutil
import tempfile

from oslo.config import cfg


def get_path(name):
    return os.path.join(cfg.CONF.cachedir, '%s.json' % name)


def store(name, content):
    if not os.path.exists(cfg.CONF.cachedir):
        os.mkdir(cfg.CONF.cachedir)

    changed = False
    dest_path = get_path(name)
    orig_path = '%s.orig' % dest_path
    last_path = '%s.last' % dest_path

    with tempfile.NamedTemporaryFile(
            dir=cfg.CONF.cachedir,
            delete=False) as new:
        new.write(json.dumps(content, indent=1))
        new.flush()
        if not os.path.exists(orig_path):
            shutil.copy(new.name, orig_path)
            changed = True
        os.rename(new.name, dest_path)

    if not changed:
        with open(dest_path) as now:
            if os.path.exists(last_path):
                with open(last_path) as then:
                    for now_line in now:
                        then_line = then.next()
                        if then_line != now_line:
                            changed = True
                            break
            else:
                changed = True
    return (changed, dest_path)


def commit(name):
    dest_path = get_path(name)
    if os.path.exists(dest_path):
        shutil.copy(dest_path, '%s.last' % dest_path)
