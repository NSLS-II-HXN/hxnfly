from __future__ import print_function

try:
    from setuptools import setup, find_packages
except ImportError:
    try:
        from setuptools.core import setup
    except ImportError:
        from distutils.core import setup


setup(name='hxnfly',
      version="0.0.2",
      author='HXN',
      packages=['hxnfly', 'hxnfly.callbacks'],
      #packages=['hxnfly', 'hxnfly.callbacks', 'hxnfly.scripts'],
      package_data={'hxnfly': ['scripts/*.txt']},
      )
