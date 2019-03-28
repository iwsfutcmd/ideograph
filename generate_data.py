#!/usr/bin/env python3

import json
import pickle
import sqlite3
import re
from collections import defaultdict
import os

data = {}

CONV = [
    (range(0xfa40, 0xfefe + 1), (0xe000, 0xfa)),
    (range(0x8e40, 0xa0fe + 1), (0xe311, 0x8e)),
    (range(0x8140, 0xdefe + 1), (0xeeb8, 0x81)),
    (range(0xc6a1, 0xc8fe + 1), (0xf672, 0xc6))
]

def big5_to_PUA(code):
    for r, (x, y) in CONV:
        if code in r:
            h = code // 0x100
            l = code % 0x100
            return (x + (157 * (h - y)) + ((l - 0x40) if (l < 0x80) else (l - 0x62)))
    raise ValueError

def prep_ids(ids):
    i = re.sub(r"(\[.+\]|[\u2ff0-\u2ffb])", "", ids)
    if "CDP-" in i:
        for m in re.finditer(r"&CDP-(....);", i):
            i = re.sub(m.group(0), chr(big5_to_PUA(int(m.group(1), 16))), i)
    return i

for line in open("cjkvi-ids/ids-cdp.txt"):
    if line.startswith("#") or line.startswith(";"):
        continue
    _, ideo, *ids = line.strip().split("\t")
    ideo = prep_ids(ideo)
    ids = [prep_ids(i) for i in ids]
    data[ideo] = set()
    for i in ids:
        for c in i:
            data[ideo].add(c)

def recursive_breakup(charset):
    output = charset.copy()
    for char in charset:
        output.update(data[char])
    if len(output) == len(charset):
        return output
    else:
        return recursive_breakup(output)

data = {ideo: list(recursive_breakup(data[ideo]) - {ideo}) for ideo in data}
reverse_data = defaultdict(list)
for ideo in data:
    for comp in data[ideo]:
        reverse_data[comp].append(ideo)

json.dump(reverse_data, open("ids-data.json", "w"), ensure_ascii=False)
pickle.dump(reverse_data, open("ids-data.pickle", "wb"))

try:
    os.remove("ids-data.db")
except FileNotFoundError:
    pass
conn = sqlite3.connect("ids-data.db")
c = conn.cursor()
c.execute("CREATE TABLE ids_data (ideo text, ids text)")
for ideo, ids in reverse_data.items():
    c.execute("INSERT INTO ids_data VALUES (?, ?)", (ideo, "".join(ids)))
conn.commit()
conn.close()
