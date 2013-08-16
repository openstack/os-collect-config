os-collect-config
=================

Collect configuration from cloud metadata sources.


# What does it do?

It collects data from defined configuration sources and runs a defined hook whenever the metadata has changed.

# Usage

You must define what sources to collect configuration data from in /etc/os-collect-config/sources.ini

The format of this file is
```ini
[default]
command=os-refresh-config

[cfn]
metadata_url=http://192.0.2.99:8000/v1/
access_key_id = ABCDEFGHIJLMNOP01234567890
secret_access_key = 01234567890ABCDEFGHIJKLMNOP
path = MyResource
stack_name = my.stack
```

These sources will be polled and whenever any of them changes, default.command will be run. OS_CONFIG_FILES will be set in the environment as a colon (":") separated list of the current copy of each metadata source. So in the example above, "os-refresh-config" would be executed with something like this in OS_CONFIG_FILES:

```
/var/run/os-collect-config/ec2.json:/var/run/os-collect-config/cfn.json
```

The previous version of the metadata from a source (if available) is present at $FILENAME.last.

When run without a command, the metadata sources are printed as a json document.

# Quick Start

sudo pip install -U git+git://github.com/stackforge/os-collect-config.git

# run it on an OpenStack instance with access to ec2 metadata:
os-collect-config
```

That should print out a json representation of the entire ec2 metadata tree.
