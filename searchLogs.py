"""
find logs that match given criteria
"""

# core libraries
import argparse
import lzma
import pickle

# own imports
from TenhouConfig import account_names, directory_name
import TenhouDecoder

parser = argparse.ArgumentParser()
parser.add_argument(
    '--since',
    help='date in yyyymmdd format: only include games since this date, exclusive',
    action='store')
parser.add_argument(
    '--before',
    help='date in yyyymmdd format: only include games before this date, inclusive',
    action='store')
parser.add_argument(
    '--player',
    help='player ID(s) to search for, space-separated if more than one',
    action='store')
parser.add_argument(
    '--lobby',
    help='the lobby to search for',
    action='store')
parser.add_argument(
    '--yaku',
    help='the yaku to search for',
    action='store')
parser.add_argument(
    '--freetext',
    help='search for text in any part of the log',
    action='store')
group = parser.add_mutually_exclusive_group()
group.add_argument(
    '--sanma',
    help='show only sanma (three-player) games',
    action='store_true')
group.add_argument(
    '--no-sanma',
    help='show no sanma (three-player) games',
    action='store_true')

args = parser.parse_args()
gamecount = 0
matchedLogs = []

targetYaku = ''
targetText = ''

def searchForFreeText(log):
    return targetText in log['content'].decode().lower()
    
def searchForYaku(log):
    game = TenhouDecoder.Game(lang='DEFAULT', suppress_draws=True)
    game.decode(log['content'].decode())    
    for round in game.rounds:
        for agari in round.agari:
            if hasattr(agari, 'yaku'):
                for yaku, han in agari.yaku:
                    if yaku.lower() == targetYaku:
                        return True
            if hasattr(agari, 'yakuman'):
                for yakuman in agari.yakuman:
                    if yakuman.lower() == targetYaku:
                        return True
    return False

if args.yaku:
    targetYaku = args.yaku.lower()
if args.freetext:
    targetText = args.freetext.lower()

for player in account_names:
    with lzma.open(directory_name + player + '.pickle.7z', 'rb') as infile:
        logs = pickle.load(infile)

    for key, log in logs.items():
        if args.since and args.since > key[0:8]:
            continue
        if args.before and args.before <= key[0:8]:
            continue
        if args.sanma and not '' in log['uname']:
            continue
        if args.no_sanma and '' in log['uname']:
            continue
        if args.lobby and args.lobby != str(log['lobby']):
            continue
        if args.player:
            players = args.player.split(' ')
            hasPlayer = False
            for player in players:
                if player in log['uname']:
                    hasPlayer = True
                    break
            if not hasPlayer:
                continue
        if args.freetext and not searchForFreeText(log):
            continue            
        if args.yaku and not searchForYaku(log):
            continue
        
        gamecount += 1
        matchedLogs.append(log)

print('Found %d games' % gamecount)

if gamecount > 0:
    print('Log                             | Results')
    print('--------------------------------|--------------------------------')
    for log in matchedLogs:
        print('%s | %s' % (log['log'], log['players']))