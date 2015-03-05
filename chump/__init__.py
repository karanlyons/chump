# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
import re
from calendar import timegm
from datetime import datetime, timedelta
from email.utils import parsedate_tz

import requests


VERSION = (1, 4, 0)

__title__ = 'Chump'
__version__ = '.'.join((str(i) for i in VERSION)) # str for compatibility with setup.py under Python 3.
__author__ = 'Karan Lyons'
__contact__ = 'karan@karanlyons.com'
__homepage__ = 'https://github.com/karanlyons/chump'
__license__ = 'Apache 2.0'
__copyright__ = 'Copyright 2013 Karan Lyons'


logger = logging.getLogger(__name__)

try:
	logger.addHandler(logging.NullHandler())

except AttributeError:
	class NullHandler(logging.Handler):
		def emit(self, record):
			pass
	
	logger.addHandler(NullHandler())


try:
	from pytz import utc

except ImportError:
	logger.warning('pytz is not installed; datetime\'s may be inaccurate.')
	
	from datetime import tzinfo
	
	class UTC(tzinfo):
		ZERO = timedelta(0)
		
		def utcoffset(self, dt):
			return self.ZERO
		
		def tzname(self, dt):
			return 'UTC'
		
		def dst(self, dt):
			return self.ZERO
		
		def localize(self, dt):
			return dt.replace(tzinfo=self)
		
		def __unicode__(self):
			return 'UTC'
		
		def __repr__(self):
			return '<UTC>'
	
	utc = UTC()


def utc_now():
	return utc.localize(datetime.utcnow())


def datetime_to_epoch(dt):
	if dt.tzinfo is None: # We got a naïve datetime. Assume it's UTC.
		dt = utc.localize(dt)
	
	return timegm(dt.astimezone(utc).timetuple())


def epoch_to_datetime(e):
	return utc.localize(datetime.utcfromtimestamp(int(e)))


def http_date_to_datetime(d):
	d_tuple = parsedate_tz(d)
	
	dt = utc.localize(datetime(*d_tuple[:6]))
	
	if d_tuple[9]: # We've got a timezone offset.
		dt += timedelta(seconds=d_tuple[9])
	
	return dt


LOWEST = -2 #: Message priority: No sound, no vibration, no banner.
LOW = -1 #: Message priority: No sound, no vibration, banner.
NORMAL = 0 #: Message priority: Sound, vibration, and banner if outside of user's quiet hours.
HIGH = 1 #: Message priority: Sound, vibration, and banner regardless of user's quiet hours.
EMERGENCY = 2 #: Message priority: Sound, vibration, and banner regardless of user's quiet hours, and re-alerts until acknowledged.


TOKEN_RE = re.compile(r'^[a-zA-Z0-9]{30}$') # Matches correct application/user tokens.


ENDPOINT = 'https://api.pushover.net/1/'
REQUESTS = {
	'message': {
		'method': 'post',
		'path': 'messages.json',
	},
	'validate': {
		'method': 'post',
		'path': 'users/validate.json',
	},
	'sound': {
		'method': 'get',
		'path': 'sounds.json',
	},
	'receipt': {
		'method': 'get',
		'path': 'receipts/'
	},
	'cancel': {
		'method': 'post',
		'path': 'receipts/'
	},
}


