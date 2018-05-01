from setuptools import setup

setup(
  name = 'tcore',
  version = '0.1.0',
  description = 'theCore C++ embedded framework CLI tools',
  author = 'Max Payne',
  scripts=['tcore'],
  author_email = 'forgge@gmail.com',
  url = 'https://github.com/theCore-embedded/tcore_cli',
  download_url = 'https://github.com/theCore-embedded/tcore_cli/archive/v0.1.0.tar.gz',
  keywords = ['embedded', 'cpp', 'c++', 'the_core'],
  classifiers = [],
  install_requires = [ 'tabulate', 'requests', 'coloredlogs' ],
  license = 'MPL'
)
