# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import os
import sys

sys.path.insert(0, os.path.abspath('..'))
import chump


project = chump.__title__
copyright = chump.__copyright__[10:]
version = release = chump.__version__
language = 'English'

extensions = [
	'sphinx.ext.autodoc',
	'sphinx.ext.intersphinx',
	'sphinx.ext.viewcode',
	'sphinx.ext.coverage'
]

autodoc_member_order = 'bysource'
intersphinx_mapping = {'python': ('http://docs.python.org/3', None)}

exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'

add_function_parentheses = True
add_module_names = True
pygments_style = 'sphinx'

htmlhelp_basename = '{project}_docs'.format(project=project.lower())
html_title = "{project} {version} Documentation".format(project=project, version=version)
html_short_title = project
html_last_updated_fmt = ''
html_show_sphinx = False

if os.environ.get('READTHEDOCS', None) == 'True':
	html_theme = 'default'

else:
	_, user, repo = chump.__homepage__.rsplit('/', 2)
	
	html_theme_options = {
		'github_user': user,
		'github_repo': repo,
		'description': 'The Best API Wrapper for Pushover.',
		'sidebar_collapse': 'false'
	}
