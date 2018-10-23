"""
sum yakus won and lost by one player, from available logs
"""

# core libraries
import argparse
import lzma
import pickle
import sys

# third-party libraries
import yaml

# own imports
from TenhouConfig import account_names, directory_name
import TenhouDecoder
import TenhouYaku

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument(
    '-w', '--winner',
    help='only count yakus for when the user won the hand',
    action='store_true')
group.add_argument(
    '-l', '--loser',
    help='only count yakus for when the user lost the hand',
    action='store_true')
group.add_argument(
    '-a', '--all',
    help='count yakus from all hands (default)',
    action='store_true')

args = parser.parse_args()
counter = TenhouYaku.YakuCounter(winner = args.winner or (False if args.loser is True else None))
gamecount = 0

for player in account_names:
    counter.player = player
    with lzma.open(directory_name + player + '.pickle.7z', 'rb') as infile:
        logs = pickle.load(infile)

    for log in logs:
        gamecount += 1
        game = TenhouDecoder.Game('DEFAULT')
        game.decode(logs[log]['content'].decode())
        counter.addGame(game)

print('%d games' % gamecount)
yaml.dump(counter.asdata(), sys.stdout, default_flow_style=False, allow_unicode=True)
