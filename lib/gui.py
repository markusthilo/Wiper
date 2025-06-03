#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from threading import Thread, Event
from pathlib import Path
from time import strftime
from tkinter import Tk, PhotoImage, StringVar
from tkinter.font import nametofont
from tkinter.ttk import Frame, Label, Entry, Button, Combobox, Treeview
from tkinter.ttk import Scrollbar, Spinbox
from tkinter.scrolledtext import ScrolledText
from tkinter.messagebox import askyesno, showerror
from tkinter.filedialog import askdirectory, askopenfilenames, asksaveasfilename
from idlelib.tooltip import Hovertip
from lib.winutils import Drives
#from lib.worker import Wipe

class WorkThread(Thread):
	'''The worker has tu run as thread not to freeze GUI/Tk'''

	def __init__(self, target_id, config, labels, log_path, echo, finish
	):
		'''Pass arguments to worker'''
		super().__init__()
		self._finish = finish
		self._kill_event = Event()
		self._worker = Wipe(device_id, log_path, labels,
			task = config.task,
			value = value,
			blocksize = blocksize,
			maxbadblocks = maxbadblocks,
			maxretries = maxretries,
			label = label,
			drive = drive,
			mbr = mbr,
			fs = fs,
			echo = echo,
			kill = self._kill_event,
			finish = self._finish
		)

	def kill(self):
		'''Kill thread'''
		self._kill_event.set()

	def run(self):
		'''Run thread'''
		#try:
		returncode = self._worker.run()
		#except:
		#	returncode = 'error'
		self._finish(returncode)

