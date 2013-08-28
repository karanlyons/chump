# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
import time
from datetime import datetime

import requests


VERSION = (0, 1, 1)

__title__ = 'chump'
__version__ = '.'.join((str(i) for i in VERSION))
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
			return int(time.mktime(d.astimezone(pytz.utc).timetuple()))
		
		except ValueError:
			return int(time.mktime(d.timetuple()))
	
	def epoch_to_datetime(e): return pytz.utc.localize(datetime.utcfromtimestamp(e))

except:
	logger.warning('pytz is not installed; datetime\'s may be innacurate.')
	
	def utc_now(): return datetime.utcnow()
	def datetime_to_epoch(d): return int(time.mktime(d.timetuple()))
	def epoch_to_datetime(e): return datetime.utcfromtimestamp(e)


class PushoverError(Exception):
	"""
	Pushover errors eponysterically end up here. :attr:`.request_id` gives you
	the request id assigned by Pushover, which can be helpful if you need to
	talk to them about the error. :attr:`.messages` stores a list of human
	readable error messages returned by the endpoint.
	
	"""
	
	def __init__(self, response):
		self.response = response
		self.request_id = self.response['request']
		self.messages = self.response['messages']
		self.bad_inputs = [key for key, value in self.response.iteritems() if value =='invalid']
	
	def __str__(self):
		return "({id}) {messages}".format(id=self.request_id, messages=" ".join(self.messages))


