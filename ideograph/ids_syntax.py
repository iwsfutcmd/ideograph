"""Parsing of Ideographic Description Sequences (IDS).

The grammar follows *The Unicode Standard*, §18.2 (Ideographic Description
Characters), as of Unicode 15.1 and later, which added the ⿼⿽ surround
operators, the ⿾ (mirror) and ⿿ (rotation) unary operators, and the ㇯
subtraction operator.  The ideographic variation indicator 〾 (U+303E) is
treated as a unary prefix operator, and U+FF1F FULLWIDTH QUESTION MARK (？)
as a placeholder for a component that cannot be represented.
"""

from __future__ import annotations

__all__ = [
    "OPERATORS",
    "SUBTRACTION",
    "UNKNOWN",
    "VARIATION_INDICATOR",
    "IDSSyntaxError",
    "components",
    "is_operator",
    "strip_variation_selectors",
]

#: U+31EF CJK STROKE HXG, used as the IDS subtraction operator: ``㇯AB`` is
#: *A* with *B* removed, so *B* is not a component of the result.
SUBTRACTION = "㇯"

#: U+303E IDEOGRAPHIC VARIATION INDICATOR.
VARIATION_INDICATOR = "〾"

#: U+FF1F FULLWIDTH QUESTION MARK, used for unrepresentable components.
UNKNOWN = "？"

#: Every IDS operator and the number of operands it takes.
OPERATORS: dict[str, int] = {
    **{chr(cp): 2 for cp in range(0x2FF0, 0x2FFE)},  # ⿰ … ⿽
    "⿲": 3,  # ⿲ left to middle and right
    "⿳": 3,  # ⿳ above to middle and below
    "⿾": 1,  # ⿾ horizontal reflection
    "⿿": 1,  # ⿿ rotation
    SUBTRACTION: 2,
    VARIATION_INDICATOR: 1,
}


class IDSSyntaxError(ValueError):
    """Raised when a string is not a well-formed IDS."""


def is_operator(char: str) -> bool:
    """Return whether *char* is an IDS operator (not a component)."""
    return char in OPERATORS


def _is_variation_selector(char: str) -> bool:
    cp = ord(char)
    return 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF


def strip_variation_selectors(text: str) -> str:
    """Remove standardized and ideographic variation selectors from *text*."""
    return "".join(c for c in text if not _is_variation_selector(c))


def _parse(ids: str) -> set[str]:
    tokens = strip_variation_selectors(ids)
    found: set[str] = set()
    pos = 0

    def parse(collect: bool) -> None:
        nonlocal pos
        if pos >= len(tokens):
            raise IDSSyntaxError(f"unexpected end of IDS {ids!r}")
        token = tokens[pos]
        pos += 1
        arity = OPERATORS.get(token)
        if arity is None:
            if collect and token != UNKNOWN:
                found.add(token)
            return
        for operand in range(arity):
            # The second operand of ㇯ is what gets *removed*.
            parse(collect and not (token == SUBTRACTION and operand == 1))

    parse(True)
    if pos != len(tokens):
        raise IDSSyntaxError(f"trailing characters in IDS {ids!r}")
    return found


def components(ids: str, *, strict: bool = False) -> set[str]:
    """Return the components named in a single IDS (one level deep).

    Operators and ``？`` are not components, and neither is anything that an
    ``㇯`` operator subtracts.  A malformed IDS raises :class:`IDSSyntaxError`
    if *strict* is true; otherwise every non-operator character in it is
    returned.

    >>> sorted(components("⿰木昜"))
    ['昜', '木']
    >>> sorted(components("㇯東㇒"))
    ['東']
    """
    try:
        return _parse(ids)
    except IDSSyntaxError:
        if strict:
            raise
        return {
            c
            for c in strip_variation_selectors(ids)
            if c not in OPERATORS and c != UNKNOWN
        }
