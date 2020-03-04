# -*- coding: utf-8 -*-
"""
Get the tenhou logs. Run with  -h  on the command line to get help

@author: ApplySci
"""

#%%       imports

# standard libraries

import argparse
import configparser
import functools
import json
import os
import sqlite3
import sys
from time import sleep

from selenium import webdriver
from tenhoulogs import TenhouLogs
from TenhouConfig import account_names, directory_name

outcome = 0

# temporarily redefine the print function so that it always flushes
print = functools.partial(print, flush=True)

# -----------------------------------------------------
#%%         process arguments

parser = argparse.ArgumentParser()
parser.add_argument(
    '-u', '--user',
    nargs='+',
    default=account_names,
    help='ID(s) of user, space-separated if more than one',
    action='store')
parser.add_argument(
    '-nf', '--no-firefox',
    help='no firefox',
    action='store_true')
parser.add_argument(
    '-c', '--chrome',
    help='chrome',
    action='store_true')
parser.add_argument(
    '--urls',
    help='URLs of games, space-separated, and all grouped together within a pair of double-quote marks',
    action='store')
parser.add_argument(
    '--ids',
    help='IDs of games, space-separated, and all grouped together within a pair of double-quote marks',
    action='store')
parser.add_argument(
    '--json',
    help='pass JSON on command line (NOT ROBUST)',
    action='store')
parser.add_argument(
    '--wait',
    help='wait for 5 minutes before updating files, to ensure Dropbox has synched',
    action='store_true')
parser.add_argument(
    '--force',
    help='force refresh of all games that can still be retrieved from tenhou.net',
    action='store_true')
parser.add_argument(
    '--no-web',
    help='do not retrieve anything from the web',
    action='store_true')

args = parser.parse_args()
if len(sys.argv) < 2:
    print('-h on the command line shows help')

# -----------------------------------------------------
#%%         initialise variables

if sys.platform == 'win32': # all windows, 32-bit or 64-bit
    firefoxdir = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', '')
    chromeProfile = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', '')
# 'darwin': # mac
#    no idea what to do
#'linux': # linux
#   try something like:
#   firefoxdir = os.environ['HOME'] + '.mozilla/firefox/'
# chromedirs = ['~/.config/chromium/*/Local Storage/leveldb',
# '~/.config/google-chrome/*/Local Storage/leveldb',]

games_discovered = []

#%%

def one_browser_logs(thisbrowser):
    """
    get the logs from localStorage of a browser managed by selenium
    """
    try:
        thisbrowser.set_window_position(-3000, 0)
        thisbrowser.get('https://tenhou.net/2/')

        for i in range(0, 40):
            log = thisbrowser.execute_script("return localStorage.getItem('log%d')" % i)
            if log is not None:
                games_discovered.append(json.loads(log))
    finally:
        thisbrowser.quit()


def get_firefox_games(profile_dir):
    """
    retrieve games from Firefox localStorage:

    """

    config = configparser.ConfigParser()
    config.read(profile_dir + 'profiles.ini')
    firefox_profile = profile_dir + config['Profile0']['Path']
    try:
        print('finding firefox files')
        with sqlite3.connect(os.path.join(firefox_profile, 'webappsstore.sqlite')) as db:
            cur = db.cursor()
            cur.execute("SELECT * FROM webappsstore2 WHERE originKey LIKE 'ten.uohnet%' AND key LIKE 'log%'")
            for row in cur.fetchall():
                if row[3][3].isdigit():
                    games_discovered.append(json.loads(row[4]))
    except:
        # can't open firefox db directly, so go via browser
        try:
            print('firing up firefox')
            browser = webdriver.Firefox(webdriver.FirefoxProfile(firefox_profile))
            one_browser_logs(browser)
        except:
            print('error during firefox localStorage processing')


def decode_chrome_leveldb_bytes(value):
    """
    decode the encoded localstorage values from the leveldb file
    """
    if value[0] == 0:
        return value[1:].decode('utf-16le')
    elif value[0] == 1:
        return value[1:].decode('utf-8')
    else:
        msg = "Unable to process Chrome LevelDB bytes in unknown format: {}".format(value)
        print(msg)
        raise ValueError(msg)


def get_chrome_games(profile_dir):
    """
    retrieve games from Chrome localStorage
    """
    try:
        print('catching chrome config')
        leveldb_directory = os.path.join(profile_dir, 'Default', 'Local Storage', 'leveldb','')
        import leveldb
        # the below line fails with a "missing files e.g. 005.sst". This python lib seems
        # incompatible with the new google chrome leveldb
        db = leveldb.LevelDB(leveldb_directory)
        for key, value in db.RangeIter(b'_http://tenhou.net\x00', b'_http://tenhou.net\x01', True):
            print(key)
            key = key.split(b'\x00', 1)[1]
            key = decode_chrome_leveldb_bytes(key)
            if key.startswith('log') and key != 'lognext':
                value = decode_chrome_leveldb_bytes(value)
                game = json.loads(value)
                print('adding %s' % game['log'])
                games_discovered.append(game)

    except:
        # can't open chrome db directly, so go via browser
        try:
            print('cranking up chrome')
            options = webdriver.ChromeOptions()
            options.add_argument('user-data-dir=%s' % profile_dir)
            options.add_argument('log-level=3')
            browser = webdriver.Chrome(options=options)
            one_browser_logs(browser)
        except:
            print('error during Chrome localStorage processing')

#%%         process data from browsers & command-line
if args.urls is not None:
    for url in args.urls.split():
        games_discovered.append({'log': url.split('log=')[1].split('&')[0]})

#%%
if args.ids is not None:
    for oneId in args.ids.split():
        games_discovered.append({'log': oneId})

#%%
if args.json:
    print('justifying json')
    games_discovered.append(TenhouLogs.add_json(args.json))

#%%
if args.no_firefox:
    print('finessing firefox')
elif os.path.isdir(firefoxdir):
    get_firefox_games(firefoxdir)
else:
    print('ERROR: failed to find firefox profile directory from %s' % firefoxdir)

#%%
if args.chrome:
    get_chrome_games(chromeProfile)
else:
    print('circumventing chrome')

# ------------------------------------------------------------
#%% wait (added this to give time for Dropbox to finish, when run from startup)
if args.wait:
    print('waiting for windows - end the wait with Ctrl-C')
    try:
        sleep(300)
    except KeyboardInterrupt:
        pass

# ------------------------------------------------------------
#%% merge with existing games
for one_user in args.user:
    print('----- ' + one_user + ' -----')
    logger = TenhouLogs(directory_name, one_user, args)
    logger.load()
    logger.add_games(games_discovered)
    logger.save()

try:
    os.remove(directory_name + 'geckodriver.log')
except:
    pass

sys.exit(outcome)