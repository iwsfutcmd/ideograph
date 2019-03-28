#!/usr/bin/env python3

import sys
import sqlite3

def sqlite_get(cursor, ideos):
    ideostr = f"{tuple(ideos)}" if len(ideos) > 1 else f"('{ideos}')"
    cursor.execute(f"SELECT ids FROM ids_data WHERE ideo in {ideostr}")
    try:
        r = cursor.fetchone()[0]
    except TypeError:
        return set()
    s = set(r)
    output = s | {ideos[0]}
    for r, ideo in zip(cursor.fetchall(), ideos[1:]):
        s = set(r[0])
        output &= s | {ideo}
    return output

if __name__ == "__main__":
    conn = sqlite3.connect("ids-data.db")
    cursor = conn.cursor()
    ideos = sys.argv[1]
    output = sqlite_get(cursor, ideos)
    sys.stdout.write("".join(sorted(output)))
    sys.exit(0)
