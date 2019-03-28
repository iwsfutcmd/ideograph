#!/usr/bin/env python3

import sys
import sqlite3

def sqlite_get(cursor, ideos):
    cursor.execute("SELECT ids FROM ids_data WHERE ideo=?", (ideos[0],))
    r = cursor.fetchone()[0]
    s = set(r)
    output = s | {ideos[0]}
    for ideo in ideos[1:]:
        cursor.execute("SELECT ids FROM ids_data WHERE ideo=?", (ideo,))
        r = cursor.fetchone()[0]
        s = set(r)
        output &= s | {ideo}
    return output

if __name__ == "__main__":
    import sqlite3
    conn = sqlite3.connect("ids-data.db")
    cursor = conn.cursor()
    ideos = sys.argv[2]
    output = sqlite_get(cursor, ideos)
    sys.stdout.write("".join(sorted(output)))
    sys.exit(0)