class APIError(Exception):
	"""
	Pushover errors eponysterically end up here.
	
	:param dict json: The json response from the endpoint.
	
	"""
	
	def __init__(self, url, request, response, timestamp):
		self.url = url #: A :py:obj:`str` of the URL of the original request.
		self.request = request #: A :py:obj:`dict` of the original request payload.
		self.response = response #: A :py:obj:`dict` of the json response from the endpoint.
		self.timestamp = timestamp #: A :py:class:`datetime.datetime` of when this error was raised.
		
		self.id = self.response['request'] #: A :py:obj:`str` of the request's id.
		self.status = self.response['status'] #: A :py:obj:`int` of the status code.
		self.errors = self.response['errors'] #: A :py:obj:`list` of human readable error messages as :py:obj:`str`s.
		
		#: A :py:class:`dict` of the request's original arguments that the endpoint didn't like as :py:obj:`str`s and why, also as :py:obj:`str`s.
		self.bad_inputs = dict([(key, value) for key, value in self.response.iteritems() if key not in set(('errors', 'status', 'receipt', 'request'))])
		
		self.receipt = self.response.get('receipt', None) #: A :py:obj:`str` of the message's receipt if it was an emergency message, otherwise ``None``.
		
		logger.debug('APIError raised. Endpoint response was {}'.format(self.response))
	
	def __unicode__(self):
		return "({id}) {errors}".format(id=self.id, errors=", ".join(self.errors))
	
	def __repr__(self):
		return "APIError(url={url!r}, request={request!r}, response={response!r}, timestamp={timestamp!r})".format(**vars(self))


class Application(object):
	"""
	The Pushover app in use.
	
	:param string token: The app's API token.
	
	"""
	
	def __init__(self, token):
		self.is_authenticated = False #: A :py:obj:`bool` indicating whether the app has been authenticated.
		self.sounds = None #: If authenticated, a :py:class:`dict` of available notification sounds, otherwise ``None``.
		self.token = unicode(token) #: The app's API token.
		
		self.limit = None #: If a message has been sent, a :py:obj:`int` representing the application's monthly message limit, otherwise ``None``.
		self.remaining = None #: If a message has been sent, a :py:obj:`int` representing the application's remaining message allotment, otherwise ``None``.
		self.reset = None #: If a message has been sent, :py:class:`datetime.datetime` representing when the application's monthly message limit will reset, otherwise ``None``.
	
	def __setattr__(self, name, value):
		super(Application, self).__setattr__(name, value)
		
		if name == 'token':
			if not TOKEN_RE.match(value):
				raise ValueError('Bad application token: expected unicode matching [a-zA-Z0-9]{30}, got {!r}'.format(value))
			
			else:
				self._authenticate()
	
	def __unicode__(self):
		return "Pushover App: {token}".format(token=self.token)
	
	def __repr__(self):
		return 'Application(token={token!r})'.format(token=self.token)
	
	def _authenticate(self):
		"""
		Authenticates the supplied app token.
		
		"""
		
		self.is_authenticated = True
		
		try:
			self._request('validate')
		
		except APIError as error:
			if 'token' in error.bad_inputs:
				self.is_authenticated = False
		
		if self.is_authenticated and self.sounds is None:
			self.sounds = self._request('sound')[0]['sounds']
	
	def get_user(self, token):
		"""
		Returns a :class:`~chump.User` attached to the
		:class:`~chump.Application` instance.
		
		:param string token: User API token.
		:rtype: :class:`~chump.User`.
		
		"""
		
		return User(self, token)
	
	def _request(self, request, data=None, url=None):
		"""
		Handles the request/response cycle to Pushover's API endpoint. Request
		types are defined in :attr:`.requests`.
		
		:param string request: 'message', 'validate', 'sound', or 'receipt'.
		:param dict data: (optional) Payload to send to endpoint.
			Defaults to ``None``.
		:param string url: (optional) URL to send payload to. Defaults to the
			URL specified by :param:request.
		
		:returns: An :py:obj:`tuple` of (``response``, ``timestamp``), where
			``response`` is a :py:obj:`dict` representing the ``json`` response
			and ``timestamp`` is a :py:class:`datetime.datetime` representing
			the time the response was returned.
		:rtype: :py:obj:`tuple`.
		
		:raises: :exc:`~chump.APIError` when request or response is invalid.
		
		"""
		
		if data is None:
			data = {}
		
		data['token'] = self.token
		
		if url is None:
			url = ENDPOINT + REQUESTS[request]['path']
		
		logger.debug('Making request ({request}): {data}'.format(request=request, data=data))
		
		response = getattr(requests, REQUESTS[request]['method'])(url, params=data)
		
		logger.debug('Response ({status_code}):\n{headers}\n{_content}'.format(**vars(response)))
		
		if response.status_code == 200 or 400 <= response.status_code < 500:
			json = response.json()
			timestamp = http_date_to_datetime(response.headers['date'])
			
			if 400 <= response.status_code < 500:
				raise APIError(url, data, json, timestamp)
			
			else:
				if request == 'message':
					self.limit = int(response.headers['X-Limit-App-Limit'])
					self.remaining = int(response.headers['X-Limit-App-Remaining'])
					self.reset = epoch_to_datetime(response.headers['X-Limit-App-Reset'])
				
				return (json, timestamp)
		
		else:
			raise APIError(url, data, {
				'request': None,
				'status': 0,
				'errors': ['unknown error ({code})'.format(code=response.status_code)],
			}, timestamp)


