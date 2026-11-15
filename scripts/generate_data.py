#!/usr/bin/env python3
"""Regenerate ``ideograph/ids-data.db`` from upstream sources.

Sources (downloaded into a cache directory on first use):

* BabelStone IDS (Andrew West) — https://babelstone.co.uk/CJK/IDS.TXT
  Primary source.  The maintainer waives all rights to the data.
* CHISE IDS — https://gitlab.chise.org/CHISE/ids (GPL-2.0-or-later)
  Used only for unified ideographs that BabelStone does not (yet) cover,
  pinned to a specific commit for reproducibility.
* Unicode Character Database (Unihan, EquivalentUnifiedIdeograph.txt) —
  the set of unified ideographs and their total stroke counts.

Usage::

    python scripts/generate_data.py            # use cached sources
    python scripts/generate_data.py --refresh  # re-download everything
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ideograph import ids_syntax as idslib  # noqa: E402

UNICODE_VERSION = "18.0.0"
BABELSTONE_URL = "https://babelstone.co.uk/CJK/IDS.TXT"
CHISE_PROJECT = "CHISE/ids"
CHISE_API = "https://gitlab.chise.org/api/v4/projects/" + urllib.parse.quote(CHISE_PROJECT, safe="")
CHISE_RAW = "https://gitlab.chise.org/" + CHISE_PROJECT + "/-/raw/{ref}/{name}"
#: CHISE IDS commit used by default (2026-11-02).  Update deliberately.
CHISE_REF = "c3057f890b4d7a990628873f19274ec33b58a7aa"

USER_AGENT = "ideograph-data-generator (+https://github.com/iwsfutcmd/ideograph)"


# --------------------------------------------------------------------------
# Downloading


def fetch(url: str, dest: Path, refresh: bool) -> Path:
    if dest.exists() and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def fetch_chise(cache: Path, ref: str, refresh: bool) -> list[Path]:
    """Download every ``IDS-UCS-*.txt`` file of CHISE IDS at *ref*."""
    listing = cache / f"chise-{ref}" / "tree.json"
    fetch(f"{CHISE_API}/repository/tree?ref={ref}&per_page=100", listing, refresh)
    names = sorted(
        entry["name"]
        for entry in json.loads(listing.read_text("utf-8"))
        if re.fullmatch(r"IDS-UCS-.+\.txt", entry["name"])
    )
    return [
        fetch(CHISE_RAW.format(ref=ref, name=name), cache / f"chise-{ref}" / name, refresh)
        for name in names
    ]


# --------------------------------------------------------------------------
# Unicode Character Database


def load_unihan(path: Path) -> tuple[set[str], dict[str, int]]:
    """Return (unified ideographs, kTotalStrokes) from ``Unihan.zip``."""
    unified: set[str] = set()
    compat: set[str] = set()
    strokes: dict[str, int] = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            with zf.open(name) as fh:
                for line in io.TextIOWrapper(fh, encoding="utf-8"):
                    if not line.startswith("U+"):
                        continue
                    cp, field, value = line.rstrip("\n").split("\t", 2)
                    char = chr(int(cp[2:], 16))
                    if field == "kRSUnicode":
                        unified.add(char)
                    elif field == "kCompatibilityVariant":
                        compat.add(char)
                    elif field == "kTotalStrokes":
                        # When two values are given, the first is the one
                        # preferred for zh-Hans; use it consistently.
                        strokes[char] = int(value.split()[0])
    return unified - compat, strokes


def load_equivalent_unified(path: Path) -> dict[str, str]:
    """Map CJK radicals and strokes to their equivalent unified ideograph."""
    mapping = {}
    for line in path.read_text("utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        src, dst = (part.strip() for part in line.split(";"))
        lo, _, hi = src.partition("..")
        for cp in range(int(lo, 16), int(hi or lo, 16) + 1):
            mapping[chr(cp)] = chr(int(dst, 16))
    return mapping


def component_strokes(char: str, strokes: dict[str, int], equiv: dict[str, str]) -> int | None:
    """Stroke count for characters that are not in Unihan (radicals, strokes)."""
    if char in strokes:
        return strokes[char]
    cp = ord(char)
    if 0x31C0 <= cp <= 0x31EF:  # CJK Strokes
        return 1
    folded = unicodedata.normalize("NFKC", char)  # Kangxi Radicals
    if folded != char and folded in strokes:
        return strokes[folded]
    if char in equiv and equiv[char] in strokes:
        return strokes[equiv[char]]
    return None


# --------------------------------------------------------------------------
# BabelStone IDS

BS_FIELD = re.compile(r"\^(?P<ids>.+?)\$\((?P<src>[^)]*)\)")
BS_UNENCODED = re.compile(r"\{(\d+)\}")


def load_babelstone(path: Path) -> tuple[dict[str, list[tuple[str, str]]], dict[str, str]]:
    """Return ({char: [(ids, sources), …]}, metadata)."""
    text = path.read_text("utf-8-sig")
    meta: dict[str, str] = {}
    replacements: dict[str, str] = {}
    entries: dict[str, list[tuple[str, str]]] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith("#"):
            if m := re.match(r"#\s*(Unicode Version|File Date|Total entries):\s*(.+)", line):
                meta[m[1]] = m[2].strip()
            # Table of unencoded components:  #<TAB>{n}<TAB>description<TAB>replacement
            parts = line.split("\t")
            if len(parts) >= 3 and BS_UNENCODED.fullmatch(parts[1]):
                replacements[parts[1]] = parts[3].strip() if len(parts) > 3 else ""
            continue
        if not line.startswith("U+"):
            continue
        fields = line.split("\t")
        char = chr(int(fields[0][2:], 16))
        seqs = []
        for field in fields[2:]:
            if field.startswith("*"):  # editorial note
                continue
            m = BS_FIELD.fullmatch(field)
            if not m:
                print(f"  warning: unparsed BabelStone field {field!r} for {char}", file=sys.stderr)
                continue
            seqs.append((m["ids"], m["src"]))
        entries[char] = seqs

    def expand(ids: str, depth: int = 0) -> str:
        def sub(m: re.Match[str]) -> str:
            rep = replacements.get(m[0], "")
            if not rep or depth > 8:
                return idslib.UNKNOWN
            return expand(rep, depth + 1)

        return BS_UNENCODED.sub(sub, ids)

    # Replace numbered unencoded components with BabelStone's suggested
    # (approximate) IDS fragments, or ？ where there is none.
    entries = {c: [(expand(i), s) for i, s in seqs] for c, seqs in entries.items()}
    return entries, meta


# --------------------------------------------------------------------------
# CHISE IDS

CHISE_ENTITY = re.compile(r"&([^;&\s]+);")
CHISE_IDC_VARIANT = re.compile(r"U-i\d+\+(2F[F][0-9A-F]|31EF)", re.I)


def chise_clean(ids: str) -> str:
    """Replace CHISE entity references with encoded characters or ？."""

    def sub(m: re.Match[str]) -> str:
        if v := CHISE_IDC_VARIANT.fullmatch(m[1]):
            return chr(int(v[1], 16))  # glyph variant of an IDS operator
        return idslib.UNKNOWN  # unencoded component (CDP, GT, AJ1, …)

    return CHISE_ENTITY.sub(sub, ids)


def load_chise(paths: list[Path]) -> dict[str, list[tuple[str, str]]]:
    entries: dict[str, list[tuple[str, str]]] = {}
    for path in paths:
        for line in path.read_text("utf-8").splitlines():
            if not line[:2] in ("U+", "U-"):
                continue
            fields = line.split("\t")
            char = chr(int(fields[0][2:], 16))
            seqs = []
            for field in fields[2:]:
                field = field.removeprefix("@apparent=")
                if not field or field.startswith("@"):
                    continue
                seqs.append((chise_clean(field), ""))
            known = entries.setdefault(char, [])
            known.extend(s for s in dict.fromkeys(seqs) if s not in known)
    return entries


# --------------------------------------------------------------------------
# Building


def build(args: argparse.Namespace) -> None:
    cache: Path = args.cache
    print("Fetching sources…", file=sys.stderr)
    ucd = f"https://www.unicode.org/Public/{args.unicode_version}/ucd/"
    unihan_zip = fetch(ucd + "Unihan.zip", cache / f"ucd-{args.unicode_version}" / "Unihan.zip", args.refresh)
    equiv_txt = fetch(
        ucd + "EquivalentUnifiedIdeograph.txt",
        cache / f"ucd-{args.unicode_version}" / "EquivalentUnifiedIdeograph.txt",
        args.refresh,
    )
    bs_path = fetch(BABELSTONE_URL, cache / "babelstone" / "IDS.TXT", args.refresh)
    chise_paths = [] if args.no_chise else fetch_chise(cache, args.chise_ref, args.refresh)

    print("Parsing…", file=sys.stderr)
    unified, strokes = load_unihan(unihan_zip)
    equiv = load_equivalent_unified(equiv_txt)
    babelstone, bs_meta = load_babelstone(bs_path)
    chise = load_chise(chise_paths)

    # Every unified ideograph gets an entry; BabelStone first, CHISE for gaps.
    entries: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for char in sorted(unified | babelstone.keys(), key=ord):
        if babelstone.get(char):
            entries[char] = ("babelstone", babelstone[char])
        elif chise.get(char):
            entries[char] = ("chise", chise[char])
        else:
            entries[char] = ("", [])

    direct: dict[str, set[str]] = {}
    for char, (_, seqs) in entries.items():
        comps: set[str] = set()
        for ids, _src in seqs:
            comps |= idslib.components(ids)
        comps.discard(char)
        direct[char] = comps

    sys.setrecursionlimit(max(10_000, sys.getrecursionlimit()))
    closure: dict[str, set[str]] = {}
    cycles = 0

    def close(char: str, stack: set[str]) -> set[str]:
        nonlocal cycles
        if char in closure:
            return closure[char]
        stack.add(char)
        out: set[str] = set()
        for comp in direct.get(char, ()):
            out.add(comp)
            if comp in stack:
                cycles += 1
                continue
            out |= close(comp, stack)
        stack.discard(char)
        out.discard(char)
        closure[char] = out
        return out

    for char in entries:
        close(char, set())

    index: dict[str, set[str]] = defaultdict(set)
    for char in entries:
        index[char].add(char)
        for comp in closure[char]:
            index[comp].add(char)

    # Radical and stroke forms that the data never uses (e.g. ⺮, which
    # BabelStone writes as 𥫗) are aliased to their equivalent unified
    # ideograph, so that input such as ⺮ still finds something.
    aliases = {src: dst for src, dst in equiv.items() if src not in index and dst in index}

    all_chars = set(entries) | set(index)
    char_strokes = {c: component_strokes(c, strokes, equiv) for c in all_chars}

    out: Path = args.output
    print(f"Writing {out}…", file=sys.stderr)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE chars (
            char TEXT PRIMARY KEY,
            strokes INTEGER,
            is_entry INTEGER NOT NULL,   -- 1 if a unified ideograph with its own record
            source TEXT,                 -- 'babelstone', 'chise' or NULL
            ids TEXT,                    -- JSON list of [ids, sources] pairs
            components TEXT              -- every component, recursively
        ) WITHOUT ROWID;
        CREATE TABLE idx (component TEXT PRIMARY KEY, chars TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE alias (char TEXT PRIMARY KEY, target TEXT NOT NULL) WITHOUT ROWID;
        """
    )
    for char in sorted(all_chars, key=ord):
        source, seqs = entries.get(char, ("", []))
        c.execute(
            "INSERT INTO chars VALUES (?, ?, ?, ?, ?, ?)",
            (
                char,
                char_strokes[char],
                int(char in entries),
                source or None,
                json.dumps(seqs, ensure_ascii=False, separators=(",", ":")) if seqs else None,
                "".join(sorted(closure.get(char, ()), key=ord)),
            ),
        )
    for comp in sorted(index, key=ord):
        c.execute("INSERT INTO idx VALUES (?, ?)", (comp, "".join(sorted(index[comp], key=ord))))
    c.executemany("INSERT INTO alias VALUES (?, ?)", sorted(aliases.items()))

    counts = defaultdict(int)
    for source, _ in entries.values():
        counts[source or "none"] += 1
    meta = {
        "unicode_version": args.unicode_version,
        "babelstone_url": BABELSTONE_URL,
        "babelstone_unicode_version": bs_meta.get("Unicode Version", ""),
        "babelstone_file_date": bs_meta.get("File Date", ""),
        "babelstone_sha256": hashlib.sha256(bs_path.read_bytes()).hexdigest(),
        "chise_url": f"https://gitlab.chise.org/{CHISE_PROJECT}",
        "chise_commit": "" if args.no_chise else args.chise_ref,
        "count_entries": str(len(entries)),
        "count_babelstone": str(counts["babelstone"]),
        "count_chise": str(counts["chise"]),
        "count_no_data": str(counts["none"]),
        "generated": datetime.now(timezone.utc).date().isoformat(),
    }
    c.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    tmp.replace(out)

    print(json.dumps(meta, indent=2, ensure_ascii=False), file=sys.stderr)
    if cycles:
        print(f"  note: {cycles} decomposition cycle edge(s) skipped", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "sources", help="download cache directory")
    parser.add_argument("--refresh", action="store_true", help="re-download sources even if cached")
    parser.add_argument("--unicode-version", default=UNICODE_VERSION, help="UCD version (default: %(default)s)")
    parser.add_argument("--chise-ref", default=CHISE_REF, help="CHISE IDS git commit/branch (default: %(default)s)")
    parser.add_argument("--no-chise", action="store_true", help="BabelStone only (no GPL-licensed data)")
    parser.add_argument("--output", type=Path, default=ROOT / "ideograph" / "ids-data.db")
    build(parser.parse_args(argv))


if __name__ == "__main__":
    main()
