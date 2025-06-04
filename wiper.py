#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Markus Thilo'
__version__ = '0.0.1_2025-06-04'
__license__ = 'GPL-3'
__email__ = 'markus.thilomarkus@gmail.com'
__status__ = 'Testing'
__description__ = 'Windows GUI tool to securely wipe drives with option to treat SSDs gently.'

from sys import executable as __executable__
from pathlib import Path
from lib.config import Config
from lib.gui import Gui

__parent_path__ = Path(__file__).parent if Path(__executable__).stem == 'python' else Path(__executable__).parent

if __name__ == '__main__':  # start here when run as application
	Gui(
		__parent_path__.joinpath('lastlog.log').absolute(),
		__parent_path__.joinpath('appicon.png').absolute(),
		__parent_path__.joinpath('zd-win.exe').absolute(),
		f'Wiper v{__version__}',
		Config(__parent_path__.joinpath('config.json')),
		Config(__parent_path__.joinpath('gui.json')),
		Config(__parent_path__.joinpath('labels.json'))
	).mainloop()
