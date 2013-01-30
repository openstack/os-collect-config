try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'name': 'cornfig',
    'description': 'applies cornfiguration from cloud metadata.',
    'author': 'echohead',
    'author_email': 'tim.miller.0@gmail.com',
    'url': 'http://github.com/echohead/cornfig',
    'version': '0.3',
    'install_requires': ['nose'],
    'packages': ['cornfig'],
    'scripts': [],
    'install_requires': ['pystache', 'anyjson'],
#    'long_description': open('README.md').read(),
    'entry_points': {
      'console_scripts': ['cornfig = cornfig.cornfig:main']
    }
}

setup(**config)
