#####
Chump
#####

.. image:: https://badge.fury.io/py/chump.svg
	:target: https://badge.fury.io/py/chump
	:alt: PyPI Version

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
	>>> message.is_sent, message.id, str(message.sent_at)
	(True, u'7LjjD6bK8hgqdK6aJzZUblOPPH9cVpjZ', '2005-10-05 07:50:40+00:00')


Installation
============

Install chump just like everything else:

.. code-block:: bash

	$ pip install chump


Usage Examples
==============

Chump's meant to be easy to use. Sending a message is just as simple as in the
example above, but there's more you can do.


Creating and sending a message yourself
---------------------------------------

If you'd like to send messages yourself, just swap out
:meth:`~chump.User.send_message`
for :meth:`~chump.User.create_message`:

.. code-block:: pycon

	>>> message = user.create_message("Happy birthday, chuck!")
	>>> message.is_sent, message.id
	None, None
	>>> message.send()
	True
	>>> message.is_sent, message.id, str(message.sent_at)
	(True, u'fZSrekCvxi2vnpVADWBNchAGrllDi4cZ', '1993-12-17 06:03:45+00:00')


Sending messages with additional parameters
-------------------------------------------

Chump supports all the message parameters outlined in Pushover's
`API Docs <https://pushover.net/api>`_. Any of these parameters can be
optionally supplied as ``kwargs``:

.. code-block:: pycon

	>>> message = user.create_message(
	... 	title="No Crackers, Gromit!",
	... 	message="We've forgotten the crackers!",
	... 	sound='intermission'
	... )
	>>> (str(message), message.sound)
	('(No Crackers, Gromit!) We've forgotten the crackers!', 'intermission')

And Chump will raise the appropriate exceptions if your ``kwargs`` violate the
API restrictions:

.. code-block:: pycon

	>>> message = user.create_message(
	... 	"Gromit, we have a problem!"
	... 	sound='this is not a sound'
	... )
	ValueError: Bad sound: must be in [u'bugle', u'classical', u'pianobar',
		u'echo', u'alien', u'siren', u'spacealarm', u'gamelan', u'bike',
		u'falling', u'cashregister', u'updown', u'pushover', u'magic',
		u'tugboat', u'none', u'incoming', u'intermission', u'cosmic',
		u'persistent', u'mechanical', u'climb'], was 'this is not a sound'

All parameters are exposed as attributes in the :class:`~chump.Message`,
so you can change them later.


Sending an emergency message
----------------------------

Pushover's emergency messages have a few additions over standard messages. They
require dismissal from the user, and if not dismissed they'll keep popping up
every ``retry`` seconds until ``timeout`` seconds from when they were sent.
When the user acknowledges the message, ``callback`` will be pinged by
Pushover's servers, but you can also check in on the message's status by
calling :meth:`~chump.EmergencyMessage.poll`:

.. code-block:: pycon

	>>> message = user.send_message(
	... 	"Do something, Gromit!",
	... 	priority=chump.EMERGENCY
	... )
	>>> message.is_sent, message.id, message.is_acknowledged
	(True, u'eChnqsE5nZyefIbTVMuS9cfDV77mMaN9', False)
	>>> message.poll()
	False
	>>> str(message.acknowledged_at)
	'1995-12-24 06:10:39+00:00'

:meth:`~chump.EmergencyMessage.poll` returns ``True`` whilst the message
has not been acknowledged, so you can use it as an argument in while loops.


Developer Interface
===================

Main Interface
--------------

.. automodule:: chump
	:members: Application, User
	:undoc-members:


Lower-Level Classes
-------------------

.. autoclass:: Message
	:members:
	:undoc-members:

.. autoclass:: EmergencyMessage
	:show-inheritance:
	:members:
	:undoc-members:


Exceptions
----------

.. autoexception:: chump.APIError
	:members:


Constants
---------

.. automodule:: chump
	:members: LOWEST, LOW, NORMAL, HIGH, EMERGENCY


.. include:: ../HISTORY.rst
