#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from json import load, dump

class Config:
	'''Handle configuration file in JSON format'''

	def __init__(self, path):
		'''Read config file'''	
		self._path = path
		self._keys = list()
		with self._path.open(encoding='utf-8') as fp:
			for key, value in load(fp).items():
				self.__dict__[key] = value
				self._keys.append(key)

	def exists(self, key):
		'''Check if key exists'''
		return key in self._keys

	def save(self, path=None):
		'''Save config file'''
		if path:
			self._path = path
		with self._path.open('w', encoding='utf-8') as fp:
			dump({key: self.__dict__[key] for key in self._keys}, fp)
