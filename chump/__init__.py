# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
import re
import warnings
from calendar import timegm
from datetime import datetime, timedelta
from email.utils import parsedate_tz

try: import ujson as json
except ImportError: import json

from .connection_pool import pool

try: # Python 3
	from urllib.error import HTTPError
	from urllib.parse import urlencode
	unicode = basestring = str

except ImportError: # Python 2
	from urllib import urlencode
	from urllib2 import HTTPError
	def bytes(s, encoding=None, errors=None): return s.encode(encoding, errors)


VERSION = (1, 6, 0)

__title__ = 'Chump'
__version__ = '.'.join((unicode(i) for i in VERSION))
__author__ = 'Karan Lyons'
__contact__ = 'karan@karanlyons.com'
__homepage__ = 'https://github.com/karanlyons/chump'
__license__ = 'Apache 2.0'
__copyright__ = 'Copyright 2013 Karan Lyons'


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


try: # pytz installed
	from pytz import utc
	def utc_now(): return utc.localize(datetime.utcnow())
	def epoch_to_datetime(e): return utc.localize(datetime.utcfromtimestamp(int(e)))

except ImportError:
	try: # dateutil installed
		from dateutil.tz import tzutc
		utc = tzutc()
	
	except ImportError:
		try: # Python >= 3.2
			from datetime import timezone
			utc = timezone.utc
		
		except ImportError: # Python < 3.2
			from datetime import tzinfo
			class UTC(tzinfo):
				ZERO = timedelta(0)
				def utcoffset(self, dt): return self.ZERO
				def tzname(self, dt): return 'UTC'
				def dst(self, dt): return self.ZERO
				def __unicode__(self): return 'UTC'
				__str__ = __unicode__
				def __repr__(self): return 'chump.UTC'
			utc = UTC()
	
	def utc_now(): return datetime.utcnow().replace(tzinfo=utc)
	def epoch_to_datetime(e): return datetime.utcfromtimestamp(int(e)).replace(tzinfo=utc)


def datetime_to_epoch(dt):
	if dt.tzinfo is not None: dt = dt.astimezone(utc)
	else: warnings.warn('Naïve datetime received: assuming UTC', RuntimeWarning)
	return timegm(dt.timetuple())


