#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from time import strftime, perf_counter
from lib.winutils import Drives
from lib.size import Size

class Wipe:
	'''Wipe disk'''

	MIN_BLOCKSIZE = 512
	STD_BLOCKSIZE = 4096
	MAX_BLOCKSIZE = 32768

	def __init__(self, device_id, app_path, labels,
		verify = False,
		allbytes = False,
		extra = False,
		value = 0,
		blocksize = 4096,
		maxbadblocks = 200,
		maxretries = 200,
		label = 'Volume',
		drive = None,
		mbr = False,
		fs = 'ntfs',
		log = None,
		echo = print,
		kill = None
	):
		'''Create object'''
		self._device_id = device_id 		# \\.\PHYSICALDRIVE\X
		self._app_path = app_path			# root directory of robocopygui.py or robocopygui.exe
		self._labels = labels				# phrases for logging etc. ("language package")
		self._verify = verify				# True to verify (no wiping)
		self._allbytes = allbytes			# 1-pass wipe but write every byte instead of checking before
		self._extra = extra					# 2-pass wipe
		self._value = value					# byte to overwrite
		self._blocksize = blocksize			# blocksize to write
		self._maxbadblocks = maxbadblocks	# tolerate badblocks before abort/error
		self._maxretries = maxretries		# number of retries before abort/error
		self._label = label					# Label of new partition
		self._drive = drive					# new drive letter
		self._mbr = mbr						# mbr instead of gpt
		self._fs = fs						# new file system
		self._log_path = log				# path to additional log (given by user, None will only write lastlog in app folder)
		self._echo = echo					# method to show messages (print or from gui)
		self._kill = kill					# event to stop wipe process

	def run(self):
		'''Execute copy process (or simulation)'''
		try:	### start logging ###
			formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
			logger = logging.getLogger()
			logger.setLevel(logging.INFO)
			lastlog_fh = logging.FileHandler(filename=self._app_path/'lastlog.txt', mode='w', encoding='utf-8')
			lastlog_fh.setFormatter(formatter)
			logger.addHandler(lastlog_fh)
			if self._log_path:	# additional log file for the user
				userlog_fh = logging.FileHandler(filename=self._log_path, mode='w', encoding='utf-8')
				userlog_fh.setFormatter(formatter)
				logger.addHandler(userlog_fh)
			self._robocopy = RoboCopy()
		except Exception as ex:
			self._abort(ex)
		start_time = perf_counter()		### read source structure ###
		src_dir_paths = set()	# given directories to copy
		src_file_paths = set()	# given files to copy
		self._info(self._labels.reading_source)
		for path in self._src_paths:
			src_path = path.resolve()
			if src_path.is_dir():
				src_dir_paths.add(src_path)
			elif src_path.is_file():
				src_file_paths.add(src_path)
			else:
				msg = self._labels.invalid_path.replace('#', f'{path}')
				logging.error(msg)
				self._echo(msg)
				raise FileNotFoundError(msg)
		src_dir_paths = list(src_dir_paths)
		src_file_paths = list(src_file_paths)
		files = list()	# all files to copy (including subdirectories): (path, size)
		total_bytes = Size(0)	# total size of all files to copy
		for this_src_dir_path in src_dir_paths:
			for path in this_src_dir_path.rglob('*'):
				if path.is_file():
					size = path.stat().st_size
					files.append((path, size, self._dst_path / path.relative_to(this_src_dir_path.parent)))
					total_bytes += size
		for path in src_file_paths:
			size = path.stat().st_size
			files.append((path, size, self._dst_path / path.name))
			total_bytes += size
		self._info(f'{self._labels.done_reading}: {len(files)} {self._labels.file_s}, {total_bytes.readable()}')
		if self._simulate:	### sumilating copy process ###
			self._info(self._labels.starting_simulation)
			collisions = list()
			col_cnt = 0
			for src_path, size, dst_path in files:
				msg = f'{src_path} ({Size(size).readable()}) -> {dst_path}'
				if dst_path.exists():
					self._echo(f'{msg} {self._labels.existing}')
					collisions.append((src_path, size, dst_path, True))
					col_cnt += 1
				else:
					self._echo(msg)
					collisions.append((src_path, size, dst_path, False))
				if self._kill and self._kill.is_set():
					break
			if self._tsv_path:	# write simple file list when simulating 
				with self._tsv_path.open('w', encoding='utf-8') as fh:
					print('src_path\tsrc_size\tdst_path\tdst_exists', file=fh)
					for src_path, size, dst_path, exists in collisions:
						collision = dst_path.name if exists else ''
						print(f'{src_path}\t{Size(size).readable()}\t{dst_path}\t{collision}', file=fh)
			if col_cnt:
				self._info(self._labels.collisions.replace('#', f'{col_cnt}'))
			if self._kill and self._kill.is_set():
				self._echo(self._labels.simulation_aborted)
			else:
				self._info(self._labels.simulation_finished)
			logging.shutdown()
			return
		if self._hashes:	### start hashing ###
			self._info(self._labels.starting_hashing)
			hash_thread = HashThread(files, algorithms=self._hashes)
			hash_thread.start()
		for src_path in src_dir_paths:	### copy directories ###
			dst_path = self._dst_path / src_path.name
			self._info(self._labels.executing.replace('#',
				f'{self._robocopy.mk_cmd(src_path, dst_path)}')
			)
			self._run_robocopy()
		for src_path in src_file_paths:	### copy files ###
			self._info(self._labels.executing.replace('#',
				f'{self._robocopy.mk_cmd(src_path.parent, self._dst_path, file=src_path.name)}')
			)
			self._run_robocopy()
		self._info(self._labels.robocopy_finished)
		total_files = len(files)
		mismatches = 0
		bad_dst_file_paths = dict()
		if self._verify == 'size':	### verify files by size ###
			self._echo_file_progress(total_files, total_files)
			self._info(self._labels.starting_size_verification)
			for cnt, (src_path, src_size, dst_path) in enumerate(files, start=1):
				self._echo_file_progress(total_files, cnt)
				dst_size = dst_path.stat().st_size
				if dst_size != src_size:
					self._warning(self._labels.mismatching_sizes.replace('#',
						f'{src_path}: {src_size} byte(s), {dst_path}: {dst_size} bytes(s)')
					)
					mismatches += 1
					bad_dst_file_paths[dst_path] = dst_size
			self._info(self._labels.size_check_finished)
			if not self._hashes:
				with self._tsv_path.open('w', encoding='utf-8') as fh:
					print('src_path\tsrc_size\tdst_path\tbad_dst_size', file=fh)
					for src_path, src_size, dst_path in files:
						bad_dst_size = bad_dst_file_paths[dst_path] if dst_path in bad_dst_file_paths else ''
						print(f'{src_path}\t{src_size}\t{dst_path}\t{bad_dst_size}', file=fh)
		if self._hashes:	### wait until hashing is finished ###
			self._info(self._labels.waiting_end_hashing)
			if hash_thread.is_alive():
				self._info(self._labels.hashing_in_progress)
				index = 0
				while hash_thread.is_alive():
					self._echo(f'{"|/-\\"[index]}  ', end='\r')
					index += 1
					if index > 3:
						index = 0
					sleep(.25)
			self._info(self._labels.hashing_finished)
		if self._verify and self._verify != 'size':	### verify by hash value ###
			bad_dst_hash = ''
			self._info(self._labels.starting_hash_verification)
			with self._tsv_path.open('w', encoding='utf-8') as fh:
				print(f'{"\t".join(hash_thread.keys)}\tbad_{self._verify}', file=fh)
				for cnt, hash_set in enumerate(hash_thread.files, start=1):
					self._echo_file_progress(total_files, cnt)
					dst_hash = FileHash.hashsum(hash_set['dst_path'], algorithm=self._verify)
					if dst_hash != hash_set[self._verify]:
						self._warning(self._labels.mismatching_hashes.replace('#',
							f'{hash_set["src_path"]}: {hash_set[self._verify]}, {hash_set["dst_path"]}: {dst_hash}')
						)
						mismatches += 1
						bad_dst_hash = dst_hash
					else:
						bad_dst_hash = ''
					print(f'{"\t".join(f'{hash_set[key]}' for key in hash_thread.keys)}\t{bad_dst_hash}', file=fh)
			self._info(self._labels.hash_check_finished.replace('#', f'{self._verify}'))
		if self._hashes and not self._verify:	### write tsv file without verification ###
			with self._tsv_path.open('w', encoding='utf-8') as fh:
				print(f'{"\t".join(hash_thread.keys)}', file=fh)
				for cnt, hash_set in enumerate(hash_thread.files, start=1):
					self._echo_file_progress(total_files, cnt)
					print(f'{"\t".join(f'{hash_set[key]}' for key in hash_thread.keys)}', file=fh)
		if self._hashes and self._verify == 'size':	### write tsv file with size verification ###
			with self._tsv_path.open('w', encoding='utf-8') as fh:
				print(f'{"\t".join(hash_thread.keys)}\tbad_dst_size', file=fh)
				for cnt, hash_set in enumerate(hash_thread.files, start=1):
					bad_dst_size = bad_dst_file_paths[hash_set['dst_path']] if hash_set['dst_path'] in bad_dst_file_paths else ''
					print(f'{"\t".join(f'{hash_set[key]}' for key in hash_thread.keys)}\t{bad_dst_size}', file=fh)
		end_time = perf_counter()
		delta = end_time - start_time
		self._info(self._labels.copy_finished.replace('#', f'{timedelta(seconds=delta)}'))
		if mismatches:
			self._warning(self._labels.mismatches.replace('#', f'{mismatches}'))
		logging.shutdown()
		return 'error' if mismatches else 'green'

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

	def	_echo_file_progress(self, total, this):
		'''Show progress of processing files'''
		self._echo(f'{this} {self._labels.of_files.replace("#", f"{total}")}, {int(100*this/total)}%', end='\r')
