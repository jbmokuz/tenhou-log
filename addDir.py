# -*- coding: utf-8 -*-
"""
Add a directory of mjlog files
@author: ApplySci
"""

from pathlib import Path
from types import SimpleNamespace

from tenhoulogs import TenhouLogs

in_dir = Path('D:/ZAPS/Rosti/Tokujou/')
out_dir = 'C:/library/Dropbox/source/tenhou/logs/'
account = 'RostiLFC'


logger = TenhouLogs(out_dir, account, SimpleNamespace(force=True, no_web=True))
logger.load()
try:
    for filepath in in_dir.glob('*.mjlog'):
        logger.add_from_file(filepath)
finally:
    logger.save()