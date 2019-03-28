#!/usr/bin/env python3

import sys
import sqlite3
from pathlib import Path


conn = sqlite3.connect(str(Path(__file__).parent/"ids-data.db"))
cursor = conn.cursor()

def find(components):
    ideostr = f"{tuple(components)}" if len(components) > 1 else f"('{components}')"
    cursor.execute(f"SELECT ids FROM ids_data WHERE ideo in {ideostr}")
    try:
        r = cursor.fetchone()
    except TypeError:
        return set()
    s = set(r[0])
    output = (s | {components[0]})
    for r, ideo in zip(cursor.fetchall(), components[1:]):
        s = set(r[0])
        output &= (s | {ideo})
    return output

if __name__ == "__main__":
    components = sys.argv[1]
    output = find(components)
    sys.stdout.write("".join(sorted(output)))
    conn.close()
    sys.exit(0)
