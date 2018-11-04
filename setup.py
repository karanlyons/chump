# -*- coding: utf-8 -*-

import sys

try: from setuptools import setup
except ImportError: from distutils.core import setup

import chump


read_mode = 'r' if sys.version_info >= (3,) else 'rU'


setup(
	name="chump",
	version=chump.__version__,
	description="A fully featured API wrapper for Pushover.",
	long_description=open('README.rst', read_mode).read(),
	long_description_content_type='text/x-rst',
	keywords='pushover api push notifications',
	author=chump.__author__,
	author_email=chump.__contact__,
	url=chump.__homepage__,
	license=chump.__license__,
	packages=['chump'],
	package_dir={'chump': 'chump'},
	package_data={'': ['README.rst', 'HISTORY.rst', 'LICENSE']},
	include_package_data=True,
	zip_safe=False,
	python_requires='>=2.7',
	project_urls={
		'Source': chump.__homepage__,
		'Documentation': 'https://chump.readthedocs.io',
		'Tracker': chump.__homepage__ + '/issues',
	},
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'License :: OSI Approved :: Apache Software License',
		'Programming Language :: Python',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.0',
		'Programming Language :: Python :: 3.1',
		'Programming Language :: Python :: 3.2',
		'Programming Language :: Python :: 3.3',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: 3.6',
		'Programming Language :: Python :: 3.7',
		'Programming Language :: Python :: Implementation :: CPython',
		'Programming Language :: Python :: Implementation :: PyPy',
	],
)
