# -*- coding: utf-8 -*-
"""
Class for handling tenhou logs

@author: ApplySci
"""

#%%       imports

# standard libraries

from collections import OrderedDict
from itertools import chain
import json
import lzma
import pickle
from types import SimpleNamespace
import urllib

from lxml import etree
import portalocker
import requests

class TenhouLogs():
    """
            stores tenhou logs
    """
    GAMEURL = 'http://tenhou.net/3/mjlog2xml.cgi?%s'
    # 'http://e.mjv.jp/0/log/plainfiles.cgi?%s'

    def __init__(self, outdir, username, args={}):
        self.outdir = outdir
        self.username = username

        self._flags = SimpleNamespace()
        self._flags.force = args.force
        self._flags.need_to_sort = False
        self._flags.no_web = args.no_web
        self._flags.have_new = False
        self._lockfile = None
        self.logs = OrderedDict()
        self.pickle_file = outdir + username + '.pickle.7z'


    def _get_rates(self, xml, key):
        """
                for one game, get the R for each player at the start of the game,
                and the player names, and add them into the OrderedDict
        """
        players = xml.find('UN').attrib
        ratestrings = players['rate'].split(',')
        rates = [float(x) for x in ratestrings]
        self.logs[key]['meanrate'] = sum(rates)/len(rates)
        names = []
        found_player = False
        for j in range(0, 4):
            nextname = urllib.parse.unquote(players['n%d' % j])
            names.append(nextname)
            if nextname == self.username:
                self.logs[key]['rate'] = rates[j]
                found_player = True
        if found_player:
            self.logs[key]['uname'] = names
        else:
            print('ignoring, player not in %s' % ','.join(names))
            del self.logs[key]

        return found_player


    def _load_from_text(self, key, text):
        """ takes an mjlog text string in, and stores it as an xml object """
        try:
            xml = etree.XML(text, etree.XMLParser(recover=True)).getroottree().getroot()
        except:
            return
        if not self._get_rates(xml, key):
            return
        self._flags.have_new = True
        self._process_scores(xml, key)


    def _process_scores(self, xml, key):
        """
        for one game, get the scores for each player,
        rank them in descending order,
        and compile into a string to match nodocchi.moe
        Add this into the self record
        """
        xml_scores = xml.find('AGARI[@owari][last()]')
        draw_test = xml.find('RYUUKYOKU[@owari][last()]')
        if xml_scores is not None and draw_test is not None:
            print('WARNING: %s had both a win and a draw with final scores!' % key)
        if xml_scores is None:
            xml_scores = draw_test
        if xml_scores is not None:
            self.logs[key]['sc'] = xml_scores.attrib['owari']

        # take only the 0,2,4,6th elements of score
        scores = [float(x) for x in self.logs[key]['sc'].split(',')][1::2]
        sortedscores = sorted(scores, reverse=True)
        sortedplayers = sorted(self.logs[key]['uname'],
                               reverse=True,
                               key=lambda x: scores[self.logs[key]['uname'].index(x)])
        self.logs[key]['place'] = sortedplayers.index(self.username) + 1
        self.logs[key]['players'] = ''
        for i, player in enumerate(sortedplayers):
            self.logs[key]['players'] += '%s(%s%.1f)' % (
                player,
                "+" if sortedscores[i] > 0 else "",
                sortedscores[i])


    def one_record(self, store, last_key):
        """
                 incorporate one record into the log
        """

        key = store['log']
        if key in self.logs and not self._flags.force:
            return

        if key[0:10] < last_key:
            self._flags.need_to_sort = True

        if key not in self.logs:
            self.logs[key] = {}

        self.logs[key].update(store)

        if 'uname' in self.logs[key] and self.username not in self.logs[key]['uname']:
            del self.logs[key]
            return

        if not self._flags.no_web:
            print('gathering game: %s' % key)
            loghttp = requests.get(
                self.GAMEURL % key,
                headers={'referer': 'http://tenhou.net/3/?%s&tw=0' % key}
            )
            if loghttp.ok:
                self.logs[key]['content'] = loghttp.content
            else:
                print('WARNING: failed to download %s' % key)
        if 'content' not in self.logs[key]:
            del self.logs[key]
            return

        self._load_from_text(key, self.logs[key]['content'])


    def _find_place_and_rate(self, this_log, key_index, logkeys):
        """
        given a particular log, find our score, and check the R rates are consistent
        """

        # check that the progression of R-scores is consistent;
        # If it's not, swap the order of specific games when that improves things
        numself = len(logkeys)
        next_rate = (this_log['rate']
                     + (this_log['meanrate'] - this_log['rate']) / 200 # TODO assumes 400+ games played
                     + 10 - 4 * this_log['place'])
        if (this_log['meanrate']
                and key_index < numself - 1
                and abs(next_rate - self.logs[logkeys[key_index + 1]]['rate']) > 0.02):
            delta = 2
            while (key_index < numself - delta and
                   logkeys[key_index + 1][0:8] == logkeys[key_index + delta][0:8]):
                # TOFIX the above test fails if neighbouring games cross days
                if abs(next_rate - self.logs[logkeys[key_index + delta]]['rate']) < 0.02:
                    # try swapping keys and see if that helps
                    # print('swapping %d with the one following' % (key_index + 1))
                    self.logs.move_to_end(logkeys[key_index + delta])
                    self.logs.move_to_end(logkeys[key_index + 1])
                    for replace in chain(
                            range(key_index + 2, key_index + delta),
                            range(key_index + delta + 1, numself)):
                        self.logs.move_to_end(logkeys[replace])
                    return True
                delta = delta + 1
        return False


    def write_csv(self):
        """
                 write out rates csv for excel file
        """
        redo = True
        if self._flags.need_to_sort:
            print('running re-sort')
            self.logs = OrderedDict(sorted(self.logs.items()))

        print('compiling csv')
        while redo:
            redo = False
            output = ''
            last_hour = '-1'
            this_minute = 0
            logkeys = tuple(self.logs)
            for key_index, key in enumerate(logkeys):
                this_log = self.logs[key]
                if self._find_place_and_rate(this_log, key_index, logkeys):
                    redo = True
                    break
                this_hour = key[8:10]
                this_minute = this_minute + 5 if this_hour == last_hour else 10
                output = output + (
                    '%s-%s-%s %s:%d,"%s",%.2f,%.2f,%d\n' %
                    (key[0:4], key[4:6], key[6:8], this_hour, this_minute,
                     this_log['players'],
                     this_log['rate'], this_log['meanrate'], this_log['place'])
                )
                last_hour = this_hour

        with open(self.outdir +  self.username + '.csv', 'w', encoding='utf-8-sig') as csv:
            csv.write(output)


    def add_from_file(self, filepath):
        """
        receives a filepath, stores the mjlog in that file in the db
        extracts the unique game id (key) from the filename.
        If it fails to parse the file, it will try to download the game
        using the key
        """
        try:
            key = filepath.stem.split('&')[0]
            if key in self.logs and not self._flags.force:
                return
            print(key)
            with filepath.open(encoding='utf-8') as f:
                text = f.read()
                self.logs[key] = {'content': bytes(text, encoding='utf-8')}
                self._load_from_text(key, text)
        except:
            # failed to load file, try downloading instead
            self.one_record({'log': key}, '')


    @staticmethod
    def add_json(json_in):
        """
                process JSON and append to list of games to log
        """
        out = []
        jsonstring = json_in.replace('"{', '{').replace('}"', '}')
        while jsonstring[0] != '{':
            jsonstring = jsonstring[1 : -1]
        todo = json.loads(jsonstring)
        if 'log' in todo:
            out.append(todo)
        else:
            for i in range(0, 40):
                next_log = 'log%d' % i
                if next_log in todo:
                    out.append(todo[next_log])
        return out


    def _guarantee_defaults(self):
        """
                guarantee that certain properties are always available for each log
        """
        defaults = {'players': '', 'rate': 0, 'meanrate': 0, 'place': 0}
        for key in tuple(self.logs):
            for check_key, default_val in defaults.items():
                if check_key not in self.logs[key]:
                    self.logs[key][check_key] = default_val


    def load(self):
        """
                load logs from file
        """
        self._lockfile = portalocker.Lock(self._lockfile, timeout=10)
        try:
            with lzma.open(self.pickle_file, 'rb') as infile:
                self.logs = pickle.load(infile)
        except FileNotFoundError:
            pass


    def add_games(self, games_to_add):
        """
                add a set of games
        """
        existing_keys = tuple(self.logs)
        latest_key = next(reversed(self.logs))[0:10] if self.logs else ''
        if self._flags.force:
            self._flags.need_to_sort = True
        new_games = []
        for one_log in games_to_add:
            if 'log' in one_log and (
                    self._flags.force or one_log['log'] not in existing_keys
                ):
                new_games.append(one_log)

        for one_log in new_games:
            self.one_record(one_log, latest_key)

        self._guarantee_defaults()


    def save(self):
        """
                save sorted self
        """
        self.write_csv()
        if self._flags.have_new:
            with lzma.open(self.pickle_file, 'wb') as outfile:
                pickle.dump(self.logs, outfile, protocol=4)
        try:
            del self._lockfile
        except IOError:
            pass
