# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import socket
import threading


HOST = 'api.pushover.net'


try: # Python 3
	from http.client import HTTPException, HTTPResponse, HTTPSConnection
	from urllib.request import build_opener, HTTPSHandler, URLError
	from urllib.response import addinfourl
	
	class FreeingHTTPResponse(HTTPResponse):
		def _close_conn(self):
			super()._close_conn()
			
			try: self._handler.free_connection(self._connection)
			except AttributeError: pass

except ImportError: # Python 2
	from httplib import HTTPException, HTTPResponse, HTTPSConnection
	from select import select
	from urllib import addinfourl
	from urllib2 import build_opener, HTTPSHandler, URLError
	
	class FreeingHTTPResponse(HTTPResponse):
		def close(self):
			# Consume any remaining data in the socket
			try:
				while select((self.fp._sock,), (), (), 0)[0]:
					if not self.fp._sock.recv(256):
						break
			
			except AttributeError:
				pass
			
			HTTPResponse.close(self)
			
			try: self._handler.free_connection(self._connection)
			except AttributeError: pass


class FreeingHTTPSConnection(HTTPSConnection):
	response_class = FreeingHTTPResponse


class PushoverPooledConnectionHandler(HTTPSHandler):
	def __init__(self, debuglevel=0, context=None):
		# Old form for Python 2 compatibility.
		HTTPSHandler.__init__(self, debuglevel, context)
		
		self.lock = threading.Lock()
		self.pool = set()
		self.free = set()
	
	def https_open(self, request):
		try:
			connection = self.get_free_connection()
			while connection:
				response = self.make_request(connection, request)
				
				if response is not None:
					break
				
				else:
					connection.close()
					self.remove_connection(connection)
					connection = self.get_free_connection()
			
			else:
				connection = self.get_new_connection()
				response = self.make_request(connection, request)
		
		except (socket.error, HTTPException) as exc:
			raise URLError(exc)
		
		else:
			if response.raw.will_close:
				self.remove_connection(connection)
			
			return response

	def get_new_connection(self):
		connection = FreeingHTTPSConnection(HOST, context=self._context)
		connection.set_debuglevel(self._debuglevel)
		self.lock.acquire()
		try: self.pool.add(connection)
		finally: self.lock.release()
		
		return connection
	
	def get_free_connection(self):
		self.lock.acquire()
		try: return self.free.pop() if self.free else None
		finally: self.lock.release()
	
	def free_connection(self, connection):
		self.lock.acquire()
		try: self.free.add(connection)
		finally: self.lock.release()
	
	def remove_connection(self, connection):
		self.lock.acquire()
		try: self.pool.remove(connection)
		except KeyError: pass
		finally: self.lock.release()
	
	def make_request(self, connection, request):
		connection.timeout = request.timeout
		try:
			try: # Python 3
				connection.request(
					request.get_method(),
					request.selector,
					request.data,
					request.headers
				)
			
			except AttributeError: # Python 2
				connection.request(
					request.get_method(),
					request.get_selector(),
					request.data,
					request.headers
				)
			
			try: raw_response = connection.getresponse(buffering=True)
			except TypeError: raw_response = connection.getresponse()
		
		except (socket.error, HTTPException):
			return None
		
		raw_response._handler = self
		raw_response._connection = connection
		
		try: # Python 3
			response = addinfourl(
				raw_response,
				raw_response.msg,
				request.get_full_url(),
				raw_response.status
			)
		
		except AttributeError: # Python 2
			response = addinfourl(
				socket._fileobject(raw_response, close=True),
				raw_response.msg,
				request.get_full_url(),
				raw_response.status
			)
			
			raw_response.recv = raw_response.read
			response.msg = raw_response.reason
		
		response.raw = raw_response
		
		return response


pool = build_opener(PushoverPooledConnectionHandler)
