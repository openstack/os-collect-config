#!/usr/bin/env python
import json
import logging
import os
import pystache
import sys
import tempfile
from optparse import OptionParser
from pystache.context import KeyNotFoundError
from subprocess import Popen, PIPE

def install_cornfig(config_path, template_root, output_path, write):
  config = read_config(config_path)
  tree = build_tree( template_paths(template_root), config )
  if write:
    for path, contents in tree.items():
      write_file( os.path.join(output_path, strip_prefix('/', path)), contents)

def write_file(path, contents):
  logger.info("writing %s", path)
  d = os.path.dirname(path)
  os.path.exists(d) or os.makedirs(d)
  with open(path, 'w') as f: f.write(contents)

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
    except KeyNotFoundError as e:
      raise CornfigException("key '%s' does not exist in metadata file '%s'" % (e.key, template))
    except Exception as e:
      raise CornfigException("could not render moustache template %s" % template)

def is_executable(path):
  return os.path.isfile(path) and os.access(path, os.X_OK)

def render_moustache(text, config):
  r = pystache.Renderer(missing_tags = 'strict')
  return r.render(text, config)

def render_executable(path, config):
  p = Popen([path], stdin=PIPE, stdout=PIPE, stderr=PIPE)
  stdout, stderr = p.communicate(json.dumps(config))
  p.wait()
  if p.returncode != 0: raise CornfigException("config script failed: %s\n\nwith output:\n\n%s" % (path, stdout + stderr))
  return stdout

def read_config(path):
  try:
    return json.loads(open(path).read())
  except:
    raise CornfigException("invalid metadata file: %s" % path)

def template_paths(root):
  res = []
  for cur_root, subdirs, files in os.walk(root):
    for f in files:
      inout = ( os.path.join(cur_root, f), os.path.join(strip_prefix(root, cur_root), f) )
      res.append(inout)
  return res

def strip_prefix(prefix, s):
  return s[len(prefix):] if s.startswith(prefix) else s

def parse_opts():
    parser = OptionParser(usage="cornfig -t TEMPLATE_ROOT [-m METADATA_FILE] [-o OUT_DIR]")
    parser.add_option('-t', '--templates', dest='template_root', help='path to template root directory')
    parser.add_option('-o', '--output',    dest='out_root',      help='root directory for output (default: /)',
                       default='/')
    parser.add_option('-m', '--metadata', dest='metadata_path',  help='path to metadata file',
                       default='/var/lib/cloud/cfn-init-data')
    parser.add_option('-v', '--validate', dest='write',          help='validate only. do not write files',
                       default=True, action='store_false')
    (opts, args) = parser.parse_args()

    if opts.template_root is None: raise CornfigException('missing option --templates')
    if not os.access(opts.out_root, os.W_OK):
      raise CornfigException("you don't have permission to write to '%s'" % opts.out_root)
    return opts

def main():
  try:
    opts = parse_opts()
    install_cornfig(opts.metadata_path, opts.template_root, opts.out_root, opts.write)
    logger.info("success")
  except CornfigException as e:
    logger.error(e)
    sys.exit(1)

class CornfigException(Exception):
  pass

# logginig
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s'
DATE_FORMAT = '%Y/%m/%d %I:%M:%S %p'
def add_handler(logger, handler):
  handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
  logger.addHandler(handler)
logger = logging.getLogger('cornfig')
logger.setLevel(logging.INFO)
add_handler(logger, logging.StreamHandler(sys.stdout))
if os.geteuid() == 0: add_handler(logger, logging.FileHandler('/var/log/cornfig.log'))

if __name__ == '__main__':
  main()
