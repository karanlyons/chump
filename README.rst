#####
Chump
#####

.. image:: https://badge.fury.io/py/chump.png
	:target: http://badge.fury.io/py/chump

Chump is an Apache2 Licensed, fully featured API wrapper for
`Pushover <https://pushover.net>`_:

.. code-block:: pycon

	>>> from chump import Pushover
	>>> app = Pushover('vmXXhu6J04RCQPaAIFUR6JOq6jllP1')
	>>> app.is_authenticated
	True
	>>> user = app.get_user('KAGAw2ZMxDJVhW2HAUiSZEamwGebNa')
	>>> user.is_authenticated, user.devices
	(True, set([u'iPhone']))
	>>> message = user.send_message("What's up, dog?")
	>>> message.is_sent, message.id, message.sent_at
	(True, u'7LjjD6bK8hgqdK6aJzZUblOPPH9cVpjZ', '2005-10-05 07:50:40+00:00')


Installation
============

Install chump just like everything else:

.. code-block:: bash

	$ pip install chump


Documentation
=============

Full documentation is available at
`ReadTheDocs <https://readthedocs.org/projects/chump/>`_:
