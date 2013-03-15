try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'name': 'os-config-applier',
    'description': 'applies configuration from cloud metadata.',
    'author': 'echohead',
    'author_email': 'tim.miller.0@gmail.com',
    'url': 'http://github.com/tripleo/os-config-applier',
    'version': '0.3',
    'install_requires': ['nose'],
    'packages': ['os_config_applier'],
    'scripts': [],
    'install_requires': ['pystache', 'anyjson'],
#    'long_description': open('README.md').read(),
    'entry_points': {
        'console_scripts': [
            'os-config-applier = os_config_applier.os_config_applier:main']
    }
}

setup(**config)