class Gui(Tk):
	'''GUI look and feel'''

	def __init__(self, app_path, version, config, gui_defs, labels):
		'''Open application window'''
		super().__init__()
		self._app_path = app_path
		self._config = config
		self._labels = labels
		self._defs = gui_defs
		self._work_thread = None
		self.title(f'{self._labels.app_title} v{version}')
		self.rowconfigure(0, weight=1)
		self.rowconfigure(5, weight=3)
		self.columnconfigure(0, weight=1)
		self.columnconfigure(1, weight=1)
		self.columnconfigure(2, weight=1)
		self.iconphoto(True, PhotoImage(file=self._app_path / self._defs.appicon))
		self.protocol('WM_DELETE_WINDOW', self._quit_app)
		font = nametofont('TkTextFont').actual()
		font_family = font['family']
		self._font_size = font['size']
		min_size_x = self._font_size * self._defs.x_factor
		min_size_y = self._font_size * self._defs.y_factor
		self.minsize(min_size_x , min_size_y)
		self.geometry(f'{min_size_x}x{min_size_y}')
		self.resizable(True, True)
		self._pad = int(self._font_size * self._defs.pad_factor)
		self._id_width = self._font_size * self._defs.tree_id
		self._info_width = self._font_size * self._defs.tree_info
		self._size_width = self._font_size * self._defs.tree_size
		self._drive_frame = Frame(self)	### drive tree ###
		self._drive_frame.grid(row=0, column=0, columnspan=3, sticky='nsew', padx=self._pad, pady=self._pad)
		self._drive_tree = Treeview(self._drive_frame,
			selectmode = 'browse',
			columns = ('Info', 'Size'),
			show = 'tree'
		)
		self._drive_tree.column('#0', width=self._id_width, stretch='no')
		self._drive_tree.column('Info', minwidth=self._info_width, stretch='yes') 
		self._drive_tree.column('Size', width = self._size_width, stretch='no')
		self._drives = Drives()
		self._drive_dump = None
		self._gen_drive_tree()
		self._drive_tree.pack(side='left', expand=True, fill='both')
		self._drive_tree.bind('<Button-1>', self._select_drive)
		vsb = Scrollbar(self._drive_frame, orient='vertical', command=self._drive_tree.yview)
		vsb.pack(side='right', fill='y')
		self._drive_tree.configure(yscrollcommand=vsb.set)
		Hovertip(self._drive_frame, self._labels.drive_tip)
		self._task = StringVar(value=self._labels.tasks[self._config.task])	### task ###
		self._task_selector = Combobox(self,
			textvariable = self._task,
			values = tuple(self._labels.tasks.values()),
			state = 'readonly',
		)
		self._task_selector.grid(row=1, column=0, sticky='nwe', padx=self._pad)
		Hovertip(self._task_selector, self._labels.task_tip)
		self._rev_tasks = dict(zip(self._labels.tasks.values(), self._labels.tasks))
		frame = Frame(self)	### value ###
		frame.grid(row=1, column=1, sticky='nwe', pady=(0, self._pad))
		Label(frame, text=f'{self._labels.value}:').pack(side='left', padx=self._pad)
		self._value_box = Spinbox(frame, values=tuple(f'{b:02x}' for b in range(0x100)), width=self._defs.box_width)
		self._value_box.pack(side='right', padx=self._pad)
		self._value_box.set(self._config.value)
		Hovertip(frame, self._labels.value_tip)
		frame = Frame(self)	### blocksize ###
		frame.grid(row=1, column=2, sticky='nwe', pady=(0, self._pad))
		Label(frame, text=f'{self._labels.blocksize}:').pack(side='left', padx=self._pad)
		self._blocksize_box = Spinbox(frame, values=tuple(2**p for p in range(9, 16)), width=self._defs.box_width)
		self._blocksize_box.pack(side='right', padx=self._pad)
		self._blocksize_box.set(self._config.blocksize)
		Hovertip(frame, self._labels.blocksize_tip)
		frame = Frame(self)	### maxbadblocks ###
		frame.grid(row=2, column=1, sticky='nwe')
		Label(frame, text=f'{self._labels.maxbadblocks}:').pack(side='left', padx=self._pad)
		self._maxbadblocks_box = Spinbox(frame, from_=0, to=0xffff, width=self._defs.box_width)
		self._maxbadblocks_box.pack(side='right', padx=self._pad)
		self._maxbadblocks_box.set(self._config.maxbadblocks)
		Hovertip(frame, self._labels.maxbadblocks_tip)
		frame = Frame(self)	### maxretries ###
		frame.grid(row=2, column=2, sticky='nwe')
		Label(frame, text=f'{self._labels.maxretries}:').pack(side='left', padx=self._pad)
		self._maxretries_box = Spinbox(frame, from_=0, to=0xffff, width=self._defs.box_width)
		self._maxretries_box.pack(side='right', padx=self._pad)
		self._maxretries_box.set(self._config.maxretries)
		Hovertip(frame, self._labels.maxretries_tip)
		self._create = StringVar(value=self._labels.create[self._config.create])	### create ###
		self._create_selector = Combobox(self,
			textvariable = self._create,
			values = tuple(self._labels.create.values()),
			state = 'readonly',
		)
		self._create_selector.grid(row=3, column=0, sticky='nwe', padx=self._pad, pady=self._pad)
		Hovertip(self._create_selector, self._labels.create_tip)
		self._rev_create = dict(zip(self._labels.create.values(), self._labels.create))
		self._fs = StringVar(value=self._labels.fs[self._config.fs])	### fs ###
		self._fs_selector = Combobox(self,
			textvariable = self._fs,
			values = tuple(self._labels.fs.values()),
			state = 'readonly',
		)
		self._fs_selector.grid(row=3, column=1, sticky='nwe', padx=self._pad, pady=self._pad)
		Hovertip(self._fs_selector, self._labels.fs_tip)
		self._rev_fs = dict(zip(self._labels.fs.values(), self._labels.fs))
		label = Label(self, text=f'{self._labels.label}:')	### label ###
		label.grid(row=4, column=0, sticky='nw', padx=self._pad)
		self._label = StringVar(value=self._config.label)
		self._label_entry = Entry(self, textvariable=self._label)
		self._label_entry.grid(row=4, column=1, sticky='nwe', padx=self._pad)
		Hovertip(label, self._labels.label_tip)
		self._start_text = StringVar(value=self._labels.choose_target)	### start ###
		self._start_button = Button(self, textvariable=self._start_text, command=self._start, state='disabled')
		self._start_button.grid(row=3, rowspan=2, column=2, sticky='nswe', padx=self._pad, pady=(self._pad, 0))
		Hovertip(self._start_button, self._labels.wipe_tip)
		self._info_text = ScrolledText(self, font=(font_family, self._font_size), padx=self._pad, pady=self._pad)
		self._info_text.grid(row=5, column=0, columnspan=3, sticky='nsew',	### info text ###
			ipadx=self._pad, ipady=self._pad, padx=self._pad, pady=self._pad)
		self._info_text.bind('<Key>', lambda dummy: 'break')
		self._info_text.configure(state='disabled')
		self._info_fg = self._info_text.cget('foreground')
		self._info_bg = self._info_text.cget('background')
		self._info_newline = True
		self._info_label = Label(self)	### info label ###
		self._info_label.grid(row=6, column=0, sticky='nsew', padx=self._pad, pady=(0, self._pad))
		self._label_fg = self._info_label.cget('foreground')
		self._label_bg = self._info_label.cget('background')
		self._quit_button = Button(self, text=self._labels.quit, command=self._quit_app)	### quit ###
		self._quit_button.grid(row=6, column=2, sticky='e', padx=self._pad, pady=(0, self._pad))
		Hovertip(self._quit_button, self._labels.quit_tip)
		self._refresh_counter = 0	# to check devices every 2 seconds
		self._warning_state = 'disabled'	# no warning info
		self._refresh_loop()	# handle warning and observe drives

	def _select_drive(self, event):
		'''Run on double click'''
		if item := self._drive_tree.identify('item', event.x, event.y):
			if device_id := self._drives.get_parent_of(item):
				self._target_id = device_id
				self._start_text.set(f'{self._labels.wipe} {self._target_id}')
				self._start_button.configure(state='normal')

	def _gen_drive_tree(self):
		'''Refresh drive tree'''
		new_drive_dump = self._drives.dump()
		if new_drive_dump != self._drive_dump:
			self._drive_dump = new_drive_dump
			self._drive_tree.delete(*self._drive_tree.get_children())
			for drive_dict in self._drive_dump:
				self._drive_tree.insert('', 'end',
					text = drive_dict['DeviceID'],
					values = (
						', '.join((drive_dict['Caption'], drive_dict['MediaType'], drive_dict['InterfaceType'])),
						drive_dict['Size'].readable() if drive_dict['Size'] else ''
					),
					iid = drive_dict['DeviceID'],
					open = True
				)
				for part_dict in drive_dict['Partitions']:
					self._drive_tree.insert(drive_dict['DeviceID'], 'end',
						text = part_dict['DeviceID'],
						values = (
							', '.join((part_dict['VolumeName'], part_dict['FileSystem'])),
							part_dict['Size'].readable() if part_dict['Size'] else ''
						),
						iid = part_dict['DeviceID']
					)

	def _refresh_loop(self):
		'''Show flashing warning'''
		if self._warning_state == 'enable':
			self._info_label.configure(text=self._labels.warning)
			self._warning_state = '1'
		if self._warning_state == '1':
			self._info_label.configure(foreground=self._defs.red_fg, background=self._defs.red_bg)
			self._warning_state = '2'
		elif self._warning_state == '2':
			self._info_label.configure(foreground=self._label_fg, background=self._label_bg)
			self._warning_state = '1'
		elif self._warning_state != 'disabled':
			self._info_label.configure(text= '', foreground=self._label_fg, background=self._label_bg)
			self._warning_state = 'disabled'
		self._refresh_counter += 1
		if self._refresh_counter > 3:
			self._refresh_counter = 0
			self._gen_drive_tree()
		self.after(500, self._refresh_loop)

	def _get_task(self):
		'''Get task'''
		try:
			task = self._rev_tasks[self._task.get()]
		except Exception as ex:
			return ex
		self._config.task = task

	def _get_value(self):
		'''Get value'''
		try:
			value = int(self._value_box.get(), 16)
		except Exception as ex:
			return ex
		if value < 0 or value >= 0x80000000:
			return ValueError(f'value out of range: {value}')
		self._config.value = value

	def _get_blocksize(self):
		'''Get block size'''
		try:
			blocksize = int(self._blocksize_box.get())
		except Exception as ex:
			return ex
		if blocksize < 0x100 or blocksize > 0x8000 or blocksize % 0x100 != 0:
			return ValueError(f'invalid block size: {blocksize}')
		self._config.blocksize = blocksize

	def _get_maxbadblocks(self):
		'''Get max bad blocks'''
		try:
			maxbadblocks = int(self._maxbadblocks_box.get())
		except Exception as ex:
			return ex
		if maxbadblocks < 0 or maxbadblocks >= 0x80000000:
			return ValueError(f'value out of range: {maxbadblocks}')
		self._config.maxbadblocks = maxbadblocks

	def _get_maxretries(self):
		'''Get max retries'''
		try:
			maxretries = int(self._maxretries_box.get())
		except Exception as ex:
			return ex
		if maxretries < 0 or maxretries >= 0x80000000:
			return ValueError(f'value out of range: {maxretries}')
		self._config.maxretries = maxretries

	def _get_create(self):
		'''Get create'''
		try:
			create = self._rev_create[self._create.get()]
		except Exception as ex:
			return ex
		self._config.create = create

	def _get_fs(self):
		'''Get fs'''
		try:
			self._config.fs = self._rev_fs[self._fs.get()]
		except Exception as ex:
			return ex
		self._config.fs = self._rev_fs[self._fs.get()]

	def _get_label(self):
		'''Get label and verify if it matches file system restrictions'''
		try:
			label = self.Drives.check_fs_label(self._label.get(), self._config.fs)
		except Exception as ex:
			return ex
		self._config.label = label

	def _start(self):
		'''Start wiping'''
		if ex := self._get_task():
			showerror(title=self._labels.error, message=f'{type(ex)}: {ex}')
			return
		if ex := self._get_value():
			showerror(title=self._labels.error, message=f'{self._labels.value_error}\n\n{type(ex)}: {ex}')
			return
		if ex := self._get_blocksize():
			showerror(title=self._labels.error, message=f'{self._labels.blocksize_error}\n\n{type(ex)}: {ex}')
			return
		if ex := self._get_maxbadblocks():
			showerror(title=self._labels.error, message=f'{self._labels.maxbadblocks_error}\n\n{type(ex)}: {ex}')
			return
		if ex := self._get_maxretries():
			showerror(title=self._labels.error, message=f'{self._labels.maxretries_error}\n\n{type(ex)}: {ex}')
			return
		if ex := self._get_create():
			showerror(title=self._labels.error, message=f'{type(ex)}: {ex}')
			return
		if ex := self._get_fs():
			showerror(title=self._labels.error, message=f'{type(ex)}: {ex}')
			return
		if ex := self._get_label():
			showerror(title=self._labels.error, message=f'{self._labels.labels_error}\n\n{type(ex)}: {ex}')
			return


		self._start_button.configure(state='disabled')
		self._clear_info()
		#self._work_thread = WorkThread(self.target_id, self._config, self._labels, self._log_path, self._echo, self._finished)
		#self._work_thread.start()


	def _clear_info(self):
		'''Clear info text'''
		self._info_text.configure(state='normal')
		self._info_text.delete('1.0', 'end')
		self._info_text.configure(state='disabled')
		self._info_text.configure(foreground=self._info_fg, background=self._info_bg)
		self._warning_state = 'stop'

	def _quit_app(self):
		'''Quit app, ask when wipe processs is running'''
		if self._work_thread:
			if not askyesno(title=self._labels.warning, message=self._labels.running_warning):
				return
			try:
				self._work_thread.kill()
			except:
				pass
		self.destroy()

	def echo(self, *args, end=None):
		'''Write message to info field (ScrolledText)'''
		msg = ' '.join(f'{arg}' for arg in args)
		self._info_text.configure(state='normal')
		if not self._info_newline:
			self._info_text.delete('end-2l', 'end-1l')
		self._info_text.insert('end', f'{msg}\n')
		self._info_text.configure(state='disabled')
		if self._info_newline:
			self._info_text.yview('end')
		self._info_newline = end != '\r'

	def finished(self, returncode):
		'''Run this when worker has finished copy process'''
		self._work_thread = None
		if returncode == 'error':
			self._info_text.configure(foreground=self._defs.red_fg, background=self._defs.red_bg)
			self._warning_state = 'enable'
			showerror(title=self._labels.warning, message=self._labels.problems)
		elif returncode == 'green':
			self._info_text.configure(foreground=self._defs.green_fg, background=self._defs.green_bg)
			self._source_text.delete('1.0', 'end')
			self._destination.set('')
		self._start_button.configure(state='normal')
