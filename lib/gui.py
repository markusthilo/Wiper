#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from threading import Thread, Event
from pathlib import Path
from time import strftime
from tkinter import Tk, PhotoImage, StringVar, BooleanVar
from tkinter.font import nametofont
from tkinter.ttk import Frame, Label, Entry, Button, Style, Combobox, Treeview
from tkinter.ttk import Scrollbar, Spinbox
from tkinter.scrolledtext import ScrolledText
from tkinter.messagebox import askyesno, showerror
from tkinter.filedialog import askdirectory, askopenfilenames, asksaveasfilename
from idlelib.tooltip import Hovertip
from lib.winutils import Drives
from tkinter import IntVar
#from lib.worker import Wipe

class WorkThread(Thread):
	'''The worker has tu run as thread not to freeze GUI/Tk'''

	def __init__(self,
		device_id,
		app_path,
		labels,
		verify,
		allbytes,
		extra,
		value,
		blocksize,
		maxbadblocks,
		maxretries,
		label,
		drive,
		mbr,
		fs,
		log,
		echo,
		kill,
		finish
	):
		'''Pass arguments to worker'''
		super().__init__()
		self._finish = finish
		self._kill_event = Event()
		self._worker = Wipe(self, device_id, app_path, labels,
			verify = verify,
			allbytes = allbytes,
			extra = extra,
			value = value,
			blocksize = blocksize,
			maxbadblocks = maxbadblocks,
			maxretries = maxretries,
			label = label,
			drive = drive,
			mbr = mbr,
			fs = fs,
			log = log,
			echo = echo,
			kill = kill
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
		
		self.rowconfigure(5, weight=1)

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
		self._drive_frame = Frame(self)
		self._drive_frame.grid(row=0, column=0, columnspan=3, sticky='nsew')
		######################### DRIVE TREE ###############################################################
		self._drive_tree = Treeview(self._drive_frame,
			selectmode = 'browse',
			columns = ('Info', 'Size'),
			show = 'tree'
		)
		self._drive_tree.column('#0', width=self._id_width, stretch='no')
		self._drive_tree.column('Info', minwidth=self._info_width, stretch='yes') 
		self._drive_tree.column('Size', width = self._size_width, stretch='no')
		drives = Drives()
		for drive_dict in drives.dump():
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
		self._drive_tree.pack(side='right', expand=True, fill='both', padx=self._pad, pady=self._pad)
		self.bind('<Double-1>', self._select_focus)
		self._drive_tree.pack(side='left', expand=True)
		vsb = Scrollbar(self._drive_frame, orient='vertical', command=self._drive_tree.yview)
		vsb.pack(side='right', fill='y')
		self._drive_tree.configure(yscrollcommand=vsb.set)
		Hovertip(self._drive_tree, self._labels.drive_tip)
		##################################################################################################
		frame = Frame(self)
		frame.grid(row=1, column=0, sticky='nwe', pady=(0, self._pad))
		Label(frame, text=f'{self._labels.value}:').pack(side='left', padx=self._pad)
		self._value_box = Spinbox(frame, values=tuple(f'{b:02x}' for b in range(0x100)), width=3)
		self._value_box.pack(side='right', padx=self._pad)
		self._value_box.set(self._config.value)
		Hovertip(frame, self._labels.value_tip)
		frame = Frame(self)
		frame.grid(row=1, column=1, sticky='nwe', pady=(0, self._pad))
		Label(frame, text=f'{self._labels.blocksize}:').pack(side='left', padx=self._pad)
		self._blocksize_box = Spinbox(frame, from_=0, to=0xffff, width=6)
		self._blocksize_box.pack(side='right', padx=self._pad)
		self._blocksize_box.set(self._config.blocksize)
		Hovertip(frame, self._labels.blocksize_tip)

		frame = Frame(self)
		frame.grid(row=1, column=1, sticky='nwe')
		Label(frame, text=f'{self._labels.blocksize}:').pack(side='left', padx=self._pad)
		self._blocksize_box = Spinbox(frame, from_=0, to=0xffff, width=6)
		self._blocksize_box.pack(side='right', padx=self._pad)
		self._blocksize_box.set(self._config.blocksize)
		Hovertip(frame, self._labels.blocksize_tip)

		frame = Frame(self)
		frame.grid(row=2, column=0, sticky='nwe')
		Label(frame, text=f'{self._labels.maxbadblocks}:').pack(side='left', padx=self._pad)
		self._maxbadblocks_box = Spinbox(frame, from_=0, to=0xffff, width=6)
		self._maxbadblocks_box.pack(side='right', padx=self._pad)
		self._maxbadblocks_box.set(self._config.maxbadblocks)
		Hovertip(frame, self._labels.maxbadblocks_tip)

		frame = Frame(self)
		frame.grid(row=2, column=1, sticky='nwe')
		Label(frame, text=f'{self._labels.maxretries}:').pack(side='left', padx=self._pad)
		self._maxretries_box = Spinbox(frame, from_=0, to=0xffff, width=6)
		self._maxretries_box.pack(side='right', padx=self._pad)
		self._maxretries_box.set(self._config.maxretries)
		Hovertip(frame, self._labels.maxretries_tip)


		self._task = StringVar(value=self._labels.tasks[self._config.task])
		self._task_selector = Combobox(self,
			textvariable = self._task,
			values = tuple(self._labels.tasks.values()),
			state = 'readonly',
		)
		self._task_selector.grid(row=4, column=0, sticky='nwe', padx=self._pad, pady=self._pad)
		Hovertip(self._task_selector, self._labels.task_tip)
		self._create = StringVar(value=self._labels.create[self._config.create])
		self._create_selector = Combobox(self,
			textvariable = self._create,
			values = tuple(self._labels.create.values()),
			state = 'readonly',
		)
		self._create_selector.grid(row=4, column=1, sticky='nwe', padx=self._pad, pady=self._pad)
		Hovertip(self._create_selector, self._labels.create_tip)
		self._fs = StringVar(value=self._labels.fs[self._config.fs])
		self._fs_selector = Combobox(self,
			textvariable = self._fs,
			values = tuple(self._labels.fs.values()),
			state = 'readonly',
		)
		self._fs_selector.grid(row=4, column=2, sticky='nwe', padx=self._pad, pady=self._pad)
		Hovertip(self._fs_selector, self._labels.fs_tip)

		return
		self._choosen_verify = StringVar(value=self._labels.verify)
		self._verify_selector = Combobox(self,
			textvariable = self._choosen_verify,
			values = list(self._gen_verify_list().values()),
			state='readonly'
		)
		self._verify_selector.pack(side='right', anchor='ne', padx=self._pad, pady=self._pad)
		self._verify_selector.bind('<<ComboboxSelected>>', self._verify_event)
		Hovertip(self._verify_selector, self._labels.verify_tip)

		return

	
		self._source_dir_button = Button(frame, text=self._labels.directory, command=self._select_source_dir)
		self._source_dir_button.pack(anchor='nw', padx=self._pad, pady=self._pad)
		Hovertip(self._source_dir_button, self._labels.source_dir_tip)
		self._source_file_button = Button(frame, text=self._labels.file_s, command=self._select_source_files)
		self._source_file_button.pack(anchor='nw', padx=self._pad, pady=self._pad)
		Hovertip(self._source_file_button, self._labels.source_file_tip)
		self._source_text = ScrolledText(self, font=(font_family, font_size))
		self._source_text.grid(row=0, column=1, sticky='nsew', ipadx=self._pad, ipady=self._pad, padx=self._pad, pady=self._pad)
		self._destination_button = Button(self, text=self._labels.destination, command=self._select_destination)
		self._destination_button.grid(row=1, column=0, sticky='nw', padx=self._pad, pady=self._pad)
		self._destination = StringVar()
		self._destination_entry = Entry(self, textvariable=self._destination)
		self._destination_entry.grid(row=1, column=1, sticky='nsew', padx=self._pad, pady=self._pad)
		Hovertip(self._destination_button, self._labels.destination_tip)
		frame = Frame(self)
		frame.grid(row=2, column=1, sticky='nw')
		self.possible_hashes = FileHash.get_algorithms()
		self._choosen_hash = StringVar(value=self._labels.hash)
		self._hash_selector = Combobox(frame, values=self._gen_hash_list(), state='readonly', textvariable=self._choosen_hash)
		self._hash_selector.pack(side='left', anchor='nw', padx=self._pad, pady=self._pad)
		self._hash_selector.bind('<<ComboboxSelected>>', self._hash_event)
		Hovertip(self._hash_selector, self._labels.hash_tip)
		self._choosen_verify = StringVar(value=self._labels.verify)
		self._verify_selector = Combobox(frame, values=self._gen_verify_list(), state='readonly', textvariable=self._choosen_verify)
		self._verify_selector.pack(side='right', anchor='ne', padx=self._pad, pady=self._pad)
		self._verify_selector.bind('<<ComboboxSelected>>', self._verify_event)
		Hovertip(self._verify_selector, self._labels.verify_tip)
		self._log_button = Button(self, text=self._labels.log, command=self._select_log)
		self._log_button.grid(row=3, column=0, sticky='nw', padx=self._pad, pady=self._pad)
		self._log = StringVar(value=self._config.log_dir)
		self._log_entry = Entry(self, textvariable=self._log)
		self._log_entry.grid(row=3, column=1, sticky='nsew', padx=self._pad, pady=self._pad)
		Hovertip(self._log_button, self._labels.log_tip)
		self._simulate_button_text = StringVar(value=self._labels.simulate_button)
		self._simulate_button = Button(self, textvariable=self._simulate_button_text, command=self._simulate)
		self._simulate_button.grid(row=4, column=0, sticky='w', padx=self._pad, pady=self._pad)
		Hovertip(self._simulate_button, self._labels.simulate_tip)
		self._exec_button = Button(self, text=self._labels.exec_button, command=self._execute)
		self._exec_button.grid(row=4, column=1, sticky='e', padx=self._pad, pady=self._pad)
		Hovertip(self._exec_button, self._labels.exec_tip)
		self._info_text = ScrolledText(self, font=(font_family, font_size), padx=self._pad, pady=self._pad)
		self._info_text.grid(row=5, column=0, columnspan=2, sticky='nsew',
			ipadx=self._pad, ipady=self._pad, padx=self._pad, pady=self._pad)
		self._info_text.bind('<Key>', lambda dummy: 'break')
		self._info_text.configure(state='disabled')
		self._info_fg = self._info_text.cget('foreground')
		self._info_bg = self._info_text.cget('background')
		self._info_newline = True
		self._info_label = Label(self)
		self._info_label.grid(row=6, column=0, sticky='w', padx=self._pad, pady=self._pad)
		self._label_fg = self._info_label.cget('foreground')
		self._label_bg = self._info_label.cget('background')
		self._quit_button = Button(self, text=self._labels.quit, command=self._quit_app)
		self._quit_button.grid(row=6, column=1, sticky='e', padx=self._pad, pady=self._pad)
		Hovertip(self._quit_button, self._labels.quit_tip)
		self._init_warning()

	def _select(self):
		'''Set target'''
		if focus := self._drive_tree.focus():
			print(focus)
		else:
			print('no focus')

	def _select_focus(self, event):
		'''Run on double click'''
		item = self._drive_tree.identify('item', event.x, event.y)
		print(self._drive_tree.item(item)['text'])



	def _read_source_paths(self):
		'''Read paths from text field'''
		if text := self._source_text.get('1.0', 'end').strip():
			return [Path(line.strip()).absolute() for line in text.split('\n')]
		return ()

	def _chck_source_path(self, source):
		'''Check if source path is valid'''
		if not source:
			return
		path = Path(source)
		if path.exists():
			return path
			showerror(title=self._labels.error, message=self._labels.src_path_not_found.replace('#', f'{path}'))

	def _select_source_dir(self):
		'''Select directory to add into field'''
		if directory := askdirectory(title=self._labels.select_dir, mustexist=True):
			path = Path(directory).absolute()
			if path in self._read_source_paths():
				showerror(title=self._labels.error, message=self._labels.already_added.replace('#', f'{path}'))
				return
			self._source_text.insert('end', f'{path}\n')

	def _select_source_files(self):
		'''Select file(s) to add into field'''
		if filenames := askopenfilenames(title=self._labels.select_files):
			for filename in filenames:
				path = Path(filename).absolute()
				if path in self._read_source_paths():
					showerror(title=self._labels.error, message=self._labels.already_added.replace('#', f'{path}'))
					return
				self._source_text.insert('end', f'{path}\n')

	def _get_source_paths(self):
		'''Get source paths from text field'''
		unverified_paths = self._read_source_paths()
		if not unverified_paths:
			showerror(title=self._labels.error, message=self._labels.no_source)
			return
		src_paths = list()
		for path in unverified_paths:
			src_path = self._chck_source_path(path)
			if not src_path:
				return
			src_paths.append(src_path)
		return src_paths

	def _select_destination(self):
		'''Select destination directory'''
		if dst_dir := askdirectory(title=self._labels.select_destination, mustexist=False):
			self._destination.set(dst_dir)
	
	def _get_destination_path(self):
		'''Get destination directory'''
		dst_dir = self._destination.get()
		if not dst_dir:
			showerror(title=self._labels.error, message=self._labels.no_destination)
			return
		dst_path = Path(dst_dir).absolute()
		if not dst_path.exists():
			return dst_path
		if not dst_path.is_dir():
			showerror(self._labels.error, self._labels.dst_no_dir.replace('#', f'{dst_path}'))
			return
		top = dst_path.samefile(dst_path.parent)
		for path in dst_path.iterdir():
			if top and path.is_dir() and path.name.upper() in ('$RECYCLE.BIN', 'SYSTEM VOLUME INFORMATION'):
				continue
			if askyesno(self._labels.warning, self._labels.dst_not_empty.replace('#', f'{dst_path}')):
				break
			else:
				return
		return dst_path

	def _gen_hash_list(self):
		'''Generate list of hashes to check'''
		return [
			f'\u2611 {hash}' if hash in self._config.hashes else f'\u2610 {hash}'
			for hash in self.possible_hashes
		]

	def _gen_verify_list(self):
		'''Generate list of verification methodes'''
		return [
			f'\u2611 {self._labels.size}' if self._config.verify == 'size' else f'\u2610 {self._labels.size}'
		] + [
			f'\u2611 {hash}' if self._config.verify == hash else f'\u2610 {hash}'
			for hash in self._config.hashes
		]

	def _hash_event(self, dummy_event):
		'''Hash algorithm selection'''
		choosen = self._choosen_hash.get()[2:]
		self._choosen_hash.set(self._labels.hash)	# reset shown text
		if choosen in self._config.hashes:
			self._config.hashes.remove(choosen)
			if choosen == self._config.verify:
				self._config.verify = 'size'
		else:
			self._config.hashes.append(choosen)
			self._config.hashes.sort()
		self._hash_selector['values'] = self._gen_hash_list()
		self._verify_selector['values'] = self._gen_verify_list()

	def _verify_event(self, dummy_event):
		'''Hash algorithm selection'''
		choosen = self._choosen_verify.get()[2:]
		self._choosen_verify.set(self._labels.verify)	# reset shown text
		choosen = 'size' if choosen == self._labels.size else choosen
		if choosen == self._config.verify:
			self._config.verify = ''
		else:
			self._config.verify = choosen
		self._verify_selector['values'] = self._gen_verify_list()

	def _select_log(self):
		'''Select directory '''
		if directory := askdirectory(title=self._labels.select_log, mustexist=False):
			self._log.set(directory)
			self._config.log_dir = directory

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

	def _clear_info(self):
		'''Clear info text'''
		self._info_text.configure(state='normal')
		self._info_text.delete('1.0', 'end')
		self._info_text.configure(state='disabled')
		self._info_text.configure(foreground=self._info_fg, background=self._info_bg)
		self._warning_state = 'stop'

	def _mk_log_dir(self, log_dir):
		'''Create log directory if not exists'''
		if log_dir:
			try:
				log_dir_path = Path(log_dir).absolute()
				log_dir_path.mkdir(parents=True, exist_ok=True)
				self._config.log_dir = f'{log_dir_path}'
			except Exception as ex:
				showerror(
					title = self._labels.warning,
					message = f'{self._labels.invalid_log_path.replace("#", f"{log_dir_path}")}\n{type(ex)}: {ex}'
				)
				return
			return log_dir_path

	def _start_worker(self, src_paths, dst_path, simulate):
		'''Disable source selection and start worker'''
		log_dir_path = self._mk_log_dir(self._log_entry.get())
		if not log_dir_path and self._config.hashes and not simulate:
			self._select_log()
			if not self._config.log_dir:
				showerror(title=self._labels.warning, message=self._labels.log_required)
				return
			log_dir_path = self._mk_log_dir(self._log_entry.get())
			if not log_dir_path:
				return
		self._config.log_dir = log_dir_path
		try:
			self._config.save()
		except:
			pass
		self._exec_button.configure(state='disabled')
		self._clear_info()
		self._work_thread = WorkThread(
			src_paths,
			dst_path,
			self._app_path,
			self._labels,
			log_dir_path / strftime(self._config.tsv_name) if log_dir_path else None,
			log_dir_path / strftime(self._config.log_name) if log_dir_path else None,
			self._config.hashes,
			self._config.verify,
			simulate,
			self.echo,
			self.finished
		)
		self._work_thread.start()

	def _simulate(self):
		'''Run simulation'''
		src_paths = self._get_source_paths()
		if not src_paths:
			return
		dst_path = self._get_destination_path()
		if not dst_path:
			return
		if self._work_thread:
			self._simulate_button_text.set(self._labels.simulate_button)
			self._work_thread.kill()
			self._work_thread = None
		else:
			self._simulate_button_text.set(self._labels.stop_button)
			self._start_worker(src_paths, dst_path, True)

	def _execute(self):
		'''Start copy process / worker'''
		src_paths = self._get_source_paths()
		if not src_paths:
			return
		dst_path = self._get_destination_path()
		if not dst_path:
			return
		try:
			dst_path.mkdir(exist_ok=True)
		except Exception as ex:
			showerror(
				title = self._labels.warning,
				message = f'{self._labels.invalid_dst_path.replace("#", dst_dir)}\n{type(ex): {ex}}'
			)
			return
		self._simulate_button.configure(state='disabled')
		self._exec_button.configure(state='disabled')
		self._start_worker(
			src_paths,
			dst_path,
			False
		)

	def _init_warning(self):
		'''Init warning functionality'''
		self._warning_state = 'disabled'
		self._warning()

	def _warning(self):
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
		self.after(500, self._warning)

	def enable_buttons(self):
		'''Run this when worker has finished to eanable start buttons'''
		self._simulate_button_text.set(self._labels.simulate_button)
		self._simulate_button.configure(state='normal')
		self._exec_button.configure(state='normal')
		self._quit_button.configure(state='normal')
		self._work_thread = None

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
		self.enable_buttons()

	def _quit_app(self):
		'''Quit app, ask when copy processs is running'''
		#################################
		self.destroy()	##### DEBUG #####
		return	#########################
		#################################
		if self._work_thread:
			if not askyesno(title=self._labels.warning, message=self._labels.running_warning):
				return
			try:
				self._work_thread.kill()
			except:
				pass
		self._config.log_dir = self._log_entry.get()
		try:
			self._config.save()
		except:
			pass
		self.destroy()