class User(object):
	"""
	A Pushover user. The user is tied to a specific
	:class:`~chump.Application` app, which can be changed later by
	setting :attr:`.app`.
	
	:param app: The Pushover app to send messages with.
	:type app: :class:`~chump.Application`
	:param string token: The user's API token.
	
	"""
	
	def __init__(self, app, token):
		self.app = app #: The Pushover app to send messages with.
		self.is_authenticated = None #: If :attr:`.app` has been authenticated, a :py:obj:`bool` indicating whether the user has been authenticated, otherwise ``None``.
		self.devices = None #: If authenticated, a :py:class:`set` of the user's devices, otherwise None.
		self.token = unicode(token) #: The user's API token.
	
	def __setattr__(self, name, value):
		super(User, self).__setattr__(name, value)
		
		if name == 'token':
			if not TOKEN_RE.match(value):
				raise ValueError('Bad user token: expected unicode matching [a-zA-Z0-9]{30}, got {!r}'.format(value))
			
			else:
				self._authenticate()
	
	def __unicode__(self):
		return "Pushover User: {token}".format(token=self.token)
	
	def __repr__(self):
		return 'User(app={app!r}, token={token!r})'.format(**vars(self))
	
	def _authenticate(self):
		"""
		Authenticates the supplied user token.
		
		"""
		
		try:
			response, _ = self.app._request('validate', {'user': self.token})
		
		except APIError as error:
			if 'token' in error.bad_inputs: # We can't authenticate users with a bad API token.
				self.app.is_authenticated = False
				self.is_authenticated = None
				self.devices = None
			
			elif 'user' not in error.bad_inputs or error.bad_inputs['user'].startswith('valid'):
				self.is_authenticated = True
				self.devices = set()
			
			else:
				self.is_authenticated = False
				self.devices = None
		
		else:
			self.is_authenticated = True
			self.devices = set(response['devices'])
	
	def create_message(self, message, html=False, title=None, timestamp=None,
		               url=None, url_title=None, device=None, priority=NORMAL,
		               callback=None, retry=30, expire=86400, sound=None):
		"""
		Creates a message to the User with :attr:`.app`.
		
		:param string message: Body for the message.
		:param string title: (optional) Title for the message. Defaults
			to ``None``.
		:param timestamp: (optional) Date and time to give the message. Defaults
			to the time the message was created.
		:type timestamp: :py:class:`datetime.datetime` or :py:obj:`int`
		:param string url: (optional) url to include in the message. Defaults
			to ``None``.
		:param string device: (optional) device from
			:attr:`.devices` to send to. Defaults to all of the user's devices.
		:param int priority: (optional) priority for the message. The
			constants :const:`~chump.LOWEST`, :const:`~chump.LOW`,
			:const:`~chump.NORMAL`, :const:`~chump.HIGH`, and
			:const:`~chump.EMERGENCY` may be used for convenience. Defaults
			to :const:`~chump.NORMAL`.
		:param string callback: (optional) If priority is
			:const:`~chump.EMERGENCY`, the url to ping when the message
			is acknowledged. Defaults to ``None``.
		:param int retry: (optional) If priority is :const:`~chump.EMERGENCY`,
			the number of seconds to wait between realerting the user. Must be
			greater than 30. Defaults to 30.
		:param int expire: (optional) If priority is
			:const:`~chump.EMERGENCY`, the number of seconds to retry before
			giving up on alerting the user. Must be less than 86400. Defaults
			to 86400.
		:param string sound: (optional) The sound from :attr:`.app.sounds`
			to play when the message is received. Defaults to the user's
			default sound.
		
		:returns: An unsent message.
		:rtype: :class:`~chump.Message` or :class:`EmergencyMessage`.
		
		"""
		
		kwargs = locals().copy()
		kwargs.pop('self')
		
		if priority == 2:
			message_class = EmergencyMessage
			kwargs.pop('priority')
		
		else:
			message_class = Message
			[kwargs.pop(key) for key in ('callback', 'retry', 'expire')]
		
		return message_class(self, **kwargs)
	
	def send_message(self, message, html=False, title=None, timestamp=None,
		             url=None, url_title=None, device=None, priority=NORMAL,
		             callback=None, retry=30, expire=86400, sound=None):
		"""
		Does the same as :meth:`.create_message`, but sends them all with
		:attr:`.app` as well.
		
		:returns: A sent message.
		:rtype: :class:`~chump.Message` or :class:`EmergencyMessage`.
		
		"""
		
		message = self.create_message(
			message, html, title, timestamp,
			url, url_title, device, priority,
			callback, retry, expire, sound
		)
		
		message.send()
		
		return message


