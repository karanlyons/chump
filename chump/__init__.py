# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import calendar
import logging
import time
from datetime import datetime
from email.utils import parsedate

import requests


VERSION = (1, 2, 0)

__title__ = 'Chump'
__version__ = '.'.join((str(i) for i in VERSION)) # str for compatibility with setup.py under Python 3.
__author__ = 'Karan Lyons'
__contact__ = 'karan@karanlyons.com'
__homepage__ = 'https://github.com/karanlyons/chump'
__license__ = 'Apache 2.0'
__copyright__ = 'Copyright 2013 Karan Lyons'


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


try:
	import pytz
	
	def utc_now(): return pytz.utc.localize(datetime.utcnow())
	
	def datetime_to_epoch(d):
		try:
			return int(calendar.timegm(d.astimezone(pytz.utc).timetuple()))
		
		except ValueError:
			return int(time.mktime(d.timetuple()))
	
	def epoch_to_datetime(e): return pytz.utc.localize(datetime.utcfromtimestamp(e))
	def http_date_to_datetime(t): return pytz.utc.localize(datetime(*parsedate(t)[:6]))

except:
	logger.warning('pytz is not installed; datetime\'s may be inaccurate.')
	
	def utc_now(): return datetime.utcnow()
	def datetime_to_epoch(d): return int(time.mktime(d.timetuple()))
	def epoch_to_datetime(e): return datetime.utcfromtimestamp(e)
	def http_date_to_datetime(t): return datetime(*parsedate(t)[:6])


LOW = -1 #: Message priority: No sound, no vibration, no banner.
NORMAL = 0 #: Message priority: Sound, vibration, and banner if outside of user's quiet hours.
HIGH = 1 #: Message priority: Sound, vibration, and banner regardless of user's quiet hours.
EMERGENCY = 2 #: Message priority: Sound, vibration, and banner regardless of user's quiet hours, and re-alerts until acknowledged.


ENDPOINT = 'https://api.pushover.net/1/'
REQUESTS = {
	'message': {
		'method': 'post',
		'url': 'messages.json',
	},
	'validate': {
		'method': 'post',
		'url': 'users/validate.json',
	},
	'sound': {
		'method': 'get',
		'url': 'sounds.json',
	},
	'receipt': {
		'method': 'get',
		'url': 'receipts/'
	}
}


class APIError(Exception):
	"""
	Pushover errors eponysterically end up here.
	
	:param dict json: The json response from the endpoint.
	
	"""
	
	def __init__(self, response):
		self.response = response #: The json response from the endpoint.
		self.status = self.response['status'] #: The status code.
		self.request_id = self.response['request'] #: The request's id.
		
		self.messages = self.response['errors'] #: A :py:obj:`list` of human readable error messages.
		
		#: A :py:class:`dict` of the inputs the endpoint didn't like and why.
		self.bad_inputs = dict([(key, value) for key, value in self.response.iteritems() if key not in {'errors', 'messages', 'status', 'receipt', 'request'}])
		
		logger.debug('APIError raised. Endpoint response was {response}'.format(response=self.response))
	
	def __str__(self):
		return "({id}) {messages}".format(id=self.request_id, messages=" ".join(self.messages))


