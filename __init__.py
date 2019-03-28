#!/usr/bin/env python3

import sys
import sqlite3
from pathlib import Path


conn = sqlite3.connect(str(Path(__file__).parent/"ids-data.db"))
cursor = conn.cursor()

def find(components):
    ideostr = f"{tuple(components)}" if len(components) > 1 else f"('{components}')"
    cursor.execute(f"SELECT ids FROM ids_data WHERE ideo in {ideostr}")
    r = cursor.fetchone()
    try:
        output = set(r[0]) | {components[0]}
    except TypeError:
        output = {components[0]}
    for r, ideo in zip(cursor.fetchall(), components[1:]):
        try:
            output &= set(r[0]) | {ideo}
        except TypeError:
            output &= {ideo}
    return output

if __name__ == "__main__":
    components = sys.argv[1]
    output = find(components)
    sys.stdout.write("".join(sorted(output)))
    conn.close()
    sys.exit(0)