class Message(object):
	"""
	A Pushover message. The message is tied to a specific
	:class:`~chump.Application` app, and :class:`~chump.User` user. All
	parameters are exposed as attributes on the message, for convenience.
	
	:param user: The user to send the message to.
	:type user: :class:`~chump.User`
	
	All other arguments are the same as in :meth:`User.create_message`.
	
	"""
	
	def __init__(self, user, message, html=False, title=None, timestamp=None,
	             url=None, url_title=None, device=None, priority=0, sound=None):
		self.user = user
		self.message = message
		self.html = html
		self.title = title
		self.timestamp = timestamp
		self.url = url
		self.url_title = url_title
		self.device = device
		self.priority = priority
		self.sound = sound
		
		self.id = None #: The id of the sent message.
		
		self.is_sent = False #: A :py:obj:`bool` indicating whether the message has been sent.
		self.sent_at = None #: A :py:class:`datetime.datetime` of when the message was sent, otherwise ``None``.
		
		self.error = None #: A :exc:`~chump.APIError` if there was an error sending the message, otherwise ``None.
	
	def __setattr__(self, name, value):
		if name == 'message' and len(value) == 0:
			raise ValueError('Bad message: must be > 0 characters, was 0')
		
		if name == 'html':
			try:
				value_type = type(value)
				value = int(value)
			
			except ValueError:
				raise ValueError('Bad html: expected bool, got {}'.format(value_type))
			
			else:
				if value not in (0, 1):
					raise ValueError('Bad html: expected bool, got {} whose not coercible to (0, 1)'.format(value_type))
		
		if value and name in set(('message', 'title', 'url', 'url_title', 'device', 'callback', 'sound', 'priority', 'retry', 'expire')):
			if name in set(('message', 'title', 'url', 'url_title', 'device', 'callback', 'sound')):
				try:
					value = unicode(value)
				
				except ValueError:
					raise ValueError('Bad {name}: expected unicode, got {type}'.format(name=name, type=type(value)))
			
			elif name in set(('priority', 'retry', 'expire')):
				try:
					value = int(value)
				
				except ValueError:
					raise ValueError('Bad {name}: expected int, got {type}'.format(name=name, type=type(value)))
			
			if name == 'title' and len(value) > 250:
				raise ValueError('Bad title: must be <= 250 characters, was {}'.format(len(value)))
			
			elif name == 'message' and len(value) > 1024:
				raise ValueError('Bad message: must be <= 1024 characters, was {}'.format(len(value)))
			
			elif name == 'url' and len(value) > 512:
				raise ValueError('Bad url: must be <= 512 characters, was {}'.format(len(value)))
			
			elif name == 'url_title' and len(value) > 100:
				raise ValueError('Bad url_title: must be <= 100 characters, was {}'.format(len(value)))
			
			elif name == 'timestamp':
				try:
					if isinstance(value, datetime):
						value = datetime_to_epoch(value)
					
					else:
						value = epoch_to_datetime(value)
				
				except (TypeError, ValueError):
					raise TypeError('Bad timestamp: expected valid int or datetime, got {}.'.format(type(value)))
			
			elif name == 'priority':
				try:
					if not -2 <= int(value) <= 2:
						raise ValueError('Bad priority: must be between -2 and 2, was {!r}'.format(value))
				
				except TypeError:
					raise TypeError('Bad priority: expected int, got {}.'.format(type(value)))
			
			elif name == 'sound' and value not in self.user.app.sounds:
				raise ValueError('Bad sound: must be in ({sounds}), was {value!r}'.format(sounds=', '.join(self.user.app.sounds.keys()), value=value))
			
			elif name == 'device' and value not in self.user.devices:
				raise ValueError('Bad device: must be in ({devices}), was {value!r}'.format(devices=', '.join(self.user.devices), value=value))
		
		super(Message, self).__setattr__(name, value)
	
	def send(self):
		"""
		Sends the message. If called after the message has been sent,
		resends it.
		
		"""
		
		self.id = None
		
		self.is_sent = False
		self.sent_at = None
		
		self.error = None
		
		data = {
			'user': self.user.token,
		}
		
		for kwarg in ('message', 'html', 'title', 'timestamp', 'url', 'url_title', 'device', 'priority', 'sound', 'retry', 'expire', 'callback'):
			if hasattr(self, kwarg) and getattr(self, kwarg):
				data[kwarg] = getattr(self, kwarg)
		
		try:
			# We've got to store this somewhere so that EmergencyMessage can check it for a receipt.
			self._response, self.sent_at = self.user.app._request('message', data)
		
		except APIError as error:
			self.is_sent = False
			self.error = error
			
			# This could be handled by calling {user,app}._authenticate, but that's two extra requests.
			if 'token' in error.bad_inputs:
				self.user.app.is_authenticated = False
				self.user.is_authenticated = None
			
			elif 'user' in error.bad_inputs:
				self.user.is_authenticated = False
		
		else:
			self.is_sent = True
			self.id = self._response['request']
		
		return self.is_sent
	
	def __unicode__(self):
		if self.title:
			return "({title}) {message}".format(**vars(self))
		
		else:
			return self.message


