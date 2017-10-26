#!/usr/bin/python3

import glob
import json
import os
import sqlite3
import struct
import sys
from optparse import OptionParser
from urllib.parse import parse_qs
from urllib.request import urlopen
from urllib.error import HTTPError

table = [
    22136, 52719, 55146, 42104, 
    59591, 46934, 9248,  28891,
    49597, 52974, 62844, 4015,
    18311, 50730, 43056, 17939,
    64838, 38145, 27008, 39128,
    35652, 63407, 65535, 23473,
    35164, 55230, 27536, 4386,
    64920, 29075, 42617, 17294,
    18868, 2081
]

def tenhouHash(game):
    code_pos = game.rindex("-") + 1
    code = game[code_pos:]
    if code[0] == 'x':
        a,b,c = struct.unpack(">HHH", bytes.fromhex(code[1:]))     
        index = 0
        if game[:12] > "2010041111gm":
            x = int("3" + game[4:10])
            y = int(game[9])
            index = x % (33 - y)
        first = (a ^ b ^ table[index]) & 0xFFFF
        second = (b ^ c ^ table[index] ^ table[index + 1]) & 0xFFFF
        return game[:code_pos] + "{:04x}{:04x}".format(first, second)
    else:
        return game

p = OptionParser()
p.add_option('-d', '--directory',
        default=os.path.expanduser('~/.tenhou-game-xml'),
        help='Directory in which to store downloaded XML')
opts, args = p.parse_args()

if not os.path.exists(opts.directory):
    os.makedirs(opts.directory)

def get_game(logname):
    logname = tenhouHash(logname)
    target_fname = os.path.join(opts.directory, "{}.xml".format(logname))
    if not os.path.exists(target_fname):
        print("Downloading game {}".format(logname))
        try:
            resp = urlopen('http://e.mjv.jp/0/log/?' + logname)
            data = resp.read()
            with open(target_fname, 'wb') as f:
                f.write(data)
        except HTTPError as e:
            if e.code == 404:
                print("Could not download game {}. Is the game still in progress?".format(logname))
            else:
                raise

for arg in args:
    get_game(arg)

sol_files = []
for pattern in (
        '~/.config/chromium/*/Pepper Data/Shockwave Flash/WritableRoot/#SharedObjects/*/mjv.jp/mjinfo.sol',
        '~/.config/google-chrome/*/Pepper Data/Shockwave Flash/WritableRoot/#SharedObjects/*/mjv.jp/mjinfo.sol',
        '~/.macromedia/Flash_Player/#SharedObjects/*/mjv.jp/mjinfo.sol',
        '~/Library/Application Support/Google/Chrome/Default/Pepper Data/Shockwave Flash/WritableRoot/#SharedObjects/*/mjv.jp/mjinfo.sol',
        ):
    sol_files.extend(glob.glob(os.path.join(os.path.expanduser(pattern))))
sqlite_files = []
for pattern in (
        '~/.config/chromium/*/Local Storage/http_tenhou.net_0.localstorage',
        '~/.config/google-chrome/*/Local Storage/http_tenhou.net_0.localstorage',
        ):
    sqlite_files.extend(glob.glob(os.path.join(os.path.expanduser(pattern))))
leveldb_directories = []
for pattern in (
        '~/.config/chromium/*/Local Storage/leveldb',
        '~/.config/google-chrome/*/Local Storage/leveldb',
        ):
    leveldb_directories.extend(glob.glob(os.path.join(os.path.expanduser(pattern))))

for sol_file in sol_files:
    print("Reading Flash state file: {}".format(sol_file))
    with open(sol_file, 'rb') as f:
        data = f.read()
    # What follows is a limited parser for Flash Local Shared Object files -
    # a more complete implementation may be found at:
    # https://pypi.python.org/pypi/PyAMF
    header = struct.Struct('>HI10s8sI')
    magic, objlength, magic2, mjinfo, padding = header.unpack_from(data)
    offset = header.size
    assert magic == 0xbf
    assert magic2 == b'TCSO\0\x04\0\0\0\0'
    assert mjinfo == b'\0\x06mjinfo'
    assert padding == 0
    ushort = struct.Struct('>H')
    ubyte = struct.Struct('>B')
    while offset < len(data):
        length, = ushort.unpack_from(data, offset)
        offset += ushort.size
        name = data[offset:offset+length]
        offset += length
        amf0_type, = ubyte.unpack_from(data, offset)
        offset += ubyte.size
        # Type 2: UTF-8 String, prefixed with 2-byte length
        if amf0_type == 2:
            length, = ushort.unpack_from(data, offset)
            offset += ushort.size
            value = data[offset:offset+length]
            offset += length
        # Type 6: Undefined
        elif amf0_type == 6:
            value = None
        # Type 1: Boolean
        elif amf0_type == 1:
            value = bool(data[offset])
            offset += 1
        # Other types from the AMF0 specification are not implemented, as they
        # have not been observed in mjinfo.sol files. If required, see
        # http://download.macromedia.com/pub/labs/amf/amf0_spec_121207.pdf
        else:
            print("Unimplemented AMF0 type {} at offset={} (hex {})".format(amf0_type, offset, hex(offset)))
        trailer_byte = data[offset]
        assert trailer_byte == 0
        offset += 1
        if name == b'logstr':
            loglines = filter(None, value.split(b'\n'))

    for logline in loglines:
        logname = parse_qs(logline.decode('ASCII'))['file'][0]
        get_game(logname)

for sqlite_file in sqlite_files:
    print("Reading Chrome localstorage: {}".format(sqlite_file))
    db = sqlite3.connect(sqlite_file)
    c = db.cursor()
    c.execute('SELECT key, value FROM ItemTable')
    for key, value in c.fetchall():
        value = value.decode('utf-16le')
        if key.startswith('log') and key != 'lognext':
            obj = json.loads(value)
            get_game(obj['log'])
    c.close()
    db.close()

def decode_chrome_leveldb_bytes(value):
    if value[0] == 0:
        return value[1:].decode('utf-16le')
    elif value[0] == 1:
        return value[1:].decode('utf-8')
    else:
        sys.exit("Unable to process Chrome LevelDB bytes in unknown format: {}".format(value))

if leveldb_directories:
    try:
        import leveldb
    except ImportError:
        sys.exit("Please install the Python 'leveldb' module to enable reading Chrome/Chromium 61 or later Local Storage")
    for leveldb_directory in leveldb_directories:
        print("Reading Chrome localstorage: {}".format(leveldb_directory))
        db = leveldb.LevelDB(leveldb_directory)
        for key, value in db.RangeIter(b'_http://tenhou.net\x00', b'_http://tenhou.net\x01', True):
            key = key.split(b'\x00', 1)[1]
            key = decode_chrome_leveldb_bytes(key)
            if key.startswith('log') and key != 'lognext':
                value = decode_chrome_leveldb_bytes(value)
                obj = json.loads(value)
                get_game(obj['log'])
