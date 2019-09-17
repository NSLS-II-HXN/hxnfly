from __future__ import print_function
import versioneer

try:
    from setuptools import setup, find_packages
except ImportError:
    try:
        from setuptools.core import setup
    except ImportError:
        from distutils.core import setup


setup(name='hxnfly',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      author='HXN',
      packages=['hxnfly', 'hxnfly.callbacks'],
      package_data={'hxnfly': ['scripts/*.txt']})
