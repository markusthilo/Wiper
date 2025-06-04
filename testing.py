#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from lib.winutils import Drives

drives = Drives()

print(
    drives.get_children_of('\\\\.\\PHYSICALDRIVE1')
)