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
from Data import Data
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

parser.add_argument(
    '--since',
    help='date in yyyymmdd format: only include games since this date',
    action='store')

parser.add_argument(
    '--before',
    help='date in yyyymmdd format: only include games before this date',
    action='store')

args = parser.parse_args()
counter = TenhouYaku.YakuCounter(winner = args.winner or (False if args.loser is True else None))
gamecount = 0

outcomes = [
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
]

outcome_names = ('I won', 'Draw', 'Bystander', 'Other tsumod', 'I dealt in', 'Averages')
for player in account_names:
    counter.player = player
    with lzma.open(directory_name + player + '.pickle.7z', 'rb') as infile:
        logs = pickle.load(infile)

    for key, log in logs.items():
        if args.since and args.since > key[0:8]:
            continue
        if args.before and args.before <= key[0:8]:
            continue
        gamecount += 1
        game = TenhouDecoder.Game(lang='DEFAULT', suppress_draws=True)
        game.decode(log['content'].decode())
        counter.reach_outcomes = []
        counter.addGame(game)

        for outcome in counter.reach_outcomes:
            # aggregate counter.reach_outcomes
            if outcome['type'] == 'DRAW':
                row = 1                                  # draw
            elif outcome['points'] > 0:
                row = 0                                  # i won
            elif outcome['points'] == -10:
                row = 2                                  # bystander
            elif outcome['type'] == 'TSUMO':
                row = 3                                  # lost to other's tsumo
            else:
                row = 4                                  # dealt in

            outcomes[row][outcome['pursuit']][0] += outcome['points']
            outcomes[row][outcome['pursuit']][1] += 1

del counter.reach_outcomes

print('%d games' % gamecount)
yaml.dump(counter.asdata(), sys.stdout, default_flow_style=False, allow_unicode=True)

print('\n==================================\n')

# make column totals and percentages
for pursuit in range(3):
    for row in range(5):
        for col in range(2):
            outcomes[5][pursuit][col] += outcomes[row][pursuit][col]

# print table
print('%d games,first to riichi,,,second to riichi,,,third to riichi,,' % gamecount)
print('My outcome,My point change,hands,% of hands,My point change,hands,% of hands,My point change,hands,% of hands')
for row in range(6):
    print(outcome_names[row], end='')
    for pursuit in range(3):
        if outcomes[row][pursuit][1]:
            print(
                ',%d,%d,%d%%' % (
                    int(100 * outcomes[row][pursuit][0] / outcomes[row][pursuit][1]),
                    outcomes[row][pursuit][1],
                    int(100 * outcomes[row][pursuit][1] / outcomes[5][pursuit][1])
                ), end=''
            )
        else:
            print(',0,0,0', end='')
    print('')

riichid_hands = outcomes[5][0][1] + outcomes[5][1][1] + outcomes[5][2][1]
total_hands = counter.hands['closed'] + counter.hands['opened']
print('total hands: %d' % total_hands)
print('Riichi rate: %.1f%%' % (100 * riichid_hands / total_hands))