class Pushover(object):
	"""
	The Pushover application in use.
	
	:param string token: Pushover API token. Can be changed later by setting
		:attr:`Pushover.token`.
	
	"""
	
	endpoint = 'https://api.pushover.net/1/'
	requests = {
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
	
	def __init__(self, token):
		self.token = token
	
	def __setattr__(self, name, value):
		super(Pushover, self).__setattr__(name, value)
		
		if name == 'token':
			self._authenticate()
	
	def __str__(self):
		return "Application: {token}".format(token=self.token)
		
	def __unicode__(self):
		return self.__str__()
	
	def __repr__(self):
		return 'Pushover(token=\'{token}\')'.format(token=self.token)
	
	def _authenticate(self):
		"""
		Authenticates the supplied application token on
		:func:`chump.Pushover.__init__`. If authenticated,
		:attr:`.is_authenticated` is ``True``, and :attr:`.sounds` is loaded
		with a ``dict`` of available notification sounds.
		
		:returns: :attr:`.is_authenticated`.
		:rtype: bool
		
		"""
		
		self.is_authenticated = True
		
		try:
			self._request('validate')
		
		except PushoverError as error:
			if 'application token is invalid' in error.messages:
				self.is_authenticated = False
		
		if self.is_authenticated and not hasattr(self, 'sounds'):
			self.sounds = self._request('sound')['sounds']
		
		return self.is_authenticated
	
	def get_user(self, token):
		"""
		Returns a :class:`PushoverUser` attached to the :class:`Pushover`
		instance.
		
		:param string token: User API token. Can be changed later by setting
			:attr:`PushoverUser.token`.
		:rtype: :class:`PushoverUser`
		
		"""
		
		return PushoverUser(self, token)
	
	def _request(self, request, data=None, url=None):
		"""
		Handles the request/response cycle to Pushover's API endpoint. Request
		types are defined in :attr:`Pushover.requests`.
		
		:param string request: 'message', 'validate', 'sound', or 'receipt'.
		:param dict data: (optional) Payload to send to endpoint.
		:param string url: (optional) URL to send payload to; overwrites.
			URL specified by :param:request.
		:returns: Response's ``json``.
		:rtype: ``json``.
		:raises: :class:`PushoverError` when request or response is invalid.
		
		"""
		
		if data is None:
			data = {}
		
		data['token'] = self.token
		
		if url is None:
			url = self.endpoint + self.requests[request]['url']
		
		logger.debug('Making request ({request}): {data}'.format(request=request, data=str(data)))
		
		request = getattr(requests, self.requests[request]['method'])(url, params=data)
		
		logger.debug('Response ({code}): {text}'.format(code=request.status_code, text=request.text))
		
		if request.status_code == 200 or 400 <= request.status_code < 500:
			response = request.json()
			
			if 400 <= request.status_code < 500:
				raise PushoverError(response)
			
			else:
				return response
		
		else:
			raise PushoverError({
				'request': None,
				'messages': ['unknown error ({code})'.format(code=request.status_code)],
			})


class PushoverUser(object):
	"""
	A Pushover user. The user is tied to a specific :class:`Pushover`
	application, which can be changed later by setting :attr:`.app`.
	
	:param string token: User API token. Can be changed later by setting
		:attr:`PushoverUser.token`.
	
	"""
	
	def __init__(self, app, token):
		self.app = app
		self.token = token
	
	def __setattr__(self, name, value):
		super(PushoverUser, self).__setattr__(name, value)
		
		if name == 'token':
			self._authenticate()
	
	def __str__(self):
		return "User: {token}".format(token=self.token)
	
	def __unicode__(self):
		return self.__str__()
	
	def __repr__(self):
		return 'PushoverUser(app={app}, token=\'{token}\')'.format(app=repr(self.app), token=self.token)
	
	def _authenticate(self):
		"""
		Authenticates the supplied user token on
		:func:`chump.PushoverUser.__init__`. If authenticated,
		:attr:`.is_authenticated` is ``True``, and :attr:`.devices` is loaded
		with a ``set`` of the user's available devices.
		
		:returns: :attr:`.is_authenticated`.
		:rtype: bool
		
		"""
		
		try:
			response = self.app._request('validate', {'user': self.token})
		
		except PushoverError as error:
			if 'user is valid but has no active devices' in error.messages:
				self.is_authenticated = True
				self.devices = set()
			
			else:
				self.authenticated = False
				
				if hasattr(self, 'devices'):
					delattr(self, 'devices')
		
		else:
			self.is_authenticated = True
			self.devices = set(response['devices'])
		
		return self.is_authenticated
	
	def send_message(self, message, title=None, timestamp=None, url=None, url_title=None, devices=None, priority=-1, callback=None, retry=30, expire=86400, sound=None):
		"""
		Sends a message to the User with :attr:``.app``.
		
		:param string message:
		:param string title: (optional)
		:param timestamp: (optional)
		:type timestamp: datetime or integer
		:param string url: (optional)
		:param devices: (optional)
		:type devices: string or iterable
		:param integer priority: (optional)
		:param string callback: (optional)
		:param integer retry: (optional)
		:param integer expire: (optional)
		:param string sound: (optional)
		
		:returns: A message or a list of messages.
		:rtype: :class:`PushoverMessage` or [:class:`PushoverMessage`,...]
		
		"""
		
		kwargs = locals()
		
		data = {
			'user': self.token,
			'message': message,
			'priority': priority,
		}
		
		if timestamp:
			if isinstance(timestamp, datetime):
				data['timestamp'] = datetime_to_epoch(timestamp)
		
		else:
			data['timestamp'] = datetime_to_epoch(utc_now())
		
		if priority == 2:
			data['retry'] = retry
			data['expire'] = expire
			
			if callback:
				data['callback'] = callback
		
		for kwarg in ('title', 'devices', 'url', 'url_title', 'sound'):
			if kwargs[kwarg]:
				data[kwarg] = kwargs[kwarg]
		
		if devices:
			if hasattr(devices, '__iter__'):
				if set(devices) != self.devices:
					return [PushoverMessage(self, data, device) for device in devices if device in self.devices]
				
				else:
					return PushoverMessage(self, data)
			
			else:
				return PushoverMessage(self, data, devices)
		
		else:
			return PushoverMessage(self, data)


class PushoverMessage(object):
	"""
	A Pushover message. The message is tied to a specific :class:`Pushover`
	application, and :class:`PushoverUser` user. The paramaters of the message
	are exposed as attributes on the object, for convenience.
	
	:param user:
	:type user: :class:`PushoverUser`
	:param dict data:
	:param device: (optional)
	:type device: string or iterable
	
	"""
	
	def __init__(self, user, data, device=None):
		self.app = user.app
		self.user = user
		self.device = device
		
		self.title = None
		self.timestamp = None
		self.url = None
		self.url_title = None
		self.priority = -1
		self.callback = None
		self.retry = None
		self.expire = None
		self.sound = None
		
		for key, value in data.iteritems():
			if key !=  'user':
				setattr(self, key, value)
		
		if self.device:
			data['device'] = device
		
		if self.timestamp:
			self.timestamp = epoch_to_datetime(self.timestamp)
		
		response = self.app._request('message', data)
		
		self.id = response['request']
		
		if self.priority == 2:
			try:
				self.receipt = response['receipt']
				self.expired = False
				self.acknowledged = False
				self.called_back = False
			
			except AttributeError:
				self.receipt = None
				self.expired = None
				self.acknowledged = None
				self.called_back = None
			
			else:
				def poll():
					if not (self.expired and self.acknowledged and self.called_back):
						response = self.app._request('receipt', url='{endpoint}{url}{receipt}.json'.format(endpoint=self.app.endpoint, url=self.app.requests['receipt']['url'], receipt=self.receipt))
						
						for attr in ('expired', 'acknowledged', 'called_back'):
							setattr(self, attr, bool(response[attr]))
							
							if response[attr]:
								attr_at = '{}_at'.format(attr)
								setattr(self, attr_at, epoch_to_datetime(response[attr_at]))
					
					return not (self.expired or self.acknowledged)
				
				setattr(self, 'poll', poll)
	
	def __str__(self):
		if self.title:
			return "({title}) {message}".format(title=self.title, message=self.message)
		
		else:
			return self.message
	
	def __unicode__(self):
		return self.__str__()