def http_date_to_datetime(d):
	d_tuple = parsedate_tz(d)
	
	if d_tuple is not None:
		return datetime(*d_tuple[:6]).replace(tzinfo=utc) - timedelta(seconds=d_tuple[9])


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
	
	:param string url: The URL of the original request.
	:param dict request: The original request payload.
	:param dict response: The ``json`` response from the endpoint.
	:param datetime timestamp: When this error was raised.
	
	"""
	
	def __init__(self, url, request, response, timestamp):
		self.url = url #: A :py:obj:`string` of the URL of the original request.
		self.request = request #: A :py:obj:`dict` of the original request payload.
		self.response = response #: A :py:obj:`dict` of the ``json`` response from the endpoint.
		self.timestamp = timestamp #: A :py:class:`~datetime.datetime` of when this error was raised.
		
		self.id = self.response['request'] #: A :py:obj:`string` of the request's id.
		self.status = self.response['status'] #: An :py:obj:`int` of the status code.
		self.errors = self.response['errors'] #: A :py:obj:`list` of human readable error messages as :py:obj:`string`\s.
		
		#: A :py:class:`dict` of the request's original arguments that the endpoint didn't like as :py:obj:`string`\s and why, also as :py:obj:`string`\s.
		self.bad_inputs = {
			key: value
			for key, value in self.response.items()
			if key not in ('errors', 'status', 'receipt', 'request')
		}
		
		#: A :py:obj:`string` of the message's receipt if it was an emergency message, otherwise :py:obj:`None`.
		self.receipt = self.response.get('receipt', None)
		
		logger.debug('APIError raised. Endpoint response was {response}'.format(response=self.response))
	
	def __unicode__(self):
		return "({id}) {errors}".format(id=self.id, errors=", ".join(self.errors))
	
	__str__ = __unicode__
	
	def __repr__(self):
		return "APIError(url={url!r}, request={request!r}, response={response!r}, timestamp={timestamp!r})".format(
			url=self.url,
			request=self.request,
			response=self.response,
			timestamp=self.timestamp,
		)


class Application(object):
	"""
	The Pushover application in use.
	
	:param string token: The application's API token.
	
	"""
	
	def __init__(self, token):
		self.token = token #: A :py:obj:`string` of the application's API token.
		self._is_authenticated = None
		self._sounds = None
		
		self.limit = None #: If a message has been sent, an :py:obj:`int` of the application's monthly message limit, otherwise :py:obj:`None`.
		self.remaining = None #: If a message has been sent, an :py:obj:`int` of the application's remaining message allotment, otherwise :py:obj:`None`.
		self.reset = None #: If a message has been sent, :py:class:`~datetime.datetime` of when the application's monthly message limit will reset, otherwise :py:obj:`None`.
	
	@property
	def is_authenticated(self):
		"""
		A lazily loaded :py:obj:`bool` indicating whether the application
		is authenticated.
		
		"""
		
		if self._is_authenticated is None:
			self._authenticate()
		
		return self._is_authenticated
	
	@is_authenticated.setter
	def is_authenticated(self, value):
		self._is_authenticated = value
	
	@property
	def sounds(self):
		"""
		A lazily loaded :py:class:`dict` of available notification sounds if
		authenticated, otherwise :py:obj:`None`.
		
		"""
		
		if self._sounds is None and self._is_authenticated is not False:
			self._authenticate()
		
		return self._sounds
	
	@sounds.setter
	def sounds(self, value):
		self._sounds = value
	
	def __setattr__(self, name, value):
		if name == 'token':
			try:
				if not TOKEN_RE.match(value):
					raise ValueError('Bad application token: expected string matching [a-zA-Z0-9]{{30}}, got {value!r}'.format(value=value))
				
				else:
					old_token = getattr(self, 'token', None)
			
			except TypeError:
				raise TypeError('Bad token: expected string, got {value_type}'.format(value_type=type(value)))
			
		super(Application, self).__setattr__(name, value)
		
		if name == 'token' and self.token != old_token:
			super(Application, self).__setattr__('_is_authenticated', None)
			super(Application, self).__setattr__('_sounds', None)
	
	def __unicode__(self):
		return "Pushover Application: {token}".format(token=self.token)
	
	__str__ = __unicode__
	
	def __repr__(self):
		return 'Application(token={token!r})'.format(token=self.token)
	
	def __eq__(self, other):
		return isinstance(other, self.__class__) and self.token and self.token == other.token
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __lt__(self, other):
		return NotImplemented
	
	__le__ = __gt__ = __ge__ = __lt__
	
	def _authenticate(self):
		"""
		Authenticates the supplied application token and populates available
		notification sounds.
		
		"""
		
		# We'll make a request for sounds (which we need to make regardless),
		# and if that error fails with a token error we know we're
		# unauthenticated.
		try:
			self._sounds = self._request('sound')[0]['sounds']
		
		except APIError as error:
			if 'token' in error.bad_inputs:
				self._is_authenticated = False
		
		else:
			self._is_authenticated = True
	
	def get_user(self, token):
		"""
		Returns a :class:`~chump.User` attached to the
		:class:`~chump.Application` instance.
		
		:param string token: User API token.
		:rtype: A :class:`~chump.User`.
		
		"""
		
		return User(self, token)
	
	def _request(self, request, data=None, url=None):
		"""
		Handles the request/response cycle to Pushover's API endpoint. Request
		types are defined in :attr:`.requests`.
		
		:param string request: The type of request to make. One of 'message',
			'validate', 'sound', 'receipt', or 'cancel'.
		:param dict data: (optional) Payload to send to endpoint.
			Defaults to :py:obj:`None`.
		:param string url: (optional) URL to send payload to. Defaults to the
			URL specified by :param:request.
		
		:returns: An :py:obj:`tuple` of (``response``, ``timestamp``), where
			``response`` is a :py:obj:`dict` of the ``json`` response and
			``timestamp`` is a :py:class:`~datetime.datetime` of the time the
			response was returned.
		:rtype: A :py:obj:`tuple`.
		
		:raises: :exc:`~chump.APIError` when the request or response
			is invalid.
		
		"""
		
		if data is None:
			data = {}
		
		data['token'] = self.token
		
		if url is None:
			url = ENDPOINT + REQUESTS[request]['path']
		
		logger.debug('Making request ({request}): {data}'.format(request=request, data=data))
		
		method = REQUESTS[request]['method']
		
		try:
			if method == 'get':
				if data:
					url += '?' + urlencode(data)
				
				response = pool.open(url)
			
			elif method == 'post':
				response = pool.open(url, bytes(urlencode(data), 'utf-8', 'strict') if data else None)
		
		except HTTPError as error_response:
			response = error_response
			response.__dict__['headers'] = error_response.hdrs
		
		response.content = response.read().decode()
		
		logger.debug('Response ({code}):\n{headers}\n{content}'.format(
			code=response.code,
			headers=response.headers,
			content=response.content,
		))
		
		if response.code == 200 or 400 <= response.code < 500:
			response_json = json.loads(response.content)
			timestamp = http_date_to_datetime(response.headers['date'])
			
			if 400 <= response.code < 500:
				raise APIError(url, data, response_json, timestamp)
			
			else:
				if request == 'message':
					self.limit = int(response.headers['X-Limit-App-Limit'])
					self.remaining = int(response.headers['X-Limit-App-Remaining'])
					self.reset = epoch_to_datetime(response.headers['X-Limit-App-Reset'])
				
				return (response_json, timestamp)
		
		else:
			raise APIError(url, data, {
				'request': None,
				'status': 0,
				'errors': ['unknown error ({code}): {content}'.format(code=response.code, content=response.content)],
			}, timestamp)


class User(object):
	"""
	A Pushover user. The user is tied to a specific
	:class:`~chump.Application`, which can be changed later
	by setting :attr:`.app`.
	
	:param app: The Pushover application to send messages with.
	:type app: :class:`~chump.Application`
	:param string token: The user's API token.
	
	"""
	
	def __init__(self, app, token):
		self.app = app #: The Pushover application to send messages with.
		self.token = token #: A :py:obj:`string` of the user's API token.
		self._is_authenticated = None
		self._devices = None
	
	@property
	def is_authenticated(self):
		"""
		A lazily loaded :py:obj:`bool` indicating whether the user is authenticated.
		
		"""
		
		if self._is_authenticated is None and self.app._is_authenticated is not False:
			self._authenticate()
		
		return self.app._is_authenticated is True and self._is_authenticated
	
	@is_authenticated.setter
	def is_authenticated(self, value):
		self._is_authenticated = value
	
	@property
	def devices(self):
		"""
		A lazily loaded a :py:class:`set` of the user's devices if authenticated,
		otherwise :py:obj:`None`.
		
		"""
		
		if self._devices is None and self._is_authenticated is not False and self.app._is_authenticated is not False:
			self._authenticate()
		
		return self._devices
	
	@devices.setter
	def devices(self, value):
		self._devices = value
	
	def __setattr__(self, name, value):
		try:
			if name == 'token':
				if not TOKEN_RE.match(value):
					raise ValueError('Bad user token: expected string matching [a-zA-Z0-9]{{30}}, got {value!r}'.format(value=value))
				
				else:
					old_token = getattr(self, 'token', None)
		
		except TypeError:
			raise TypeError('Bad token: expected string, got {value_type}'.format(value_type=type(value)))
		
		super(User, self).__setattr__(name, value)
		
		if name == 'token' and self.token != old_token:
			super(User, self).__setattr__('_is_authenticated', None)
			super(User, self).__setattr__('_devices', None)
	
	def __unicode__(self):
		return "Pushover User: {token}".format(token=self.token)
	
	__str__ = __unicode__
	
	def __repr__(self):
		return 'User(app={app!r}, token={token!r})'.format(app=self.app, token=self.token)
	
	def __eq__(self, other):
		return isinstance(other, self.__class__) and self.token and self.token == other.token and self.app == other.app
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __lt__(self, other):
		return NotImplemented
	
	__le__ = __gt__ = __ge__ = __lt__
	
	def _authenticate(self):
		"""
		Authenticates the supplied user token.
		
		"""
		
		try:
			response, _ = self.app._request('validate', {'user': self.token})
		
		except APIError as error:
			if 'token' in error.bad_inputs: # We can't authenticate users with a bad API token.
				self.app._is_authenticated = False
				self.app._sounds = None
				self._is_authenticated = None
				self._devices = None
			
			else:
				self.app._is_authenticated = True
				
				if 'user' not in error.bad_inputs or error.bad_inputs['user'].startswith('valid'):
					self._is_authenticated = True
					self._devices = set()
				
				else:
					self._is_authenticated = False
					self._devices = None
		
		else:
			self._is_authenticated = True
			self._devices = set(response['devices'])
	
	def create_message(self, message, html=False, title=None, timestamp=None,
		               url=None, url_title=None, device=None, priority=NORMAL,
		               callback=None, retry=30, expire=86400, sound=None):
		"""
		Creates a message to the User with :attr:`.app`.
		
		:param string message: Body for the message.
		:param bool html: Whether the message should be formatted as HTML.
			Defaults to :py:obj:`False`.
		:param string title: (optional) Title for the message. Defaults
			to :py:obj:`None`.
		:param timestamp: (optional) Date and time to give the message.
			Defaults to the time the message was created.
		:type timestamp: :py:class:`~datetime.datetime` or :py:obj:`int`
		:param string url: (optional) URL to include in the message. Defaults
			to :py:obj:`None`.
		:param string device: (optional) device from
			:attr:`.devices` to send to. Defaults to all of the user's devices.
		:param int priority: (optional) priority for the message. The
			constants :const:`~chump.LOWEST`, :const:`~chump.LOW`,
			:const:`~chump.NORMAL`, :const:`~chump.HIGH`, and
			:const:`~chump.EMERGENCY` may be used for convenience. Defaults
			to :const:`~chump.NORMAL`.
		:param string callback: (optional) If priority is
			:const:`~chump.EMERGENCY`, the URL to ping when the message
			is acknowledged. Defaults to :py:obj:`None`.
		:param int retry: (optional) If priority is :const:`~chump.EMERGENCY`,
			the number of seconds to wait between re-alerting the user. Must be
			greater than 30. Defaults to 30.
		:param int expire: (optional) If priority is
			:const:`~chump.EMERGENCY`, the number of seconds to retry before
			giving up on alerting the user. Must be less than 86400. Defaults
			to 86400.
		:param string sound: (optional) The sound from :attr:`.app.sounds`
			to play when the message is received. Defaults to the user's
			default sound.
		
		:returns: An unsent message.
		:rtype: A :class:`~chump.Message` or :class:`~chump.EmergencyMessage`.
		
		"""
		
		kwargs = locals().copy()
		kwargs.pop('self')
		
		if priority == EMERGENCY:
			message_class = EmergencyMessage
			kwargs.pop('priority')
		
		else:
			message_class = Message
			kwargs.pop('callback')
			kwargs.pop('retry')
			kwargs.pop('expire')
		
		return message_class(self, **kwargs)
	
	def send_message(self, message, html=False, title=None, timestamp=None,
		             url=None, url_title=None, device=None, priority=NORMAL,
		             callback=None, retry=30, expire=86400, sound=None):
		"""
		Does the same as :meth:`.create_message`, but then sends the message
		with :attr:`.app`.
		
		:returns: A sent message.
		:rtype: A :class:`~chump.Message` or :class:`~chump.EmergencyMessage`.
		
		"""
		
		message = self.create_message(
			message, html, title, timestamp,
			url, url_title, device, priority,
			callback, retry, expire, sound,
		)
		
		message.send()
		
		return message


class Message(object):
	"""
	A Pushover message. The message is tied to a specific
	:class:`~chump.Application`, and :class:`~chump.User`. All
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
		
		self.id = None #: A :py:obj:`string` of the id of the message if sent, otherwise :py:obj:`None`.
		
		self.is_sent = False #: A :py:obj:`bool` indicating whether the message has been sent.
		self.sent_at = None #: A :py:class:`~datetime.datetime` of when the message was sent, otherwise :py:obj:`None`.
		
		self.error = None #: An :exc:`~chump.APIError` if there was an error sending the message, otherwise :py:obj:`None`.
	
	def __unicode__(self):
		if self.title:
			return "({title}) {message}".format(title=self.title, message=self.message)
		
		else:
			return self.message
	
	__str__ = __unicode__
	
	def __eq__(self, other):
		return isinstance(other, self.__class__) and self.id and self.id == other.id
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __lt__(self, other):
		return NotImplemented
	
	__le__ = __gt__ = __ge__ = __lt__
	
	def __setattr__(self, name, value):
		if name == 'html':
			try:
				value = int(value)
			
			except ValueError:
				raise TypeError('Bad html: expected bool, got {value_type}'.format(value_type=type(value)))
			
			else:
				if value not in (0, 1):
					raise TypeError('Bad html: expected bool, got {value_type} that is not coercible to (0, 1)'.format(value_type=type(value)))
		
		elif name in ('message', 'title', 'url', 'url_title', 'device', 'callback', 'sound'):
			if value is not None:
				if not isinstance(value, basestring):
					raise TypeError('Bad {name}: expected string, got {type}'.format(name=name, type=type(value)))
				
				elif name == 'message' and not (0 < len(value) <= 1024):
					raise ValueError('Bad message: must be 0-1024 characters, was {length}'.format(length=len(value)))
				
				if name == 'title' and len(value) > 250:
					raise ValueError('Bad title: must be <= 250 characters, was {length}'.format(length=len(value)))
				
				elif name == 'url' and len(value) > 512:
					raise ValueError('Bad url: must be <= 512 characters, was {length}'.format(length=len(value)))
				
				elif name == 'url_title' and len(value) > 100:
					raise ValueError('Bad url_title: must be <= 100 characters, was {length}'.format(length=len(value)))
				
				elif name == 'device':
					if self.user.is_authenticated:
						if value not in self.user.devices:
							raise ValueError('Bad device: must be in ({devices}), was {value!r}'.format(
								devices=', '.join(repr(s) for s in sorted(self.user.devices)),
								value=value,
							))
					else:
						logger.warning('Unverified device: {ancestor} is unauthorized, {value!r} may be bad'.format(
							ancestor='application' if self.user.app._is_authenticated is False else 'user',
							value=value
						))
				
				elif name == 'sound':
					if self.user.app.is_authenticated:
						if value not in self.user.app.sounds:
							raise ValueError('Bad sound: must be in ({sounds}), was {value!r}'.format(
								sounds=', '.join(repr(s) for s in sorted(self.user.app.sounds.keys())),
								value=value,
							))
					else:
						logger.warning('Unverified sound: application is unauthorized, {value!r} may be bad'.format(value=value))
		
		elif name == 'priority':
			try:
				value = int(value)
			
			except ValueError:
				raise TypeError('Bad {name}: expected int, got {type}'.format(name=name, type=type(value)))
		
		elif name == 'timestamp':
			if value is not None:
				try:
					if not isinstance(value, datetime):
						value = epoch_to_datetime(value)
				
				except (TypeError, ValueError):
					raise TypeError('Bad timestamp: expected valid int or datetime, got {value_type}.'.format(value_type=type(value)))
		
		elif name == 'priority':
			try:
				if not -2 <= int(value) <= 2:
					raise ValueError('Bad priority: must be between -2 and 2, was {value!r}'.format(value=value))
			
			except TypeError:
				raise TypeError('Bad priority: expected int, got {value_type}.'.format(value_type=type(value)))
		
		super(Message, self).__setattr__(name, value)
	
	def send(self):
		"""
		Sends the message. If called after the message has been sent,
		resends it.
		
		:returns: A :py:obj:`bool` indicating if the message was
			successfully sent.
		:rtype: A :py:obj:`bool`.
		
		"""
		
		self.id = None
		
		self.is_sent = False
		self.sent_at = None
		
		self.error = None
		
		data = {
			'user': self.user.token,
		}
		
		for kwarg in ('message', 'html', 'title', 'url', 'url_title', 'device', 'priority', 'sound', 'retry', 'expire', 'callback'):
			if getattr(self, kwarg, None):
				data[kwarg] = getattr(self, kwarg)
		
		if self.timestamp:
			data['timestamp'] = datetime_to_epoch(self.timestamp)
		
		try:
			# We've got to store this somewhere so that EmergencyMessage can check it for a receipt.
			self._response, self.sent_at = self.user.app._request('message', data)
		
		except APIError as error:
			self.is_sent = False
			self.error = error
			
			# This could be handled by calling {user,app}._authenticate, but that's two extra requests.
			if 'token' in error.bad_inputs:
				self.user.app._is_authenticated = False
				self.user.app._sounds = None
				self.user._is_authenticated = None
				self.user._devices = None
			
			elif 'user' in error.bad_inputs:
				self.user._is_authenticated = False
				self.user._devices = None
		
		else:
			self.is_sent = True
			self.user._is_authenticated = True
			self.user.app._is_authenticated = True
			self.id = self._response['request']
		
		return self.is_sent


