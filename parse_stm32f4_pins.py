#!/usr/bin/python3

import sys
import csv
import json
import copy

# This script takes TI pinconfig, got from the Reference Manual
# and converts it to theCore menu description

src=sys.argv[1]

'''
        "items-PA0": {
            "config-afsel": {
                "type": "enum",
                "description": "Alternate function",
                "depends_on": "config-direction == 'af'",
                "long_description": [],
                "values": [
                    "AF1: TIM2_CH1_ETR",
                    "AF2: TIM5_CH1",
                    "AF3: TIM8_ETR",
                    "AF7: USART2_CTS",
                    "AF8: UART4_TX",
                    "AF11: ETH_MII_CRS",
                ]
            }
'''

item={
    'config-afsel': {
        'type': 'enum',
        'description': 'Alternate function',
        'depends_on': 'config-direction == \'af\'',
        'long_description': [],
        'values': []
    }
}

items={}

with open(src, 'r') as f:
    c = csv.DictReader(f)
    for row in c:
        # Entire CSV is a concatenation of couple of tables.
        # Header names can be observed multiple times inside a CSV file.
        if row['Port'] == 'Port' or row['Port'] == '':
            continue

        afs = []

        for k, v in row.items():
            if k and k.startswith('AF') and v != '-':
                af_str = ''

                sym_hyphen_detected = False
                prev_ch = None

                for ch in v:
                    if ch == '\n':
                        if prev_ch == '_':
                            # Example case: UART1_\nTX
                            # Skip '\n', thus merging two strings, they're likely
                            # is a part of whole word
                            sym_hyphen_detected = True

                        prev_ch = '\n'
                        # Skip '\n' in any case
                        continue

                    # If sym_hyphen_detected is True, it means that \n is skipped
                    # and that's enough. No need to handle other cases.
                    if not sym_hyphen_detected:
                        if ch != '_' and prev_ch == '\n':
                            # Example case: UART1\nUSART2
                            # Change '\n' to '/', thus making two words, they're likely
                            # must be separated
                            af_str += '/' # Change \n to ' '
                    else:
                        sym_hyphen_detected = False

                    prev_ch = ch
                    af_str += ch

                # Strip final whitespaces (if any)
                afs.append('{}: {}'.format(k, ''.join(af_str.split())))

        new_item = copy.deepcopy(item)
        new_item['config-afsel']['values'] = afs

        items['items-' + row['Port']] = new_item

    print(json.dumps(items, indent=4))

'''
    items={}
    for line in f:
        afs = [ None ]
        data = line.split(' ')
        pin_id = data[0]
        for af in data[2:]:
            if not '-' in af:
                afs.append(af)
        new_item = copy.deepcopy(item)
        new_item['config-afsel']['values'] = afs.copy()
        items['items-' + pin_id] = new_item

    print(json.dumps(items, indent=4))
'''
