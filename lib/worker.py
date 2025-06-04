#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from lib.winutils import Drives, WinPopen
from lib.size import Size

class Wipe:
	'''Wipe disk'''

	def __init__(self, device_id, log_path, zd_path, app_name, labels,
		task = 'selective',
		value = '00',
		blocksize = 0x1000,
		maxbadblocks = 200,
		maxretries = 200,
		create = 'gpt',
		fs = 'ntfs',
		label = 'Volume',
		echo = print,
		kill = None,
		finish = None,
		debug = False
	):
		'''Create object'''
		self._device_id = device_id 		# \\.\PHYSICALDRIVE\X
		self._log_path = log_path			# path to log file
		self._labels = labels				# phrases for logging etc. ("language package")
		self._task = task					# what to do: selective, full, extra or verify
		self._create = create				# create partition table: gpt, mbr or none
		self._fs = fs if create else None	# new file system
		self._label = label					# label of new partition
		self._echo = echo					# method to show messages (print or from gui)
		self._kill = kill					# event to stop wipe process
		self._finish = finish				# method to call when wipe process is finished
		formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
		logger = logging.getLogger()
		logger.setLevel(logging.DEBUG if debug else logging.INFO)
		log_fh = logging.FileHandler(filename=self._log_path, mode='w', encoding='utf-8')
		log_fh.setFormatter(formatter)
		logger.addHandler(log_fh)
		logging.info(self._labels.log_head.replace('#', app_name))
		logging.debug(f'''Parameters:
	device to wipe:			{self._device_id}
	task:					{self._task}
	value/byte to write:	{value}
	block size:				{blocksize}
	max. bad blocks:		{maxbadblocks}
	max. retries:			{maxretries}
	create partition table:	{self._create}
	new file system:		{self._fs}
	partition/drive label:	{self._label}
'''
		)
		self._cmd = [
			f'{zd_path}',
			'-f', value,
			'-b', f'{blocksize}',
			'-m', f'{maxbadblocks}',
			'-r', f'{maxretries}'
		]
		if self._task == 'full':
			self._cmd.append('-a')
		elif self._task  == 'extra':
			self._cmd.append('-x')
		elif self._task  == 'verify':
			self._cmd.append('-v')
		self._cmd.append(self._device_id)
		self._script_path = log_path.parent / 'diskpart_tmp_script.txt'	# path to script for diskpart
		self._drives = Drives()
		self._logical_ids = self._drives.get_children_of(self._device_id)

	def run(self):
		'''Execute copy process (or simulation)'''
		problems = False
		self._info(self._labels.executing.replace('#', ' '.join(self._cmd)))
		print(self._cmd)
		zd_proc = WinPopen(self._cmd)
		print(zd_proc)
		for line in zd_proc.stdout:
			msg = line.strip()
			if msg.startswith('...'):
				self.echo(msg, end='\r')
			elif msg == '':
				self._echo('')
			else:
				self._info(msg)
		if zd_proc.stderr:
			self._error(zd_proc.stderr.read())
			problems = True

		if self._task != 'verify' and self._create:
			self._drives.create_partition(self._drive_id, script_path, label='Volume', drive=None, mbr=False, fs='ntfs'):
			
		if problems:
			self._warning(self._labels.problems)
		else:
			self._info(self._labels.all_done)
		logging.shutdown()
		return 'error' if problems else 'green'

	def _info(self, msg):
		'''Log info and echo message'''
		logging.info(msg)
		self._echo(msg)

	def _decode_exception(self, arg):
		'''Decode exception'''
		return f'{type(arg)}: {arg}' if isinstance(arg, Exception) else str(arg)

	def _warning(self, arg):
		'''Log and echo warning'''
		msg = self._decode_exception(arg)
		logging.warning(msg)
		self._echo(msg)

	def _error(self, arg):
		'''Log and echo error'''
		msg = self._decode_exception(arg)
		logging.error(msg)
		self._echo(msg)

	def _abort(self, ex):
		'''Abort on error / exception'''
		self._error(ex)
		try:
			logging.shutdown()
		except:
			pass
		raise ex

	def _chck_returncode(self, returncode):
		if returncode > 5:
			ex = ChildProcessError(self._labels.robocopy_problem.replace('#', f'{returncode}'))
			self._error(ex)
			raise ex

	def _run_robocopy(self):
		'''Run RoboCopy'''
		for line in self._robocopy.run():
			if line.endswith('%'):
				self._echo(line, end='\r')
			else:
				self._echo(line)
			if self._kill and self._kill.is_set():
				self._robocopy.process.terminate()
				raise SystemExit('Kill signal')
		if self._robocopy.returncode > 5:
			ex = ChildProcessError(self._labels.robocopy_problem.replace('#', f'{self._robocopy.returncode}'))
			self._error(ex)
			raise ex

