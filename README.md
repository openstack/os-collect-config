os-apply-config
===============

Apply configuration from cloud metadata (JSON).


# What does it do?

It turns a cloud-metadata file like this:
```javascript
{"keystone": {"database": {"host": "127.0.0.1", "user": "keystone", "password": "foobar"}}}
```
into service config files like this:
```
[sql]
connection = mysql://keystone:foobar@127.0.0.1/keystone
...other settings...
```

# Usage

Just pass it the path to a directory tree of templates:
```
sudo os-apply-config -t /home/me/my_templates
```

# Templates

The template directory structure should mimic a root filesystem, and contain templates for only those files you want configured.

e.g.
```
~/my_templates$ tree
.
└── etc
    ├── keystone
    │   └── keystone.conf
    └── mysql
        └── mysql.conf
```

An example tree [can be found here](https://github.com/tripleo/openstack_config_templates).

If a template is executable it will be treated as an **executable template**.
Otherwise, it will be treated as a **mustache template**.

## Mustache Templates

If you don't need any logic, just some string substitution, use a mustache template.

Metadata settings are accessed with dot ('.') notation:

```
[sql]
connection = mysql://{{keystone.database.user}}:{{keystone.database.password}@{{keystone.database.host}}/keystone
```

## Executable Templates

Configuration requiring logic is expressed in executable templates.

An executable template is a script which accepts configuration as a JSON string on standard in, and writes a config file to standard out.

The script should exit non-zero if it encounters a problem, so that os-apply-config knows what's up.

The output of the script will be written to the path corresponding to the executable template's path in the template tree.


```ruby
#!/usr/bin/env ruby
require 'json'
params = JSON.parse STDIN.read
puts "connection = mysql://#{c['keystone']['database']['user']}:#{c['keystone']['database']['password']}@#{c['keystone']['database']['host']}/keystone"
```

You could even embed mustache in a heredoc, and use that:
```ruby
#!/usr/bin/env ruby
require 'json'
require 'mustache'
params = JSON.parse STDIN.read

template = <<-eos
[sql]
connection = mysql://{{keystone.database.user}}:{{keystone.database.password}}@{{keystone.database.host}}/keystone

[log]
...
eos

# tweak params here...

puts Mustache.render(template, params)
```

# Quick Start
```bash
# install it
sudo pip install -U git+git://github.com/stackforge/os-config-applier.git

# grab example templates
git clone git://github.com/stackforge/triple-image-elements /tmp/config

# run it
os-apply-config -t /tmp/config/elements/nova/os-config-applier/ -m /tmp/config/elements/boot-stack/config.json -o /tmp/config_output
```
