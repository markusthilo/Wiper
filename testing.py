#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from lib.worker import Wipe
from lib.config import Config

worker = Wipe(
        '\\\\.\\PHYSICALDRIVE1',
        Path(__file__).parent / 'lastlog.txt',
		Path(__file__).parent / 'zd-win.exe',
        'Wiper Testing',
        Config(Path(__file__).parent / 'labels.json'),
		task = 'selective',
		value = '00',
		blocksize = 4096,
		maxbadblocks = 200,
		maxretries = 200,
		create = 'gpt',
		fs = 'ntfs',
		label = 'Volume',
		debug = True
)
print(worker.run())
