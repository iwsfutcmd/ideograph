"""Find ideographs (e.g. Han characters) by their components.

>>> import ideograph
>>> "楊" in ideograph.find("木日勿")
True
>>> {"木", "昜", "日", "勿"} <= ideograph.components("楊")
True
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import NamedTuple

from . import ids_syntax

__all__ = [
    "IDS",
    "aliases",
    "component_counts",
    "cycle_breaks",
    "components",
    "data_info",
    "find",
    "ideographs",
    "ids",
    "normalize",
    "total_strokes",
]

__version__ = "2.0.0"

#: Location of the bundled SQLite database (see ``scripts/generate_data.py``).
DB_PATH = Path(__file__).with_name("ids-data.db")

_conn: sqlite3.Connection | None = None
_aliases: dict[str, str] | None = None
_lock = threading.Lock()


def _db() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True, check_same_thread=False)
        return _conn


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    conn = _db()
    with _lock:
        return conn.execute(sql, params).fetchall()


def _alias_map() -> dict[str, str]:
    global _aliases
    if _aliases is None:
        _aliases = dict(_query("SELECT char, target FROM alias"))
    return _aliases


class IDS(NamedTuple):
    """One Ideographic Description Sequence for a character."""

    #: The sequence itself, e.g. ``"⿰木昜"``.  ``？`` marks a component that
    #: has no Unicode representation.
    sequence: str
    #: BabelStone source references for the glyph form described, e.g.
    #: ``"GHTJKPV"`` (G = China, H = Hong Kong, T = Taiwan, J = Japan,
    #: K = South Korea, P = North Korea, V = Vietnam, …).  Empty when the
    #: data source does not say.
    sources: str


def normalize(text: str) -> str:
    """Normalize user input for lookup.

    * CJK compatibility ideographs become their canonical equivalents (NFC).
    * Kangxi Radicals (U+2F00–U+2FDF) become the unified ideographs they are
      compatibility equivalents of (⽊ → 木).
    * CJK Radicals Supplement and CJK Strokes characters that the data never
      uses become their equivalent unified ideograph, per the UCD's
      ``EquivalentUnifiedIdeograph.txt`` (⺮ → 𥫗, ㇐ → 一).  Radical forms
      that *are* used in the data (⺈, ⻖ …) are kept as they are.
    """
    aliases = _alias_map()
    out = []
    for c in unicodedata.normalize("NFC", text):
        if 0x2F00 <= ord(c) <= 0x2FDF:
            c = unicodedata.normalize("NFKC", c)
        out.append(aliases.get(c, c))
    return "".join(out)


def _single(ideo: str) -> str:
    char = normalize(ideo)
    if len(char) != 1:
        raise ValueError("ideo must consist of one character")
    return char


def find(components: str | Iterable[str]) -> set[str]:
    """Return every ideograph that contains *all* of the given components.

    *components* is a string (or iterable of strings) of components.  A
    component given more than once must occur at least that many times, at
    any depth: ``find("木木")`` finds 林 and 森 but not 杜, and
    ``find("口口口")`` finds 品 and 器.  Whitespace, IDS operators and
    characters that are not components of anything in the data are ignored.
    A character always matches itself, so ``find("木")`` includes 木.
    Matching is visual, not etymological: 人 and 亻 are distinct components.
    """
    query = Counter(
        c
        for c in normalize("".join(components))
        if not c.isspace() and not ids_syntax.is_operator(c) and c != ids_syntax.UNKNOWN
    )
    result: set[str] | None = None
    known: dict[str, int] = {}
    for component in sorted(query):
        rows = _query("SELECT chars FROM idx WHERE component = ?", (component,))
        if not rows:
            continue
        known[component] = query[component]
        matches = set(rows[0][0])
        result = matches if result is None else result & matches
        if not result:
            break
    if not result:
        return set()
    for component, n in known.items():
        if n > 1:
            result &= _occurring_at_least(component, n)
    return result


_COUNT = re.compile(r"(\D)(\d+)")


def _counts(char: str) -> dict[str, int]:
    """Components occurring more than once in *char* (at any depth)."""
    rows = _query("SELECT counts FROM chars WHERE char = ?", (char,))
    if not rows or not rows[0][0]:
        return {}
    return {c: int(n) for c, n in _COUNT.findall(rows[0][0])}


def _occurring_at_least(component: str, n: int) -> set[str]:
    """Characters in which *component* occurs at least *n* (≥ 2) times."""
    found = set()
    pattern = re.compile(re.escape(component) + r"(\d+)")
    rows = _query(
        "SELECT char, counts FROM chars WHERE counts IS NOT NULL AND instr(counts, ?) > 0",
        (component,),
    )
    for char, counts in rows:
        m = pattern.search(counts)
        # A character also counts as containing itself once.
        if m and int(m[1]) + (char == component) >= n:
            found.add(char)
    return found


def component_counts(ideo: str) -> dict[str, int]:
    """Return every component of an ideograph with how often it occurs.

    Occurrences at all depths are counted: 森 (⿱木林, with 林 = ⿰木木)
    contains 林 once and 木 three times.  When a character has several
    IDS (regional glyph forms), the largest count for each component is used.

    >>> c = component_counts("森")
    >>> c["木"], c["林"]
    (3, 1)
    """
    char = _single(ideo)
    counts = _counts(char)
    return {c: counts.get(c, 1) for c in sorted(components(char), key=ord)}


def components(ideo: str, *, recursive: bool = True) -> set[str]:
    """Return the components of a single ideograph.

    By default the set contains the components, the components of those
    components and so on, down to the most basic ones in the data.  With
    ``recursive=False`` only the components named directly in the
    character's IDS are returned.
    """
    char = _single(ideo)
    if not recursive:
        out: set[str] = set()
        for seq in ids(char):
            out |= ids_syntax.components(seq.sequence)
        out.discard(char)
        return out
    rows = _query("SELECT components FROM chars WHERE char = ?", (char,))
    return set(rows[0][0]) if rows else set()


def ids(ideo: str) -> list[IDS]:
    """Return the Ideographic Description Sequences recorded for *ideo*.

    Characters with regional glyph differences may have several.
    """
    char = _single(ideo)
    rows = _query("SELECT ids FROM chars WHERE char = ?", (char,))
    if not rows or not rows[0][0]:
        return []
    return [IDS(seq, src) for seq, src in json.loads(rows[0][0])]


def total_strokes(char: str) -> int | None:
    """Return the total stroke count of *char*, or ``None`` if unknown.

    Unified ideographs use the (first) Unihan ``kTotalStrokes`` value; CJK
    strokes count as one stroke, and radical forms take the count of their
    equivalent unified ideograph.
    """
    rows = _query("SELECT strokes FROM chars WHERE char = ?", (_single(char),))
    return rows[0][0] if rows else None


def ideographs() -> Iterator[str]:
    """Iterate over every ideograph in the data, in code point order."""
    for (char,) in _query("SELECT char FROM chars WHERE is_entry = 1 ORDER BY char"):
        yield char


def aliases() -> dict[str, str]:
    """Return the radical/stroke aliases applied by :func:`normalize`.

    Maps CJK Radicals Supplement and CJK Strokes characters that the data
    does not use to their equivalent unified ideograph (e.g. ⺮ → 𥫗).
    """
    return dict(_alias_map())


def cycle_breaks() -> dict[str, set[str]]:
    """Return the decomposition links ignored to break cycles.

    A few IDS describe a character by subtraction from a character that in
    turn contains it (𫝀 = ㇯五一 "五 minus 一", while 五 = ⿱一𫝀).  Those links
    are left out of the component graph, so that 𫝀 does not count as
    containing 五.  Maps each character to the components ignored for it.
    """
    out: dict[str, set[str]] = {}
    for char, component in _query("SELECT char, component FROM cycle_break"):
        out.setdefault(char, set()).add(component)
    return out


def data_info() -> dict[str, str]:
    """Return provenance information about the bundled data."""
    return dict(_query("SELECT key, value FROM meta"))
