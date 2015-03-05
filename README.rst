#####
Chump
#####

.. image:: https://img.shields.io/pypi/v/chump.svg
	:target: https://pypi.python.org/pypi/chump
	:alt: PyPI Version

.. image:: https://img.shields.io/badge/docs-latest-blue.svg
	:target: https://chump.readthedocs.org/en/latest/
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
	(True, {'iPhone'})
	>>> message = user.send_message("What's up, dog?")
	>>> message.is_sent, message.id, str(message.sent_at)
	(True, '7LjjD6bK8hgqdK6aJzZUblOPPH9cVpjZ', '2005-10-05 07:50:40+00:00')


Installation
============

Install chump just like everything else:

.. code-block:: bash

	$ pip install chump


Documentation
=============

Full documentation is available at
`ReadTheDocs <https://chump.readthedocs.org/en/latest/>`_.
