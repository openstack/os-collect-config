import json
import os
import pystache
import subprocess
from pystache.context import KeyNotFoundError

class CornfigException(Exception):
  pass

def install_cornfig(config_path, template_root):
  config = read_config(config_path)
  for in_file, out_file in template_paths(template_root):
    print render_template(in_file, config)

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
  r = pystache.Renderer(missing_tags = 'strict')
  return r.render(text, config)

def render_executable(path, config):
  try:
    return subprocess.check_output([path], env=flatten(config))
  except subprocess.CalledProcessError as e:
    raise CornfigException("config script failed: %s\n\nwith output:\n\n%s" % (path, e.output))

def read_config(path):
  return json.loads(open(path).read())

def flatten(d, prefix='', res=None):
  res = res or {}
  for k, v in d.items():
    key = (prefix + '.' + k) if len(prefix) > 0 else k
    if isinstance(v, str):
      res[key] = v
    elif isinstance(v, dict):
       res = dict(res.items() + flatten(v, key, res).items())
    else:
      raise CornfigException("expected only strings and hashes in config.")
  return res

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
