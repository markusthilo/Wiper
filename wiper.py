#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__application__ = 'Wiper'
__description__ = 'Windows GUI tool to securely wipe drives with option to treat SSDs gently.'
__version__ = '0.2.0_2025-06-19'
__status__ = 'Testing'
__license__ = 'GPL-3'
__author__ = 'Markus Thilo'
__email__ = 'markus.thilomarkus@gmail.com'

from sys import executable as __executable__
from threading import Thread, Event
from pythoncom import CoInitialize, CoUninitialize
from pathlib import Path
from ctypes import windll
from subprocess import run
from tkinter import Tk, PhotoImage, StringVar, BooleanVar, Checkbutton, Toplevel
from tkinter.font import nametofont
from tkinter.ttk import Frame, Label, Entry, Button, Combobox, Treeview
from tkinter.ttk import Scrollbar, Spinbox, Progressbar
from tkinter.scrolledtext import ScrolledText
from tkinter.messagebox import showerror, askokcancel, askyesno, showwarning
from idlelib.tooltip import Hovertip
from worker import Wipe
from classes_wiper import Config, Drives

__parent_path__ = Path(__file__).parent if Path(__executable__).stem == 'python' else Path(__executable__).parent

class WorkThread(Thread):
	'''The worker has tu run as thread not to freeze GUI/Tk'''

	def __init__(self, target_id, echo, finish):
		'''Pass arguments to worker'''
		super().__init__()
		self._finish = finish
		self._kill_event = Event()
		try:
			self._worker = Wipe(target_id, echo=echo, kill=self._kill_event, finish=self._finish)
		except Exception as ex:
			self._finish(ex)

	def kill(self):
		'''Kill thread'''
		self._kill_event.set()

	def kill_is_set(self):
		'''Return True if kill event is set'''
		return self._kill_event.is_set()

	def run(self):
		'''Run thread'''
		CoInitialize()
		try:
			returncode = self._worker.run()
		except Exception as ex:
			returncode = ex
		CoUninitialize()
		self._finish(returncode)

