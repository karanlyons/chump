# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import logging
import time
from datetime import datetime

import requests


VERSION = (0, 1, 0)

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
	def __init__(self, request_id, messages):
		self.request_id = request_id
		self.messages = messages
	
	def __str__(self):
		return "({id}) {messages}".format(id=self.request_id, messages=" ".join(self.messages))


class Pushover(object):
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
			self.authenticate()
	
	def __str__(self):
		return "Application: {token}".format(token=self.token)
		
	def __unicode__(self):
		return self.__str__()
	
	def __repr__(self):
		return 'Pushover(token=\'{token}\')'.format(token=self.token)
	
	def authenticate(self, token=None):
		self.is_authenticated = True
		
		try:
			self.request('validate')
		
		except PushoverError as error:
			if 'application token is invalid' in error.messages:
				self.is_authenticated = False
		
		if self.is_authenticated and not hasattr(self, 'sounds'):
			self.sounds = self.request('sound')['sounds']
		
		return self.is_authenticated
	
	def get_user(self, token):
		return PushoverUser(self, token)
	
	def request(self, request, data={}, url=None):
		data['token'] = self.token
		
		if url is None:
			url = self.endpoint + self.requests[request]['url']
		
		logger.debug('Making request ({request}): {data}'.format(request=request, data=str(data)))
		
		request = getattr(requests, self.requests[request]['method'])(url, params=data)
		
		logger.debug('Response ({code}): {text}'.format(code=request.status_code, text=request.text))
		
		if request.status_code == 200 or 400 <= request.status_code < 500:
			response = request.json()
			
			if 400 <= request.status_code < 500:
				raise PushoverError(response['request'], response['errors'])
			
			else:
				return response
		
		else:
			raise PushoverError(None, ['unknown error ({code})'.format(code=request.status_code)])


class PushoverUser(object):
	def __init__(self, app, token):
		self.app = app
		self.token = token
	
	def __setattr__(self, name, value):
		super(PushoverUser, self).__setattr__(name, value)
		
		if name == 'token':
			self.authenticate()
	
	def __str__(self):
		return "User: {token}".format(token=self.token)
	
	def __unicode__(self):
		return self.__str__()
	
	def __repr__(self):
		return 'PushoverUser(app={app}, token=\'{token}\')'.format(app=repr(self.app), token=self.token)
	
	def authenticate(self):
		try:
			response = self.app.request('validate', {'user': self.token})
		
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
		
		response = self.app.request('message', data)
		
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
						response = self.app.request('receipt', url='{endpoint}{url}{receipt}.json'.format(endpoint=self.app.endpoint, url=self.app.requests['receipt']['url'], receipt=self.receipt))
						
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