class Application(object):
	"""
	The Pushover app in use.
	
	:param string token: The app's API token.
	
	"""
	
	def __init__(self, token):
		self.is_authenticated = False #: A :py:obj:`bool` indicating whether the app has been authenticated.
		self.sounds = None #: If authenticated, a :py:class:`dict` of available notification sounds, otherwise ``None``.
		self.token = unicode(token) #: The app's API token.
	
	def __setattr__(self, name, value):
		super(Application, self).__setattr__(name, value)
		
		if name == 'token':
			self._authenticate()
	
	def __str__(self):
		return "Pushover App: {token}".format(token=self.token)
		
	def __unicode__(self):
		return self.__str__()
	
	def __repr__(self):
		return 'Application(token=\'{token}\')'.format(token=self.token)
	
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
			self.sounds = self._request('sound')['sounds']
	
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
		
		:returns: Response's ``json``.
		:rtype: ``json``.
		
		:raises: :exc:`~chump.APIError` when request or response is invalid.
		
		"""
		
		if data is None:
			data = {}
		
		data['token'] = self.token
		
		if url is None:
			url = ENDPOINT + REQUESTS[request]['url']
		
		logger.debug('Making request ({request}): {data}'.format(request=request, data=unicode(data)))
		
		response = getattr(requests, REQUESTS[request]['method'])(url, params=data)
		
		logger.debug('Response ({code}): {text}'.format(code=response.status_code, text=response.text))
		
		if response.status_code == 200 or 400 <= response.status_code < 500:
			json = response.json()
			json['sent'] = http_date_to_datetime(response.headers['date'])
			
			if 400 <= response.status_code < 500:
				raise APIError(json)
			
			else:
				return json
		
		else:
			raise APIError({
				'request': None,
				'status': 0,
				'messages': ['unknown error ({code})'.format(code=response.status_code)],
			})


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
			self._authenticate()
	
	def __str__(self):
		return "Pushover User: {token}".format(token=self.token)
	
	def __unicode__(self):
		return self.__str__()
	
	def __repr__(self):
		return 'User(app={app}, token=\'{token}\')'.format(app=repr(self.app), token=self.token)
	
	def _authenticate(self):
		"""
		Authenticates the supplied user token.
		
		"""
		
		try:
			response = self.app._request('validate', {'user': self.token})
		
		except APIError as error:
			if 'token' in error.bad_inputs: # We can't authenticate users with a bad API token.
				self.app.is_authenticated = False
				self.is_authenticated = None
				self.devices = None
			
			elif 'user' not in error.bad_inputs:
				self.is_authenticated = True
				self.devices = set()
			
			else:
				self.is_authenticated = False
				self.devices = None
		
		else:
			self.is_authenticated = True
			self.devices = set(response['devices'])
	
	def create_message(self, message, title=None, timestamp=None,
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
			constants :const:`~chump.LOW`, :const:`~chump.NORMAL`,
			:const:`~chump.HIGH`, and :const:`~chump.EMERGENCY` may be used for
			convenience. Defaults to :const:`~chump.NORMAL`.
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
		
		kwargs = locals()
		kwargs.pop('self')
		
		if priority == 2:
			message_class = EmergencyMessage
			kwargs.pop('priority')
		
		else:
			message_class = Message
			[kwargs.pop(key) for key in ('callback', 'retry', 'expire')]
		
		return message_class(self, **kwargs)
	
	def send_message(self, message, title=None, timestamp=None,
	                 url=None, url_title=None, device=None, priority=NORMAL,
	                 callback=None, retry=30, expire=86400, sound=None):
		"""
		Does the same as :func:`.create_message`, but sends them all with
		:attr:`.app` as well.
		
		:returns: A sent message.
		:rtype: :class:`~chump.Message` or :class:`EmergencyMessage`.
		
		"""
		
		message = self.create_message(
			message, title, timestamp,
			url, url_title, devices, priority,
			callback, retry, expire, sound
		)
		
		messages.send()
		
		return messages


class Message(object):
	"""
	A Pushover message. The message is tied to a specific
	:class:`~chump.Application` app, and :class:`~chump.User` user. All
	parameters are exposed as attributes on the message, for convenience.
	
	:param user: The user to send the message to.
	:type user: :class:`~chump.User`
	
	All other arguments are the same as in :func:`User.create_message`.
	
	"""
	
	def __init__(self, user, message, title=None, timestamp=None,
	             url=None, url_title=None, device=None, priority=0, sound=None):
		self.user = user
		self.message = message
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
		if value and name in {'message', 'title', 'url', 'url_title', 'device', 'callback', 'sound', 'priority', 'retry', 'expire'}:
			if name in {'message', 'title', 'url', 'url_title', 'device', 'callback', 'sound'}:
				try:
					value = unicode(value)
				
				except ValueError:
					raise ValueError('Bad {name}: expected string, got {type}'.format(name=name, type=type(value)))
			
			if name in {'priority', 'retry', 'expire'}:
				try:
					value = int(value)
				
				except ValueError:
					raise ValueError('Bad {name}: expected int, got {type}'.format(name=name, type=type(value)))
			
			if name in {'message', 'title'}:
				length = len(value)
				length += len(list({'message', 'title'} - {name})[0]) # Yup.
				
				if length > 512:
					raise ValueError('Bad {name}: message + title must be <= 512 characters, was {length}'.format(name=name, length=length))
			
			elif name == 'url' and len(value) > 500:
				raise ValueError('Bad url: must be <= 500 characters, was {length}'.format(length=len(value)))
			
			elif name =='url_title' and len(value) > 50:
				raise ValueError('Bad url_title: must be <= 500 characters, was {length}'.format(length=len(value)))
			
			elif name == 'timestamp':
				try:
					if isinstance(value, datetime):
						value = datetime_to_epoch(value)
					
					else:
						value = epoch_to_datetime(value)
				
				except (TypeError, ValueError):
					raise TypeError('Bad timestamp: expected valid int or datetime, got {type}.'.format(type=type(value)))
			
			elif name == 'priority':
				try:
					if not -1 <= int(value) <= 2:
						raise ValueError('Bad priority: must be between -1 and 2, was {value}'.format(value=value))
				
				except TypeError:
					raise TypeError('Bad priority: expected int, got {type}.'.format(type=type(value)))
			
			elif name == 'sound' and value not in self.user.app.sounds:
				raise ValueError('Bad sound: must be in {sounds}, was {value}'.format(sounds=self.user.app.sounds.keys(), value=repr(value)))
			
			elif name == 'device' and value not in self.user.devices:
				raise ValueError('Bad device: must be in {devices}, was {value}'.format(devices=self.user.devices, value=repr(value)))
		
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
		
		for kwarg in ('message', 'title', 'timestamp', 'url', 'url_title', 'device', 'priority', 'sound', 'retry', 'expire', 'callback'):
			if hasattr(self, kwarg) and getattr(self, kwarg):
				data[kwarg] = getattr(self, kwarg)
		
		try:
			# We've got to store this somewhere so that EmergencyMessage can check it for a receipt.
			self._response = self.user.app._request('message', data)
		
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
			self.sent_at = self._response['sent']
		
		return self.is_sent
	
	def __str__(self):
		if self.title:
			return "({title}) {message}".format(title=self.title, message=self.message)
		
		else:
			return self.message
	
	def __unicode__(self):
		return self.__str__()


class EmergencyMessage(Message):
	"""
	An emergency Pushover message, (that is, a message with the priority of
	:const:`~chump.EMERGENCY`).
	
	All arguments are the same as in :class:`~chump.Message`, with the
	additions of ``call_back``, ``retry``, and ``timeout``, which
	are all, too, as defined in :func:`User.create_message`.
	
	"""
	
	def __init__(self, user, message, title=None, timestamp=None, url=None,
		         url_title=None, device=None, sound=None, callback=None,
		         retry=30, expire=86400):
		priority = EMERGENCY
		
		super(EmergencyMessage, self).__init__(
			user, message, title, timestamp, url,
			url_title, device, priority, sound
		)
		
		self.callback = callback
		self.retry = retry
		self.expire = expire
		
		self.receipt = None #: The receipt returned by the endpoint, for polling.
		
		self.last_delivered_at = None #: A :py:class:`datetime.datetime` of when the message was last delivered.
		
		self.is_acknowledged = None #: A :py:obj:`bool` indicating whether the message has been acknowledged.
		self.acknowledged_at = None #: A :py:class:`datetime.datetime` of when the message was acknowledged, otherwise ``None``.
		
		self.is_expired = None #: A :py:obj:`bool` indicating whether the message has expired.
		self.expires_at = None #: A :py:class:`datetime.datetime` of when the message expires.
		
		self.is_called_back = None #: A :py:obj:`bool` indicating whether the message has been called back.
		self.called_back_at = None #: A :py:class:`datetime.datetime` of when the message was called back, otherwise ``None``.
	
	def __setattr__(self, name, value):
		if name == 'retry' and value < 30:
			raise ValueError('Bad retry: must be >= 30, was {value}'.format(value=value))
		
		elif name == 'expire' and value > 86400:
			raise ValueError('Bad expire: must be <= 86400, was {value}'.format(value=value))
		
		super(EmergencyMessage, self).__setattr__(name, value)
	
	def send(self):
		self.receipt = None
		
		self.last_delivered_at = None
		
		self.is_acknowledged = None
		self.acknowledged_at = None
		
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
				self._response = self.user.app._request('receipt', url='{endpoint}{url}{receipt}.json'.format(
					endpoint=ENDPOINT,
					url=REQUESTS['receipt']['url'],
					receipt=self.receipt
				))
				
				for attr in ('acknowledged', 'expired', 'called_back'):
					setattr(self, 'is_{}'.format(attr), bool(self._response[attr]))
					
				for attr_at in ('acknowledged_at', 'expires_at', 'called_back_at', 'last_delivered_at'):
					if self._response[attr_at]:
						setattr(self, attr_at, epoch_to_datetime(self._response[attr_at]))
			
			return not (self.is_acknowledged or self.is_expired)
		
		else:
			return None