class EmergencyMessage(Message):
	"""
	An emergency Pushover message, (that is, a message with the priority of
	:const:`~chump.EMERGENCY`).
	
	All arguments are the same as in :class:`~chump.Message`, with the
	additions of ``callback``, ``retry``, and ``timeout``, which
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
		
		self.receipt = None #: A :py:obj:`string` of the receipt returned by the endpoint, for polling.
		self.last_polled_at = None #: A :py:class:`~datetime.datetime` of when the message was last polled.
		
		self.last_delivered_at = None #: A :py:class:`~datetime.datetime` of when the message was last delivered.
		
		self.is_acknowledged = None #: A :py:obj:`bool` indicating whether the message has been acknowledged.
		self.acknowledged_at = None #: A :py:class:`~datetime.datetime` of when the message was acknowledged, otherwise :py:obj:`None`.
		self.acknowledged_by = None #: A :class:`~chump.User` of the first user to have acknowledged the notification, otherwise :py:obj:`None`.
		
		self.is_expired = None #: A :py:obj:`bool` indicating whether the message has expired.
		self.expires_at = None #: A :py:class:`~datetime.datetime` of when the message expires.
		
		self.is_called_back = None #: A :py:obj:`bool` indicating whether the message has been called back.
		self.called_back_at = None #: A :py:class:`~datetime.datetime` of when the message was called back, otherwise :py:obj:`None`.
	
	def __eq__(self, other):
		return isinstance(other, self.__class__) and self.receipt and self.receipt == other.receipt
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __setattr__(self, name, value):
		if name in ('retry', 'expire'):
			try:
				value = int(value)
			
			except ValueError:
				raise TypeError('Bad {name}: expected int, got {type}'.format(name=name, type=type(value)))
			
			if name == 'retry' and value < 30:
				raise ValueError('Bad retry: must be >= 30, was {value}'.format(value=value))
			
			elif name == 'expire' and not 0 < value <= 86400:
				raise ValueError('Bad expire: must be 0-86400, was {value}'.format(value=value))
		
		super(EmergencyMessage, self).__setattr__(name, value)
	
	def send(self):
		"""
		Sends the message. If called after the message has been sent,
		resends it.
		
		:returns: A :py:obj:`bool` indicating if the message was
			successfully sent.
		:rtype: A :py:obj:`bool`.
		
		"""
		
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
		
		:returns: A :py:obj:`bool` indicating if the message has not expired,
			called back nor been acknowledged, or :py:obj:`None` if the message
			has no receipt with which to poll.
		:rtype: A :py:obj:`bool` or :py:obj:`None`.
		
		"""
		
		if not self.is_sent:
			self.send()
		
		if self.receipt:
			if not (self.is_expired and self.is_acknowledged and self.is_called_back):
				self._response, self.last_polled_at = self.user.app._request('receipt', url='{endpoint}{path}{receipt}.json'.format(
					endpoint=ENDPOINT,
					path=REQUESTS['receipt']['path'],
					receipt=self.receipt,
				))
				
				for attr in ('acknowledged', 'expired', 'called_back'):
					setattr(self, 'is_{attr}'.format(attr=attr), bool(self._response[attr]))
				
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
		Cancels the request for acknowledgment of a sent message.
		
		:returns: A :py:obj:`bool` indicating if the message was
			successfully cancelled.
		:rtype: A :py:obj:`bool`.
		
		"""
		
		self._response, self.last_polled_at = self.user.app._request('cancel', url='{endpoint}{path}{receipt}/cancel.json'.format(
			endpoint=ENDPOINT,
			path=REQUESTS['receipt']['path'],
			receipt=self.receipt,
		))
		
		return bool(self._response['status'])
