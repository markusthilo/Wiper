#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sys import executable as __executable__
import logging
from pathlib import Path
from time import time, strftime
from os import getpid
from classes_wiper import Config, Drives, WinPopen

__parent_path__ = Path(__file__).parent if Path(__executable__).stem == 'python' else Path(__executable__).parent

class Wipe:
	'''Wipe disk'''

	def __init__(self, device_id, echo=print, kill=None, finish=None):
		'''Create object'''
		self._time = strftime('%Y-%m-%d_%H%M')
		self._pid = f'{getpid():08x}'
		self._device_id = device_id 		# \\.\PHYSICALDRIVE\X
		self._echo = echo					# method to show messages (print or from gui)
		self._kill = kill					# event to stop wipe process
		self._finish = finish				# method to call when wipe process is finished
		self._config = Config(__parent_path__ / 'config.json')
		self._labels = Config(__parent_path__ / 'labels.json')
		self._log_dir_path = __parent_path__ / 'logs'	### logging ###
		if self._log_dir_path.exists():
			if self._log_dir_path.is_file():
				self._log_dir_path.unlink()
				self._log_dir_path.mkdir()
			else:
				now = time()	# purge logs older 7 days
				for path in self._log_dir_path.iterdir():
					if now - path.stat().st_mtime > 604800:
						try:
							path.unlink()
						except:
							pass
		else:
			self._log_dir_path.mkdir()
		self._log_file_path = self._log_dir_path / f'{self._time}_{self._pid}_log.txt'
		formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
		logger = logging.getLogger()
		logger.setLevel(logging.INFO)
		log_fh = logging.FileHandler(filename=self._log_file_path, mode='w', encoding='utf-8')
		log_fh.setFormatter(formatter)
		logger.addHandler(log_fh)
		self._cmd = [__parent_path__ / 'zd-win.exe',
			'-f', self._config.value,
			'-b', f'{self._config.blocksize}',
			'-m', f'{self._config.maxbadblocks}',
			'-r', f'{self._config.maxretries}'
		]
		if self._config.task == 'full':
			self._cmd.append('-a')
		elif self._config.task  == 'extra':
			self._cmd.append('-x')
		elif self._config.task  == 'verify':
			self._cmd.append('-v')
		self._cmd.append(self._device_id)
		self._script_path = self._log_dir_path /  f'{self._time}_{self._pid}_diskpart.txt'	# path to script for diskpart
		self._warnings = False

	def run(self):
		'''Execute copy process (or simulation)'''
		self._drives = Drives()
		msg = self._labels.log_head.replace('#', f'{self._config.application} v{self._config.version}')
		for attr, info in self._drives.get_drive_info(self._device_id).items():
			if info:
				msg += f'\n{attr}: {info}'
		msg += '\n'
		logging.info(msg)
		self._echo(self._labels.executing.replace('#', f'{self._cmd[0].name} {" ".join(self._cmd[1:])}'))
		self._old_part_ids = self._drives.get_children_of(self._device_id)
		zd_proc = WinPopen(self._cmd)	### zd-win ###
		for line in zd_proc.stdout:
			msg = line.strip()
			if msg.startswith('...'):
				self._echo(msg, end='\r')
			elif msg.startswith('Warning:'):
				self._warning(msg)
			elif msg == '':
				self._echo('')
			else:
				self._info(msg)
			if self._check_kill_signal():
				zd_proc.terminate()
				zd_proc.wait()
				return
		if stderr := zd_proc.stderr.read().strip():
			if stderr.startswith('Error: found bad blocks:'):
				msg = self._labels.bad_blocks_error.replace('#', stderr)
				if self._config.task == 'verify' and self._config.create == 'none':
					self._warning(msg)
				else:
					self._error(ChildProcessError(msg))
			else:
				self._error(ChildProcessError(self._labels.zd_error.replace('#', stderr)))
		if  self._config.create != 'none':
			if self._config.create != 'none' and self._config.fs:	### diskpart ###
				new_volume_id = None	# do not assign drive
				if self._config.create == 'none' or self._config.fs == 'none':
					self._info(self._labels.running_diskpart)
					self._drives.diskpart(self._device_id, self._script_path,
						pt = None if self._config.create == 'none' else self._config.create,
						fs = None,
						echo = self._echo
					)
				else:	# assign new partition to drive letter
					id_list = sorted(list(self._old_part_ids))	# test former drive letters first
					occupied_ids = self._drives.get_occupied_volumes()
					for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
						volume_id = f'{letter}:'
						if volume_id not in self._old_part_ids and volume_id not in occupied_ids:
							id_list.append(volume_id)
					verified_id_list = list()
					for volume_id in id_list:
						try:
							if Path(volume_id).is_dir():
								continue
						except:
							pass
						verified_id_list.append(volume_id)
					if verified_id_list:
						for cnt, volume_id in enumerate(id_list):
							if self._check_kill_signal():
								return
							if cnt == 0:
								self._info(self._labels.running_diskpart)
							else:
								self._info(self._labels.running_diskpart_again)
							self._drives.diskpart(self._device_id, self._script_path,
								pt = self._config.create,
								fs = self._config.fs,
								label = self._config.label,
								letter = volume_id.rstrip(':'),
								echo = self._echo
							)
							if Path(volume_id).is_dir():
								new_volume_id = volume_id
								break
							if not new_volume_id:
								self._warning(self._labels.unable_assign_drive)
					else:
						self._info(self._labels.running_diskpart)
						self._drives.diskpart(self._device_id, self._script_path,
							pt = self._config.create,
							fs = self._config.fs,
							label = self._config.label,
							echo = self._echo
						)
						self._warning(self._labels.no_free_letter)
			if new_volume_id:
				self._info(self._labels.finished)
				self._echo(self._labels.drive_ready.replace('#', f'{new_volume_id}'))
				logging.shutdown()
				drive_path = Path(new_volume_id)
				try:
					drive_path.joinpath(f'{self._time}_wiper_log.txt').write_bytes(self._log_file_path.read_bytes())
				except:
					self._echo(self._labels.warning_log.replace('#', f'{drive_path}'))
					self._warnings = True
				return not self._warnings
			else:
				self._warning(self._labels.warning_assign.replace('#', f'{drive_path}'))
			self._warnings = True
		self._info(self._labels.finished)
		if self._warnings:
			self._warning(self._labels.warnings_occured)
		else:
			returncode = True
		logging.shutdown()
		return returncode

	def _info(self, msg):
		'''Log info and echo message'''
		logging.info(msg)
		self._echo(msg)

	def _warning(self, msg):
		'''Log and echo warning'''
		logging.warning(msg)
		self._echo( f'{self._labels.warning}: msg')

	def _error(self, msg):
		'''Log and echo error'''
		logging.error(msg)
		logging.shutdown()
		returncode = f'{self._labels.error}: msg'
		self._echo(returncode)
		return returncode

	def _check_kill_signal(self):
		'''Check if kill signal is set'''
		if self._kill and self._kill.is_set():
			self._info(self._labels.aborting_by_user)
			logging.shutdown()
			return True
		return False