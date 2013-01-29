try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'name': 'cornfig'
    'description': 'applies cornfiguration from cloud metadata.',
    'author': 'echohead',
    'url': 'github.com/echohead/cornfig',
    'version': '0.1',
    'install_requires': ['nose'],
    'packages': ['cornfig'],
    'scripts': [],
    'install_requires': ['pystache']
}

setup(**config)
