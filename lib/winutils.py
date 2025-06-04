#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE, STDOUT, STARTUPINFO, STARTF_USESHOWWINDOW
from wmi import WMI
from pathlib import Path
from time import sleep
from lib.size import Size

class WinPopen(Popen):
	'''Popen with startupinfo'''

	def __init__(self, cmd):
		'''Create process'''
		self._cmd = cmd
		startupinfo = STARTUPINFO()
		startupinfo.dwFlags |= STARTF_USESHOWWINDOW
		super().__init__(self._cmd,
			stdout = PIPE,
			stderr = STDOUT,
			encoding = 'utf-8',
			errors = 'ignore',
			universal_newlines = True,
			startupinfo = startupinfo
		)

	def __repr__(self):
		'''Return command line as string'''
		return ' '.join(f"'{item}'" if isinstance(item, Path) else f'{item}' for item in self._cmd)

class Drives:
	'''Use WMI to get infos about drives'''

	DISKPART_TIMEOUT = 30
	DISKPART_RETRIES = 10
	DISKPART_DELAY = 10
	NTFS_LABEL_CHARS = r'abcdefghijklmnopqrstuvwxyz!§$%&()@-_#=[]{}€'
	FAT_LABEL_CHARS = r'abcdefghijklmnopqrstuvwxyz!§$%&()@-_#'

	def __init__(self):
		'''Connect to API'''			
		self._conn = WMI()

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
		device_id = str(device_id).upper()
		parents = self.get_parents()
		if device_id.startswith('\\\\.\\PHYSICALDRIVE'):
			return device_id if device_id in parents.values() else None
		try:
			return parents[device_id]
		except KeyError:
			return

	def get_children_of(self, device_id):
		'''Return logical drives / partitions of given physical drive'''
		part2logical = {rel.Antecedent.DeviceID: rel.Dependent.DeviceID
			for rel in self._conn.Win32_LogicalDiskToPartition()
		}
		return {part2logical[rel.Dependent.DeviceID] for rel in self._conn.Win32_DiskDriveToDiskPartition()
			if rel.Antecedent.DeviceID == device_id
		}

	def dump(self):
		'''Return list of all drives'''
		parents = self.get_parents()
		log_disks = self.get_logical()
		drives = list()
		for device_id, drive_dict in self.get_physical().items():
			drive = {'DeviceID': device_id} | drive_dict
			drive['Partitions'] = list()
			for log_id, disk_id in parents.items():
				if disk_id == device_id:
					drive['Partitions'].append({'DeviceID': log_id} | log_disks[log_id])
			drives.append(drive)
		return drives

	def get_system_ids(self):
		'''Get ids if system drives'''
		ids = set()
		for os_drive in self._conn.Win32_OperatingSystem():
			if os_drive.SystemDrive:
				ids.add(os_drive.SystemDrive)
				ids.add(self.get_parent_of(os_drive.SystemDrive))
		return ids

	def get_free_drive_letter(self):
		'''Get 1st free drive letter'''
		assigned = [drive_id.rstrip(':') for drive_id in self.get_logical()]
		for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
			if letter not in assigned:
				return letter

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

	def create_partition(self, drive_id, script_path, label='Volume', drive=None, mbr=False, fs='ntfs'):
		'''Create partition using diskpart'''
		drive_id = str(drive_id).upper()
		if drive:
			drive = drive.rstrip(':\\/')
		else:
			drive = self.get_free_drive_letter()
			if not drive:
				raise OSError('No free drive letters')
		drive_path = Path(f'{drive}:\\')
		if mbr:
			table = 'mbr'
		else:
			table = 'gpt'
		script_path.write_text(f'''select disk {drive_id[17:]}
clean
convert {table}
create partition primary
format quick fs={fs} label={label}
assign letter={drive}
''')
		proc = WinPopen([f'diskpart', '/s', f'{script_path}'])
		for line in proc.stdout:
			print(line.rstrip())
		return

		try:
			proc.wait(timeout=self.DISKPART_TIMEOUT)
		except TimeoutExpired:
			pass
		try:
			scrip_path.unlink()
		except:
			pass
		for cnt in range(self.DISKPART_RETRIES):
			print(cnt)
			if drive_path.exists():
				return drive_path
			sleep(self.DISKPART_DELAY)
