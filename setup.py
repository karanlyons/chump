#!/usr/bin/env python

import chump


try:
	from setuptools import setup

except ImportError:
	from distutils.core import setup

install_requires = []
for line in open('requirements.txt', 'rbU').readlines():
	if line and line not in '\n' and not line.startswith(('#', '-')):
		install_requires.append(line.replace('\n', ''))

setup(
	name='chump',
	version=chump.__version__,
	description='A fully featured API wrapper for Pushover.',
	long_description='\n\n'.join([open('README.rst', 'rbU').read(), open('HISTORY.rst', 'rbU').read()]),
	author=chump.__author__,
	author_email=chump.__contact__,
	url=chump.__homepage__,
	license=open('LICENSE', 'rbU').read(),
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
		'Programming Language :: Python :: 2.7',
	),
)
