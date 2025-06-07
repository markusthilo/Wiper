#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from worker import Wipe

worker = Wipe('\\\\.\\PHYSICALDRIVE1')
print(worker.run())
