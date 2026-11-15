# ideograph

Look up ideographs by their components. At the moment it covers Han characters
(CJK unified ideographs) — all 101,997 of them in **Unicode 18.0**, including
Extension J — but it could be expanded to include other ideographic scripts
such as Tangut or Sumero-Akkadian cuneiform.

There is also a web interface: <https://iwsfutcmd.github.io/ideograph-webapp/>
([source](https://github.com/iwsfutcmd/ideograph-webapp)).

## Installation

```bash
pip install ideograph
```

or, for the latest version from this repository:

```bash
pip install git+https://github.com/iwsfutcmd/ideograph
```

Python 3.10 or later is required. There are no dependencies.

## Usage

### `find()`

`find()` takes a string of components and returns the set of ideographs that
contain *all* of them (at any depth).

```python
>>> import ideograph
>>> print("".join(sorted(ideograph.find("木日勿"))))
䵘楊糃鸉𣓗𣓾𣝻𣿘𥂸𥟘𥠜𦓻𦼴𩁒𪎥𪎧𪳷𬬍𭧺𰘲𰟣𱈾𱤅𲦺
```

Characters in the string that are not components of anything (spaces, Latin
letters, IDS operators …) are ignored. Input is normalized first: CJK
compatibility ideographs become their canonical equivalents, Kangxi Radicals
become the corresponding unified ideographs (⽊ → 木), and radical or stroke
forms that the data does not use become their equivalent unified ideograph
(⺮ → 𥫗).

Matching is visual rather than etymological, so 人 and 亻 are different
components.

### `components()`

`components()` takes a single ideograph and returns the set of its components,
the components of those components, and so on, down to the most basic
components in the data. Pass `recursive=False` for only the components named
in the character's own IDS.

```python
>>> sorted(ideograph.components("楊"))
['㇒', '一', '丨', '丿', '勹', '勿', '十', '囗', '日', '旦', '昜', '木', '𠃌', '𠆢']
>>> sorted(ideograph.components("楊", recursive=False))
['昜', '木']
```

### `ids()`, `total_strokes()`, `ideographs()`, `aliases()`, `data_info()`

```python
>>> ideograph.ids("𧵉")   # one IDS per regional glyph form, with its sources
[IDS(sequence='⿰貝尔', sources='G'), IDS(sequence='⿰貝尓', sources='T')]
>>> ideograph.total_strokes("楊")
13
>>> sum(1 for _ in ideograph.ideographs())
101997
>>> ideograph.data_info()["unicode_version"]
'18.0.0'
```

`ideograph.ids_syntax` contains the IDS parser used to build the data
(it understands the Unicode 15.1 operators ⿼⿽⿾⿿ and ㇯).

### Command line

```console
$ ideograph 木日勿
䵘楊糃鸉𣓗𣓾𣝻𣿘𥂸𥟘𥠜𦓻𦼴𩁒𪎥𪎧𪳷𬬍𭧺𰘲𰟣𱈾𱤅𲦺
$ ideograph --sort strokes 木日勿
𣓗𣓾楊𥟘𥠜𦓻𱤅糃𣿘𪳷𰘲𲦺𦼴𭧺𰟣𣝻𥂸𪎥𪎧䵘𩁒𬬍鸉𱈾
$ ideograph -d --ids 楊
⿰木昜	GHTJKPV
㇒一丨丿勹勿十囗日旦昜木𠃌𠆢
$ ideograph --info
```

You may need a font with wide CJK coverage (e.g. BabelStone Han, Jigmo,
Plangothic, TH-Tshyn) to see characters from the newer extensions.

## Data

Component data comes from [BabelStone IDS](https://babelstone.co.uk/CJK/IDS.TXT),
supplemented by [CHISE IDS](https://gitlab.chise.org/CHISE/ids) for characters
BabelStone does not yet cover, and stroke counts from the
[Unihan database](https://www.unicode.org/reports/tr38/). See
[DATA.md](DATA.md) for details and licensing: **the bundled database is
GPL-2.0-or-later** because of the CHISE data; the code is MIT.

Earlier versions (1.x) used [cjkvi-ids](https://github.com/cjkvi/cjkvi-ids),
which has not been updated since 2019; unencoded components are no longer
mapped to the Private Use Area.

The data is stored in a SQLite database, which can be regenerated with:

```bash
python scripts/generate_data.py            # downloads sources into .cache/
python scripts/generate_data.py --refresh  # re-download the latest sources
```

Pinned versions (Unicode version, CHISE commit) are constants at the top of the
script and can be overridden on the command line (`--help`).

## Development

```bash
pip install -e . pytest
pytest
```
