#####
Chump
#####

.. image:: https://badge.fury.io/py/chump.svg
	:target: https://badge.fury.io/py/chump
	:alt: PyPI Version

.. image:: https://readthedocs.org/projects/chump/badge/?version=latest
	:target: https://readthedocs.org/projects/chump/?badge=latest
	:alt: Documentation Status

Chump is an Apache2 Licensed, fully featured API wrapper for
`Pushover <https://pushover.net>`_:

.. code-block:: pycon

	>>> from chump import Application
	>>> app = Application('vmXXhu6J04RCQPaAIFUR6JOq6jllP1')
	>>> app.is_authenticated
	True
	>>> user = app.get_user('KAGAw2ZMxDJVhW2HAUiSZEamwGebNa')
	>>> user.is_authenticated, user.devices
	(True, set([u'iPhone']))
	>>> message = user.send_message("What's up, dog?")
	>>> message.is_sent, message.id, unicode(message.sent_at)
	(True, u'7LjjD6bK8hgqdK6aJzZUblOPPH9cVpjZ', u'2005-10-05 07:50:40+00:00')


Installation
============

Install chump just like everything else:

.. code-block:: bash

	$ pip install chump


Documentation
=============

Full documentation is available at
`ReadTheDocs <https://chump.readthedocs.org/en/latest/>`_.
