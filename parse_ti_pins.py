#!/usr/bin/python3

import sys
import csv
import json
import copy

# This script takes TI pinconfig, got from the Reference Manual
# and converts it to theCore menu description

src=sys.argv[1]

item={
    'config-afsel': {
        'type': 'enum',
        'description': 'Alternate function',
        'depends_on': 'config-direction == \'af\'',
        'long_description': [],
        'values': []
    }
}

with open(src, 'r') as f:
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