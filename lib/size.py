#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class Size(int):
	'''Copy functionality'''

	def readable(self, format_k='{iec} / {si}', format_b='{b} byte(s)'):
		'''Genereate readable size string,
			format_k: "{iec} / {si} / {b} bytes" gives e.g. 9.54 MiB / 10.0 MB / 10000000 bytes
			format_b will be returned if size < 5 bytes
		'''
		def _round(*base):	# intern function to calculate human readable
			for prefix, b in base:
				rnd = round(self/b, 2)
				if rnd >= 1:
					break
			if rnd >= 10:
				rnd = round(rnd, 1)
			if rnd >= 100:
				rnd = round(rnd)
			return f'{rnd} {prefix}', rnd
		try:	# start method here
			size = int(self)
		except (TypeError, ValueError):
			return 'undetected'
		iec = None
		rnd_iec = 0
		si = None
		rnd_si = 0
		if '{iec}' in format_k:
			iec, rnd_iec = _round(('PiB', 2**50), ('TiB', 2**40), ('GiB', 2**30), ('MiB', 2**20), ('kiB', 2**10))
		if '{si}' in format_k:
			si, rnd_si = _round(('PB', 10**15), ('TB', 10**12), ('GB', 10**9), ('MB', 10**6), ('kB', 10**3))
		if not '{b}' in format_k and rnd_iec == 0 and rnd_si == 0:
			return format_b.format(b=size)
		return format_k.format(iec=iec, si=si, b=size)

	def __add__(self, other):
		'''Plus'''
		return Size(int.__add__(self, other))