# ideograph

A tool to look up ideographs by their components. At the moment, it only contains Han characters, but it could be expanded to include other ideographic scripts such as Tangut or Sumero-Akkadian Cuneiform.

## Installation

```bash
$ pip install ideograph
```

## Usage

*ideograph* consists of a single function `find()`, which takes a string of ideograph components and returns a set of ideographs that include all of those components.

Characters in the component string that are not ideographic components are ignored.

Note that the current implementation is quite strict and relies on visual distinction for components rather than etymological connection: e.g. "人" ≠ "亻".

*ideograph* can either be used from the command line:

```bash
$ ideograph 木日勿
䵘楊鸉𣝻𣿘𥂸𥠜𦼴𩁒𪳷𬬍
```

or imported as a Python package:

```python3
>>> import ideograph
>>> ideograph.find("木日勿")
{'𣿘', '𣝻', '𥠜', '𪎥', '𩁒', '𪎧', '𥟘', '𣓗', '楊', '𣓾', '𬬍', '𪳷', '𦼴', '鸉', '䵘', '𥂸'}
```

## Data

Character components are derived from the [cjkvi-ids database](https://github.com/cjkvi/cjkvi-ids) (included in this Git repository as a submodule), specifically the `ids-cdp.txt` data file. As some components do not currently have a Unicode code point assigned to them, they are given code points in the Private Use Area of Unicode. Note that because of this, some of these characters may be returned by the `find()` function.

Data is stored in a sqlite3 database, which can be regenerated from cjkvi-ids data by running the `generate_data.py` script.