import os

#def process_template(in_f, out_f):


def read_config(path):
  return json.loads(open(path).read())


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
