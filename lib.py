#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from json import load, dump
from subprocess import Popen, PIPE, STDOUT, STARTUPINFO, STARTF_USESHOWWINDOW
from wmi import WMI
from time import sleep

class Config:
	'''Handle configuration file in JSON format'''

	def __init__(self, path):
		'''Read config file'''	
		self.path = path
		self._keys = list()
		with self.path.open(encoding='utf-8') as fp:
			for key, value in load(fp).items():
				self.__dict__[key] = value
				self._keys.append(key)

	def exists(self, key):
		'''Check if key exists'''
		return key in self._keys

	def save(self, path=None):
		'''Save config file'''
		if path:
			self.path = path
		with self.path.open('w', encoding='utf-8') as fp:
			dump({key: self.__dict__[key] for key in self._keys}, fp)

class Size(int):
	'''Human readable size'''

	def __repr__(self):
		'''Genereate readable size'''
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
		if self < 0:
			raise ValueError('Size must be positive')
		iec, rnd_iec = _round(('PiB', 2**50), ('TiB', 2**40), ('GiB', 2**30), ('MiB', 2**20), ('kiB', 2**10))
		si, rnd_si = _round(('PB', 10**15), ('TB', 10**12), ('GB', 10**9), ('MB', 10**6), ('kB', 10**3))
		return (f'{iec} / {si} / ' if rnd_iec or rnd_si else '') + f'{int(self)} ' + ('byte' if self == 1 else 'bytes')

	def __add__(self, other):
		'''Plus'''
		return Size(int.__add__(self, other))

class WinPopen(Popen):
	'''Popen with startupinfo'''

	def __init__(self, cmd):
		'''Create process'''
		self._cmd = cmd
		startupinfo = STARTUPINFO()
		startupinfo.dwFlags |= STARTF_USESHOWWINDOW
		super().__init__(cmd,
			stdout = PIPE,
			#stderr = STDOUT,
			stderr = PIPE,
			encoding = 'utf-8',
			errors = 'ignore',
			universal_newlines = True,
			startupinfo = startupinfo
		)

