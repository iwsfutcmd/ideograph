"""Command-line interface: ``ideograph 木日勿`` or ``python -m ideograph``."""

from __future__ import annotations

import argparse
import sys

import ideograph


def _sort_key(order: str):
    if order == "strokes":
        return lambda c: (ideograph.total_strokes(c) or sys.maxsize, ord(c))
    return ord


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ideograph",
        description="Find ideographs by their components.",
    )
    parser.add_argument("text", nargs="?", help="components to search for (or, with -d, one character)")
    parser.add_argument(
        "-d", "--decompose", action="store_true", help="list the components of a character instead"
    )
    parser.add_argument(
        "-s",
        "--sort",
        choices=("codepoint", "strokes"),
        default="codepoint",
        help="result order (default: %(default)s)",
    )
    parser.add_argument("--ids", action="store_true", help="with -d, print the IDS sequences too")
    parser.add_argument("--info", action="store_true", help="show where the bundled data comes from")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {ideograph.__version__}")
    args = parser.parse_args(argv)

    if args.info:
        for key, value in ideograph.data_info().items():
            print(f"{key}\t{value}")
        return 0
    if args.text is None:
        parser.error("the following arguments are required: text")

    if args.decompose:
        try:
            result = ideograph.components(args.text)
        except ValueError as exc:
            parser.error(str(exc))
        if args.ids:
            for seq in ideograph.ids(args.text):
                print(f"{seq.sequence}\t{seq.sources}".rstrip("\t"))
    else:
        result = ideograph.find(args.text)
    print("".join(sorted(result, key=_sort_key(args.sort))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