class Gui(Tk):
	'''GUI look and feel'''

	def __init__(self):
		'''Open application window'''
		super().__init__()
		self._defs = Config(__parent_path__ / 'gui.json')
		self._labels = Config(__parent_path__ / 'labels.json')
		self._config = Config(__parent_path__ / 'config.json')
		self._config.application = __application__
		self._config.version = __version__
		self._work_thread = None
		self._drives = Drives()
		self._target_id = None
		self._forbidden_ids = self._drives.get_system_ids()	# drives not to selected
		drive_id = f'{Path(__file__).drive}'	# prevent wiping drive of this application
		self._forbidden_ids.add(drive_id)
		if parent_id := self._drives.get_parent_of(drive_id):
			self._forbidden_ids.add(parent_id)
		if drive_id := f'{Path().home().drive}':
			self._forbidden_ids.add(drive_id)
			if parent_id := self._drives.get_parent_of(drive_id):
				self._forbidden_ids.add(drive_id)
		self._drive_dump = None	# to check for changes
		self.title(f'{__application__} v{__version__}')	### define the gui ###
		for row, weight in enumerate(self._defs.row_weights):
			self.rowconfigure(row, weight=weight)
		for column, weight in enumerate(self._defs.column_weights):
			self.columnconfigure(column, weight=weight)
		self.iconphoto(True, PhotoImage(file=__parent_path__ / 'appicon.png'))
		self.protocol('WM_DELETE_WINDOW', self._quit_app)
		self._font = nametofont('TkTextFont').actual()
		min_size_x = self._font['size'] * self._defs.x_factor
		min_size_y = self._font['size'] * self._defs.y_factor
		self.minsize(min_size_x , min_size_y)
		self.geometry(f'{min_size_x}x{min_size_y}')
		self.resizable(True, True)
		self._pad = int(self._font['size'] * self._defs.pad_factor)
		self._id_width = self._font['size'] * self._defs.tree_id
		self._info_width = self._font['size'] * self._defs.tree_info
		self._size_width = self._font['size'] * self._defs.tree_size
		self._drive_frame = Frame(self)	### drive tree ###
		self._drive_frame.grid(row=0, column=0, columnspan=3, sticky='nsew', padx=self._pad, pady=self._pad)
		self._start_text = StringVar(value=self._labels.select_target)	
		self._start_button = None
		self._drive_tree = Treeview(self._drive_frame,
			selectmode = 'browse',
			columns = ('Info', 'Size'),
			show = 'tree'
		)
		self._drive_tree.column('#0', width=self._id_width, stretch='no')
		self._drive_tree.column('Info', minwidth=self._info_width, stretch='yes') 
		self._drive_tree.column('Size', width = self._size_width, stretch='no')
		self._drive_tree.tag_configure('forbidden', foreground=self._defs.red_fg, background=self._defs.red_bg)
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
			state = 'readonly'
		)
		self._task_selector.grid(row=1, column=0, sticky='nwe', padx=self._pad)
		Hovertip(self._task_selector, self._labels.task_tip)
		self._rev_tasks = dict(zip(self._labels.tasks.values(), self._labels.tasks))
		frame = Frame(self)	### value ###
		frame.grid(row=1, column=1, sticky='nwe', pady=(0, self._pad))
		label = Label(frame, text=f'{self._labels.value}:')
		label.pack(side='left', padx=(self._pad, 0))
		self._value_box = Spinbox(frame, values=tuple(f'{b:02x}' for b in range(0x100)), width=self._defs.box_width)
		self._value_box.pack(side='right', padx=(0, self._pad))
		self._value_box.set(self._config.value)
		Hovertip(frame, self._labels.value_tip)
		Hovertip(label, self._labels.value_tip)
		frame = Frame(self)	### blocksize ###
		frame.grid(row=1, column=2, sticky='nwe', pady=(0, self._pad))
		Label(frame, text=f'{self._labels.blocksize}:').pack(side='left', padx=(self._pad, 0))
		self._blocksize_box = Spinbox(frame,
			values = (0x200, 0x400, 0x800) + tuple(0x1000 * p for p in range(1, 201)),
			width= self._defs.box_width
		)
		self._blocksize_box.pack(side='right', padx=(0, self._pad))
		self._blocksize_box.set(self._config.blocksize)
		Hovertip(frame, self._labels.blocksize_tip)
		frame = Frame(self)	### maxbadblocks ###
		frame.grid(row=2, column=1, sticky='nwe')
		label = Label(frame, text=f'{self._labels.maxbadblocks}:')
		label.pack(side='left', padx=(self._pad, 0))
		self._maxbadblocks_box = Spinbox(frame, from_=0, to=0xffff, width=self._defs.box_width)
		self._maxbadblocks_box.pack(side='right', padx=(0, self._pad))
		self._maxbadblocks_box.set(self._config.maxbadblocks)
		Hovertip(frame, self._labels.maxbadblocks_tip)
		Hovertip(label, self._labels.maxbadblocks_tip)
		frame = Frame(self)	### maxretries ###
		frame.grid(row=2, column=2, sticky='nwe')
		label = Label(frame, text=f'{self._labels.maxretries}:')
		label.pack(side='left', padx=(self._pad, 0))
		self._maxretries_box = Spinbox(frame, from_=0, to=0xffff, width=self._defs.box_width)
		self._maxretries_box.pack(side='right', padx=(0, self._pad))
		self._maxretries_box.set(self._config.maxretries)
		Hovertip(frame, self._labels.maxretries_tip)
		Hovertip(label, self._labels.maxretries_tip)
		self._create = StringVar(value=self._labels.create[self._config.create])	### create ###
		self._create_selector = Combobox(self,
			textvariable = self._create,
			values = tuple(self._labels.create.values()),
			state = 'readonly'
		)
		self._create_selector.grid(row=3, column=0, sticky='nwe', padx=self._pad, pady=self._pad)
		Hovertip(self._create_selector, self._labels.create_tip)
		self._rev_create = dict(zip(self._labels.create.values(), self._labels.create))
		self._fs = StringVar(value=self._labels.fs[self._config.fs])	### fs ###
		self._fs_selector = Combobox(self,
			textvariable = self._fs,
			values = tuple(self._labels.fs.values()),
			state = 'readonly'
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
		Hovertip(self._label_entry, self._labels.label_tip)
		self._start_button = Button(self, textvariable=self._start_text, command=self._start, state='disabled')	### start ###
		self._start_button.grid(row=3, rowspan=2, column=2, sticky='nswe', padx=self._pad, pady=(self._pad, 0))
		Hovertip(self._start_button, self._labels.wipe_tip)
		self._info_text = ScrolledText(self, font=(self._font['family'], self._font['size']), padx=self._pad, pady=self._pad)
		self._info_text.grid(row=5, column=0, columnspan=3, sticky='nsew',	### info text ###
			ipadx=self._pad, ipady=self._pad, padx=self._pad, pady=self._pad)
		self._info_text.bind('<Key>', lambda dummy: 'break')
		self._info_text.configure(state='disabled')
		self._info_fg = self._info_text.cget('foreground')
		self._info_bg = self._info_text.cget('background')
		self._info_newline = True
		self._shutdown = BooleanVar(value=False)	### shutdown after finish
		self._shutdown_button = Checkbutton(self,
			text = self._labels.shutdown,
			variable = self._shutdown,
			command = self._toggle_shutdown
		)
		self._shutdown_button.grid(row=6, column=0, sticky='nsw', padx=self._pad, pady=(0, self._pad))
		Hovertip(self._shutdown_button, self._labels.shutdown_tip)
		self._info_label = Label(self)	### info label ###
		self._info_label.grid(row=6, column=1, sticky='nsw', padx=self._pad, pady=(0, self._pad))
		self._label_fg = self._info_label.cget('foreground')
		self._label_bg = self._info_label.cget('background')
		self._quit_text = StringVar(value=self._labels.quit)	### quit ###
		self._quit_button = Button(self, textvariable=self._quit_text, command=self._quit_app)
		self._quit_button.grid(row=6, column=2, sticky='nse', padx=self._pad, pady=(0, self._pad))
		Hovertip(self._quit_button, self._labels.quit_tip)
		if windll.shell32.IsUserAnAdmin() == 0:
			msg = self._labels.admin_required.replace('#', __application__)
			showerror(self._labels.error, msg)
			raise SystemExit(msg)
		self._refresh_counter = 0	# to check devices every 2 seconds
		self._warning_state = 'disabled'	# no warning info
		self._refresh_loop()	# handle warning and observe drives

	def _gen_drive_tree(self):
		'''Refresh drive tree'''
		try:
			new_drive_dump = self._drives.dump()
		except:
			new_drive_dump = self._drive_dump
		if new_drive_dump != self._drive_dump:
			self._drive_dump = new_drive_dump
			self._drive_tree.delete(*self._drive_tree.get_children())
			current_ids = set()
			for drive_dict in self._drive_dump:
				drv_id = drive_dict['DeviceID']
				current_ids.add(drv_id)
				infos = list()
				if drive_dict['Caption']:
					infos.append(drive_dict['Caption'])
				if drive_dict['MediaType']:
					infos.append(drive_dict['MediaType'])
				if drive_dict['InterfaceType']:
					infos.append(drive_dict['InterfaceType'])
				values = (', '.join(infos), drive_dict['Size'] if drive_dict['Size'] else '')
				if drv_id in self._forbidden_ids:
					self._drive_tree.insert('', 'end', text=drv_id, values=values, iid=drv_id, open=True, tags='forbidden')
				else:
					self._drive_tree.insert('', 'end', text=drv_id, values=values, iid=drv_id, open=True)
				for part_dict in drive_dict['Partitions']:
					part_id = part_dict['DeviceID']
					current_ids.add(part_id)
					infos = list()
					if part_dict['VolumeName']:
						infos.append(part_dict['VolumeName'])
					if part_dict['FileSystem']:
						infos.append(part_dict['FileSystem'])
					values = (', '.join(infos), part_dict['Size'] if part_dict['Size'] else '')
					if part_id in self._forbidden_ids:
						self._drive_tree.insert(drv_id, 'end', text=part_id, values=values, iid=part_id, tags='forbidden')
					else:
						self._drive_tree.insert(drv_id, 'end', text=part_id, values=values, iid=part_id)
			if not self._target_id in current_ids and self._start_button:
				self._start_text.set(self._labels.select_target)
				self._start_button.configure(state='disabled')
				self._target_id = None

	def _select_drive(self, event):
		'''Run on double click'''
		if item := self._drive_tree.identify('item', event.x, event.y):
			if item in self._forbidden_ids:
				self._start_text.set(self._labels.select_target)
				self._start_button.configure(state='disabled')
				self._target_id = None
				return
			self._target_id = self._drives.get_parent_of(item)
			self._get_task()
			self._start_button.configure(state='normal')
			self._info_text.configure(foreground=self._info_fg, background=self._info_bg)
			self._warning_state = 'stop'

	def _refresh_loop(self):
		'''Show flashing warning'''
		self._get_task()
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

	def _clear_info(self):
		'''Clear info text'''
		self._info_text.configure(state='normal')
		self._info_text.delete('1.0', 'end')
		self._info_text.configure(state='disabled')
		self._info_text.configure(foreground=self._info_fg, background=self._info_bg)
		self._warning_state = 'stop'

	def _get_task(self):
		'''Get task'''
		try:
			task = self._rev_tasks[self._task.get()]
		except Exception as ex:
			return ex
		else:
			self._config.task = task
		finally:
			if self._target_id:
				if self._config.task == 'verify':
					self._start_text.set(self._labels.verify.replace('#', self._target_id))
				else:
					self._start_text.set(self._labels.wipe.replace('#', self._target_id))

	def _get_value(self):
		'''Get value'''
		try:
			value = int(self._value_box.get(), 16)
		except Exception as ex:
			return ex
		if value < 0 or value > 0xff:
			return ValueError(f'value out of range: {value}')
		self._config.value = f'{value:02x}'

	def _get_blocksize(self):
		'''Get block size'''
		try:
			blocksize = int(self._blocksize_box.get())
		except Exception as ex:
			return ex
		if blocksize < 0x100 or blocksize % 0x100 != 0:
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
		if self._config.fs != 'none':
			try:
				label = self._drives.check_fs_label(self._label.get(), self._config.fs)
			except Exception as ex:
				return
		else:
			label = self._label.get()
		self._config.label = label

	def _start(self):
		'''Start wiping'''
		target = self._target_id
		if logical := self._drives.get_children_of(self._target_id):
			target += f' ({", ".join(logical)})'
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
		if ex := self._get_label() and self._config.create != 'none' and self._config.fs != 'none':
			showerror(title=self._labels.error, message=f'{self._labels.label_error}\n\n{type(ex)}: {ex}')
			return
		try:
			self._config.save()
		except:
			showerror(title=self._labels.error, message=self._labels.start_replace('#', self.config.path))
			return
		if self._config.task == 'verify':
			if self._config.create != 'none' and not askokcancel(
					title = self._labels.warning,
					message = self._labels.verify_warning.replace('#', target)
				):
					return
		elif not askokcancel(
				title = self._labels.warning,
				message = self._labels.wipe_warning.replace('#', target)
			):
				return
		self._start_button.configure(state='disabled')
		self._task_selector.configure(state='disabled')
		self._value_box.configure(state='disabled')
		self._maxbadblocks_box.configure(state='disabled')
		self._maxretries_box.configure(state='disabled')
		self._create_selector.configure(state='disabled')
		self._fs_selector.configure(state='disabled')
		self._label_entry.configure(state='disabled')
		self._blocksize_box.configure(state='disabled')
		self._quit_text.set(self._labels.abort)
		self._clear_info()
		self._work_thread = WorkThread(self._target_id, self.echo, self.finished)
		self._work_thread.start()

	def _toggle_shutdown(self):
		'''Toggle select switch to shutdown after finish'''
		if self._shutdown.get():
			self._shutdown.set(False)
			if askyesno(title=self._labels.warning, message=self._labels.shutdown_warning):
				self._shutdown.set(True)

	def _reset(self):
		'''Reset buttons'''
		self._start_text.set(self._labels.select_target)
		self._start_button.configure(state='disabled')
		self._task_selector.configure(state='normal')
		self._value_box.configure(state='normal')
		self._maxbadblocks_box.configure(state='normal')
		self._maxretries_box.configure(state='normal')
		self._create_selector.configure(state='normal')
		self._fs_selector.configure(state='normal')
		self._label_entry.configure(state='normal')
		self._blocksize_box.configure(state='normal')
		self._shutdown.set(False)
		self._quit_text.set(self._labels.quit)
		self._target_id = None
		self._work_thread = None

	def _quit_app(self):
		'''Quit app or ask to abort process'''
		if self._work_thread:	
			if self._work_thread.kill_is_set():
				self._reset()
			else:
				if askokcancel(title=self._labels.warning, message=self._labels.abort_warning):
					self._work_thread.kill() # kill running work thread
				return
		self._get_value()
		self._get_blocksize()
		self._get_maxbadblocks()
		self._get_maxretries()
		self._get_create()
		self._get_fs()
		self._get_label()
		try:
			self._config.save()
		except:
			pass
		self.destroy()

	def _enable_warning(self):
		'''Enable red text field and blinking Label'''
		self._info_text.configure(foreground=self._defs.red_fg, background=self._defs.red_bg)
		self._warning_state = 'enable'

	def _delay_shutdown(self):
		'''Delay shutdown and update progress bar'''
		if self._shutdown_cnt < self._defs.shutdown_delay:
			self._shutdown_cnt += 1
			self._delay_progressbar.step(1)
			self._shutdown_window.after(1000, self._delay_shutdown)
		else:
			run(['shutdown', '/s'])

	def _shutdown_dialog(self):
		'''Show shutdown dialog'''
		self._shutdown_window = Toplevel(self)
		self._shutdown_window.title(self._labels.warning)
		self._shutdown_window.transient(self)
		self._shutdown_window.focus_set()
		self._shutdown_window.resizable(False, False)
		self._shutdown_window.grab_set()
		frame = Frame(self._shutdown_window, padding=self._pad)
		frame.pack(fill='both', expand=True)
		Label(frame,
			text = '\u26A0',
			font = (self._font['family'], self._font['size'] * self._defs.symbol_factor),
			foreground = self._defs.symbol_fg,
			background = self._defs.symbol_bg
		).pack(side='left', padx=self._pad, pady=self._pad)
		Label(frame, text=self._labels.shutdown_question, anchor='s').pack(
			side='right', fill='both', padx=self._pad, pady=self._pad
		)
		frame = Frame(self._shutdown_window, padding=self._pad)
		frame.pack(fill='both', expand=True)
		self._delay_progressbar = Progressbar(frame, mode='determinate', maximum=self._defs.shutdown_delay)
		self._delay_progressbar.pack(side='top', fill='x', padx=self._pad, pady=self._pad)
		cancel_button = Button(frame, text=self._labels.cancel_shutdown, command=self._shutdown_window.destroy)
		cancel_button.pack(side='bottom', fill='both', padx=self._pad, pady=self._pad)
		self.update_idletasks()
		self._shutdown_cnt = 0
		self._delay_shutdown()
		self._shutdown_window.wait_window(self._shutdown_window)

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
		if returncode:
			if self._shutdown.get():	### Shutdown dialog ###
				self._shutdown_dialog()
			if isinstance(returncode, Exception):
				self._enable_warning()
				showerror(
					title = self._labels.error, 
					message = f'{self._labels.aborted_on_error}\n\n{type(returncode)}:\n{returncode}'
				)
			elif isinstance(returncode, str):
				self._enable_warning()
				showwarning(title=self._labels.warning, message=self._labels.process_returned.replace('#', returncode))
			else:
				self._info_text.configure(foreground=self._defs.green_fg, background=self._defs.green_bg)
		self._reset()

if __name__ == '__main__':  # start here when run as application
	Gui().mainloop()
