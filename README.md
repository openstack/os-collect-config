os-apply-config
===============

Collect configuration from cloud metadata sources.


# What does it do?

It collects data from defined configuration sources and runs a defined hook whenever the metadata has changed.

# Usage

You must define what sources to collect configuration data from in /etc/os-collect-config/sources.ini

The format of this file is
```ini
[default]
command=os-refresh-config

[ec2]
type=ec2-metadata

[cfn]
type=cloudformation
```

These sources will be processed in order, and whenever any of them changes, default.command will be run. OS_CONFIG_FILES will be set in the environment as a colon (":") separated list of the current copy of each metadata source. So in the example above, "os-refresh-config" would be executed with something like this in OS_CONFIG_FILES:

```
/var/run/os-collect-config/ec2.json:/var/run/os-collect-config/cfn.json
```

The sources can also be crafted using runtime arguments:

```
os-collect-config --command=os-refresh-config --source ec2:type=ec2-metadata --source cfn:type=cloudformation
```

# Quick Start

sudo pip install -U git+git://github.com/stackforge/os-collect-config.git

# run it on an OpenStack instance with access to ec2 metadata:
os-collect-config --print --source "ec2:ec2-metadata"
```

That should print out a json representation of the entire ec2 metadata tree.