class EmergencyMessage(Message):
	"""
	An emergency Pushover message, (that is, a message with the priority of
	:const:`~chump.EMERGENCY`).
	
	All arguments are the same as in :class:`~chump.Message`, with the
	additions of ``call_back``, ``retry``, and ``timeout``, which
	are all, too, as defined in :meth:`User.create_message`.
	
	"""
	
	def __init__(self, user, message, html=False, title=None, timestamp=None,
		         url=None, url_title=None, device=None, sound=None,
		         callback=None, retry=30, expire=86400):
		priority = EMERGENCY
		
		super(EmergencyMessage, self).__init__(
			user, message, html, title, timestamp, url,
			url_title, device, priority, sound
		)
		
		self.callback = callback
		self.retry = retry
		self.expire = expire
		
		self.receipt = None #: The receipt returned by the endpoint, for polling.
		self.last_polled_at = None #: A :py:class:`datetime.datetime` of when the message was last polled.
		
		self.last_delivered_at = None #: A :py:class:`datetime.datetime` of when the message was last delivered.
		
		self.is_acknowledged = None #: A :py:obj:`bool` indicating whether the message has been acknowledged.
		self.acknowledged_at = None #: A :py:class:`datetime.datetime` of when the message was acknowledged, otherwise ``None``.
		self.acknowledged_by = None #: A :class:`~chump.User` of the first user to have acknowledged the notification, otherwise :py:obj:`None`.
		
		self.is_expired = None #: A :py:obj:`bool` indicating whether the message has expired.
		self.expires_at = None #: A :py:class:`datetime.datetime` of when the message expires.
		
		self.is_called_back = None #: A :py:obj:`bool` indicating whether the message has been called back.
		self.called_back_at = None #: A :py:class:`datetime.datetime` of when the message was called back, otherwise ``None``.
	
	def __setattr__(self, name, value):
		if name in ('retry', 'expire'):
			try:
				value = int(value)
			
			except ValueError:
				raise ValueError('Bad {name}: expected int, got {type}'.format(name=name, type=type(value)))
		
		if name == 'retry' and value < 30:
			raise ValueError('Bad retry: must be >= 30, was {}'.format(value))
		
		elif name == 'expire' and not 0 < value <= 86400:
			raise ValueError('Bad expire: must be <= 86400 and >= 0, was {}'.format(value))
		
		super(EmergencyMessage, self).__setattr__(name, value)
	
	def send(self):
		self.receipt = None
		
		self.last_delivered_at = None
		
		self.is_acknowledged = None
		self.acknowledged_at = None
		self.acknowledged_by = None
		
		self.is_expired = None
		self.expires_at = None
		
		self.is_called_back = None
		self.called_back_at = None
		
		super(EmergencyMessage, self).send()
		
		if self.is_sent:
			self.receipt = self._response['receipt']
		
		self.poll() # Poll immediately to fill attributes.
		
		return self.is_sent
	
	def poll(self):
		"""
		Polls for the results of the sent message. If the message has not been
		sent, does so.
		
		:returns: A boolean indicating if the message has not expired, called
			back nor been acknowledged, or ``None`` if the message has no
			receipt with which to poll.
		:rtype: :py:obj:`bool` or ``None``.
		
		"""
		
		if not self.is_sent:
			self.send()
		
		if self.receipt:
			if not (self.is_expired and self.is_acknowledged and self.is_called_back):
				self._response, self.last_polled_at = self.user.app._request('receipt', url='{endpoint}{path}{receipt}.json'.format(
					endpoint=ENDPOINT,
					path=REQUESTS['receipt']['path'],
					receipt=self.receipt
				))
				
				for attr in ('acknowledged', 'expired', 'called_back'):
					setattr(self, 'is_{}'.format(attr), bool(self._response[attr]))
					
				for attr_at in ('acknowledged_at', 'expires_at', 'called_back_at', 'last_delivered_at'):
					if self._response[attr_at]:
						setattr(self, attr_at, epoch_to_datetime(self._response[attr_at]))
				
				if self._response['acknowledged_by']:
					if self._response['acknowledged_by'] == self.user.token:
						self.acknowledged_by = self.user
					
					else:
						self.acknowledged_by = self.user.app.get_user(self._response['acknowledged_by'])
			
			return not (self.is_acknowledged or self.is_expired)
		
		else:
			return None
	
	def cancel(self):
		"""
		Cancels the request for acknowledgement of a sent message.
		
		"""
		
		self._response, self.last_polled_at = self.user.app._request('cancel', url='{endpoint}{path}{receipt}/cancel.json'.format(
			endpoint=ENDPOINT,
			path=REQUESTS['receipt']['path'],
			receipt=self.receipt
		))
		
		return bool(self._response['status'])
