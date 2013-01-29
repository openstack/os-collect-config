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

logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p', level=logging.INFO)

class CornfigException(Exception):
  pass

def install_cornfig(config_path, template_root, output_path='/'):
  config = read_config(config_path)
  tree = build_tree( template_paths(template_root), config )
  for path, contents in tree.items():
    write_file( os.path.join(output_path, strip_prefix('/', path)), contents)

def write_file(path, contents):
  logging.info("writing %s", path)
  d = os.path.dirname(path)
  if not os.path.exists(d):
    os.makedirs(d)
  out = open(path, 'w')
  out.write(contents)
  out.close()

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
    return render_moustache(open(template).read(), config)

def is_executable(path):
  return os.path.isfile(path) and os.access(path, os.X_OK)

def render_moustache(text, config):
  try:
    r = pystache.Renderer(missing_tags = 'strict')
    return r.render(text, config)
  except KeyNotFoundError as e:
    raise CornfigException("key '%s' does not exist metadata file." % e.key)

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

# given a root directory, return a list of tuples
# containing input and output paths
def template_paths(root):
  res = []
  for cur_root, subdirs, files in os.walk(root):
    for f in files:
      inout = ( os.path.join(cur_root, f), os.path.join(strip_prefix(root, cur_root), f) )
      res.append(inout)
  return res

def strip_prefix(prefix, s):
  return s[len(prefix):] if s.startswith(prefix) else s


def usage():
  print "Usage:\n  cornfig TEMPLATE_ROOT JSON_PATH OUTPUT_ROOT"
  sys.exit(1)

def main():
  try:
    parser = OptionParser(usage="cornfig -t TEMPLATE_ROOT [-m METADATA_FILE] [-o OUT_DIR]")
    parser.add_option('-m', '--metadata', dest='metadata_path',
      help='path to metadata file (default: /var/lib/cloud/cfn-init-data)',
      default='/var/lib/cloud/cfn-init-data')
    parser.add_option('-t', '--templates', dest='template_root', help='path to template root directory')
    parser.add_option('-o', '--output', dest='out_root', help='root directory for output (default: /)', default='/')
    (options, args) = parser.parse_args()

    if options.template_root is None: raise CornfigException('missing option --templates')

    install_cornfig(options.metadata_path, options.template_root, options.out_root)
  except CornfigException as e:
    logging.error(e)
    sys.exit(1)

if __name__ == '__main__':
  main()
