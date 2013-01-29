cornfig
=======

Apply configuration from cloud metadata.


# What does it do?

it turns a cloud-metdata file like this:
```
{"config": {"keystone": {"database": {"host": "127.0.0.1", "user": "keystone", "password": "foobar"}}}}
```
into service config files like this:
```
[sql]
connection = mysql://keystone:foobar@127.0.0.1/keystone
...other settings...
```

# But HOW??

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

An executable template is a script which accepts parameters in environment variables, and writes a config file to standard out.

The output of the script will be written to the path corresponding to the executable template's path in the template tree.

e.g.
```
#/bin/sh
echo "[sql]"
echo "connection = mysql://$keystone_database_user:$keystone_database_password@$keystone_database_user/keystone"
```