class Drives:
	'''Use WMI to get infos about drives'''

	DELAY = 1
	RETRIES = 10
	NTFS_LABEL_CHARS = r'abcdefghijklmnopqrstuvwxyz!§$%&()@-_#=[]{}€'
	FAT_LABEL_CHARS = r'abcdefghijklmnopqrstuvwxyz!§$%&()@-_#'

	def __init__(self):
		'''Connect to API'''			
		self._conn = WMI()

	def _retrie(self, method, *args):
		'''Retrieve data from WMI'''
		for _ in range(self.RETRIES):
			try:
				return method(*args)
			except:
				sleep(self.DELAY)
		raise ChildProcessError('WMI timeout')

	def logical(self):
		'''Get drive letters'''
		return {log_disk.DeviceID for log_disk in self._conn.Win32_LogicalDisk()}

	def get_logical(self):
		'''Get logical disks'''
		log_disks = dict()
		for log_disk in self._conn.Win32_LogicalDisk():
			log_disks[log_disk.DeviceID] = dict()
			try:
				log_disks[log_disk.DeviceID]['VolumeName'] = log_disk.VolumeName
			except AttributeError:
				log_disks[log_disk.DeviceID]['VolumeName'] = ''
			try:
				log_disks[log_disk.DeviceID]['FileSystem'] = log_disk.FileSystem
			except AttributeError:
				log_disks[log_disk.DeviceID]['FileSystem'] = ''
			try:
				log_disks[log_disk.DeviceID]['Size'] = Size(log_disk.Size)
			except TypeError:
				log_disks[log_disk.DeviceID]['Size'] = None
		return log_disks

	def get_physical(self):
		'''Get physical disks'''
		drives = dict()
		for drive in self._conn.Win32_DiskDrive():
			drives[drive.DeviceID] = dict()
			try:
				drives[drive.DeviceID]['Caption'] = drive.Caption
			except AttributeError:
				drives[drive.DeviceID]['Caption'] = ''
			try:
				drives[drive.DeviceID]['MediaType'] = drive.MediaType
			except AttributeError:
				drives[drive.DeviceID]['MediaType'] = ''
			try:
				drives[drive.DeviceID]['InterfaceType'] = drive.InterfaceType
			except AttributeError:
				drives[drive.DeviceID]['InterfaceType'] = ''
			try:
				drives[drive.DeviceID]['Size'] = Size(drive.Size)
			except TypeError:
				drives[drive.DeviceID]['Size'] = None
		return drives

	def get_parents(self):
		'''Return dict LOGICALDRIVE: PHYSICALDRIVE'''
		disk2part = {(rel.Antecedent.DeviceID, rel.Dependent.DeviceID)
			for rel in self._conn.Win32_DiskDriveToDiskPartition()
		}
		part2logical = {(rel.Antecedent.DeviceID, rel.Dependent.DeviceID)
			for rel in self._conn.Win32_LogicalDiskToPartition()
		}
		return {logical: disk
			for disk, part_disk in disk2part
			for part_log, logical in part2logical
			if part_disk == part_log
		}

	def get_parent_of(self, device_id):
		'''Get parent of given device'''
		if device_id.startswith('\\\\.\\PHYSICALDRIVE'):
			return device_id
		return self.get_parents()[device_id]

	def get_children_of(self, device_id):
		'''Return logical drives / partitions of given physical drive'''
		part2logical = {rel.Antecedent.DeviceID: rel.Dependent.DeviceID
			for rel in self._conn.Win32_LogicalDiskToPartition()
		}
		return {part2logical[rel.Dependent.DeviceID] for rel in self._conn.Win32_DiskDriveToDiskPartition()
			if rel.Antecedent.DeviceID == device_id and rel.Dependent.DeviceID in part2logical
		}

	def dump(self):
		'''Return list of all drives'''
		parents = self.get_parents()
		log_disks = self.get_logical()
		drives = dict()
		for device_id, drive_dict in self.get_physical().items():
			drive = {'DeviceID': device_id} | drive_dict
			drive['Partitions'] = list()
			for log_id, disk_id in parents.items():
				if disk_id == device_id:
					drive['Partitions'].append({'DeviceID': log_id} | log_disks[log_id])
			try:
				drives[int(device_id.lstrip('\\\\.\\PHYSICALDRIVE'))] = drive
			except ValueError:
				pass
		return [drives[i] for i in sorted(drives.keys())]

	def get_system_ids(self):
		'''Get ids if system drives'''
		ids = set()
		for os_drive in self._conn.Win32_OperatingSystem():
			if os_drive.SystemDrive:
				ids.add(os_drive.SystemDrive)
				ids.add(self.get_parent_of(os_drive.SystemDrive))
		return ids

	def check_fs_label(self, label, fs):
		'''Check if string would be a valid file system label'''
		fs = fs.lower()
		if fs == 'ntfs':
			max_len = 32
			valid_chars = self.NTFS_LABEL_CHARS
		elif fs == 'exfat':
			max_len = 15
			valid_chars = self.FAT_LABEL_CHARS
		elif fs == 'fat32':
			max_len = 11
			valid_chars = self.FAT_LABEL_CHARS
		else:
			raise ValueError(f'invalid fs: {fs}')
		if len(label) > max_len:
			raise ValueError(f'label too long ({max_len} max. for {fs}): "{label}", {len(label)} chars')
		for char in label:
			if char.lower() not in valid_chars:
				raise ValueError(f'invalid chaaracter in "{label}": {char}')
		return label

	def diskpart(self, drive_id, script_path, pt='gpt', fs='ntfs', label='Volume', letter=None):
		'''Create partition table and partition using diskpart'''
		script = f'select disk {drive_id.lstrip("\\\\.\\PHYSICALDRIVE")}\nclean\nconvert {pt}\n'
		if fs:
			script += f'create partition primary\nformat quick fs={fs} label={label}\n'
			if letter:
				script += f'assign letter={letter}\n'
		script_path.write_text(script)
		return WinPopen([f'diskpart', '/s', f'{script_path}'])
