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

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile

from pystache import context

from config_exception import ConfigException
from renderers import JsonRenderer
from value_types import ensure_type

TEMPLATES_DIR = os.environ.get('OS_CONFIG_APPLIER_TEMPLATES', None)
if TEMPLATES_DIR is None:
    TEMPLATES_DIR = '/opt/stack/os-apply-config/templates'
    if not os.path.isdir(TEMPLATES_DIR):
        # Backwards compat with the old name.
        TEMPLATES_DIR = '/opt/stack/os-config-applier/templates'


def install_config(config_path, template_root,
                   output_path, validate, subhash=None):
    config = strip_hash(read_config(config_path), subhash)
    tree = build_tree(template_paths(template_root), config)
    if not validate:
        for path, contents in tree.items():
            write_file(os.path.join(
                output_path, strip_prefix('/', path)), contents)


def print_key(config_path, key, type_name, default=None):
    config = read_config(config_path)
    keys = key.split('.')
    for key in keys:
        try:
            config = config[key]
        except KeyError:
            if default is not None:
                print default
                return
            else:
                raise ConfigException(
                    'key %s does not exist in %s' % (key, config_path))
    ensure_type(config, type_name)
    print config


def write_file(path, contents):
    logger.info("writing %s", path)
    d = os.path.dirname(path)
    os.path.exists(d) or os.makedirs(d)
    with tempfile.NamedTemporaryFile(dir=d, delete=False) as newfile:
        newfile.write(contents)
        os.chmod(newfile.name, 0644)
        os.rename(newfile.name, path)

# return a map of filenames->filecontents


def build_tree(templates, config):
    res = {}
    for in_file, out_file in templates:
        res[out_file] = render_template(in_file, config)
    return res


def render_template(template, config):
    if is_executable(template):
        return render_executable(template, config)
    else:
        try:
            return render_moustache(open(template).read(), config)
        except context.KeyNotFoundError as e:
            raise ConfigException(
                "key '%s' from template '%s' does not exist in metadata file."
                % (e.key, template))
        except Exception as e:
            raise ConfigException(
                "could not render moustache template %s" % template)


def is_executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def render_moustache(text, config):
    r = JsonRenderer(missing_tags='ignore')
    return r.render(text, config)


def render_executable(path, config):
    p = subprocess.Popen([path],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(json.dumps(config))
    p.wait()
    if p.returncode != 0:
        raise ConfigException(
            "config script failed: %s\n\nwith output:\n\n%s" %
            (path, stdout + stderr))
    return stdout


def read_config(paths):
    for path in paths:
        if os.path.exists(path):
            try:
                return json.loads(open(path).read())
            except Exception:
                raise ConfigException("invalid metadata file: %s" % path)
    raise ConfigException("No metadata found.")


def template_paths(root):
    res = []
    for cur_root, subdirs, files in os.walk(root):
        for f in files:
            inout = (os.path.join(cur_root, f), os.path.join(
                strip_prefix(root, cur_root), f))
            res.append(inout)
    return res


def strip_prefix(prefix, s):
    return s[len(prefix):] if s.startswith(prefix) else s


def strip_hash(h, keys):
    if not keys:
        return h
    for k in keys.split('.'):
        if k in h and isinstance(h[k], dict):
            h = h[k]
        else:
            raise ConfigException(
                "key '%s' does not correspond to a hash in the metadata file"
                % keys)
    return h


def parse_opts(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--templates', metavar='TEMPLATE_ROOT',
                        help="""path to template root directory (default:
                        %(default)s)""",
                        default=TEMPLATES_DIR)
    parser.add_argument('-o', '--output', metavar='OUT_DIR',
                        help='root directory for output (default:%(default)s)',
                        default='/')
    parser.add_argument('-m', '--metadata', metavar='METADATA_FILE', nargs='*',
                        help='path to metadata files. First one that exists'
                        ' will be used. (default: %(default)s)',
                        default=['/var/cache/heat-cfntools/last_metadata',
                                 '/var/lib/heat-cfntools/cfn-init-data',
                                 '/var/lib/cloud/data/cfn-init-data'])
    parser.add_argument(
        '-v', '--validate', help='validate only. do not write files',
        default=False, action='store_true')
    parser.add_argument(
        '--print-templates', default=False, action='store_true',
        help='Print templates root and exit.')
    parser.add_argument('-s', '--subhash',
                        help='use the sub-hash named by this key,'
                             ' instead of the full metadata hash')
    parser.add_argument('--key', metavar='KEY', default=None,
                        help='print the specified key and exit.'
                             ' (may be used with --type and --key-default)')
    parser.add_argument('--type', default='default',
                        help='exit with error if the specified --key does not'
                             ' match type. Valid types are'
                             ' <int|default|netaddress|raw>')
    parser.add_argument('--key-default',
                        help='This option only affects running with --key.'
                             ' Print this if key is not found. This value is'
                             ' not subject to type restrictions. If --key is'
                             ' specified and no default is specified, program'
                             ' exits with an error on missing key.')
    opts = parser.parse_args(argv[1:])

    return opts


def main(argv=sys.argv):
    opts = parse_opts(argv)
    if opts.print_templates:
        print(opts.templates)
        return 0

    try:
        if opts.templates is None:
            raise ConfigException('missing option --templates')

        if opts.key:
            print_key(opts.metadata,
                      opts.key,
                      opts.type,
                      opts.key_default)
        else:
            install_config(opts.metadata, opts.templates, opts.output,
                           opts.validate, opts.subhash)
            logger.info("success")
    except ConfigException as e:
        logger.error(e)
        return 1
    return 0


# logging
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s'
DATE_FORMAT = '%Y/%m/%d %I:%M:%S %p'


def add_handler(logger, handler):
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
logger = logging.getLogger('os-apply-config')
logger.setLevel(logging.INFO)
add_handler(logger, logging.StreamHandler())
if os.geteuid() == 0:
    add_handler(logger, logging.FileHandler('/var/log/os-apply-config.log'))
