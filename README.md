cornfig
=======

Apply configuration from cloud metadata.


# What does it do?

it turns a cloud-metdata file like this:
```javascript
{"config": {"keystone": {"database": {"host": "127.0.0.1", "user": "keystone", "password": "foobar"}}}}
```
into service config files like this:
```
[sql]
connection = mysql://keystone:foobar@127.0.0.1/keystone
...other settings...
```

# but... but HOW??

Just pass it the path to a directory tree of templates:
```
cornfig /home/me/my_templates
```

# Templates?

The template directory structure should mimic a root filesystem, and contain templates for only those files you want cornfig-ed.

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

If a template is executable it will be treated as an **executable template**.
Otherwise, it will be treated as a **moustache template**.

## Moustache Templates

If you don't need any logic, just some string substitution, use a moustache template:

```
[sql]
connection = mysql://{{keystone.database.user}}:{{keystone.database.password}@{{keystone.database.host}}/keystone
```

## Executable Templates

Configuration requiring logic is best expressed as an executable template.

An executable template is a script which accepts parameters via environment variables or standard in, and writes a config file to standard out.

The output of the script will be written to the path corresponding to the executable template's path in the template tree.

e.g.
```bash
#/bin/sh
echo "[sql]"
echo "connection = mysql://$keystone_database_user:$keystone_database_password@$keystone_database_user/keystone"
```

TODO: the script is passed the contents of the metadata file on stdin, so you can use a higher-level languages, too:
```ruby
#!/usr/bin/env/ruby
require 'json'
c = JSON.parse STDIN.read
puts "connection = mysql://#{c['keystone']['database']['user']}:#{c['keystone']['database']['password']}@#{c['keystone']['database']['host']}/keystone"
```

