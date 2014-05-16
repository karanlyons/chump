# -*- coding: utf-8 -*-

import re
import sys


try:
	from setuptools import setup

except ImportError:
	from distutils.core import setup

install_requires = []
for line in open('requirements.txt', 'rU').readlines():
	if line and line not in '\n' and not line.startswith(('#', '-')):
		install_requires.append(line.replace('\n', ''))

# I'm not proud of this.
init = open('./chump/__init__.py').read()
metadata = dict(re.findall("__([a-z]+)__ = '([^']+)'", init))
metadata['version'] = '.'.join(re.search("VERSION = \((.*)\)", init).group(1).split(', '))

kwargs = {}
if sys.version_info >= (3,):
	kwargs['use_2to3'] = True

setup(
	name="chump",
	version=metadata['version'],
	description="A fully featured API wrapper for Pushover.",
	long_description="\n\n".join([open('README.rst', 'rU').read(), open('HISTORY.rst', 'rU').read()]),
	author=metadata['author'],
	author_email=metadata['contact'],
	url=metadata['homepage'],
	license=open('LICENSE', 'rU').read(),
	packages=['chump'],
	package_dir={'chump': 'chump'},
	package_data={'': ['README.rst', 'HISTORY.rst', 'LICENSE']},
	include_package_data=True,
	install_requires=install_requires,
	zip_safe=False,
	classifiers=(
		'Development Status :: 5 - Production/Stable',
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'License :: OSI Approved :: Apache Software License',
		'Programming Language :: Python',
		'Programming Language :: Python :: 2.6',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.1',
		'Programming Language :: Python :: 3.2',
		'Programming Language :: Python :: 3.3',
	),
	**kwargs
)
