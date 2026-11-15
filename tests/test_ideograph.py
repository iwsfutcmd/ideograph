import pytest

import ideograph
from ideograph import ids_syntax
from ideograph.__main__ import main


def test_find_basic():
    result = ideograph.find("木日勿")
    assert {"楊", "䵘", "鸉"} <= result
    assert all({"木", "日", "勿"} <= ideograph.components(c) | {c} for c in result)


def test_find_includes_component_itself():
    assert "木" in ideograph.find("木")


def test_find_is_strict_about_variant_components():
    assert "你" in ideograph.find("亻")
    assert "你" not in ideograph.find("人")


def test_find_ignores_non_components():
    assert ideograph.find("木 x ⿰") == ideograph.find("木")
    assert ideograph.find("") == set()
    assert ideograph.find("abc") == set()
    assert ideograph.find("'\"") == set()  # no SQL injection / quoting issues


def test_find_repeated_components_mean_at_least_that_many():
    two = ideograph.find("木木")
    assert {"林", "森", "麻"} <= two
    assert "杜" not in two and "木" not in two
    three = ideograph.find("木木木")
    assert "森" in three and "林" not in three
    assert {"品", "器"} <= ideograph.find("口口口")
    assert "器" in ideograph.find("口口口口") and "品" not in ideograph.find("口口口口")
    assert "晶" in ideograph.find("日日日")
    # Order and spacing don't matter; other components still have to be present.
    assert ideograph.find("木 日 木") == ideograph.find("木木日")
    assert ideograph.find("木木日") <= two
    # Normalization happens before counting: ⽊ is 木.
    assert ideograph.find("⽊木") == two
    # Ignored characters don't count.
    assert ideograph.find("木xx") == ideograph.find("木")


def test_component_counts():
    assert ideograph.component_counts("森")["木"] == 3
    assert ideograph.component_counts("森")["林"] == 1
    assert ideograph.component_counts("器")["口"] == 4
    assert set(ideograph.component_counts("楊")) == ideograph.components("楊")
    assert ideograph.component_counts("a") == {}


def test_find_accepts_iterables():
    assert ideograph.find(["木", "日"]) == ideograph.find("木日")


def test_normalization():
    assert ideograph.normalize("⽊") == "木"  # Kangxi radical
    assert ideograph.normalize("豈") == "豈"  # compatibility ideograph
    assert ideograph.normalize("⺮") == "𥫗"  # unused radical form → equivalent
    assert ideograph.normalize("⺈") == "⺈"  # radical form used in the data
    assert ideograph.find("⽊") == ideograph.find("木")
    assert ideograph.aliases()["⺮"] == "𥫗"


def test_components():
    assert ideograph.components("楊", recursive=False) == {"木", "昜"}
    assert {"木", "昜", "日", "勿"} <= ideograph.components("楊")
    assert "楊" not in ideograph.components("楊")
    assert ideograph.components("a") == set()
    with pytest.raises(ValueError):
        ideograph.components("楊柳")


def test_ids_with_sources():
    assert ideograph.ids("𧵉") == [("⿰貝尔", "G"), ("⿰貝尓", "T")]
    assert ideograph.ids("a") == []


def test_extension_j_from_chise():
    char = "\U00033479"  # last character of CJK Ext. J (Unicode 17.0)
    assert ideograph.ids(char)
    assert "中" in ideograph.components(char)
    assert char in ideograph.find("中𱷥")


def test_subtraction_operand_is_not_a_component():
    # 𬻌 = ㇯東㇒ (東 minus a stroke)
    assert "東" in ideograph.components("𬻌", recursive=False)
    assert "㇒" not in ideograph.components("𬻌", recursive=False)


def test_total_strokes():
    assert ideograph.total_strokes("楊") == 13
    assert ideograph.total_strokes("㇒") == 1
    assert ideograph.total_strokes("a") is None


def test_ideographs_and_info():
    chars = list(ideograph.ideographs())
    assert chars == sorted(chars, key=ord)
    assert len(chars) > 100_000
    info = ideograph.data_info()
    assert info["unicode_version"].startswith("18.")
    assert int(info["count_entries"]) == len(chars)


@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        ("⿰木昜", {"木", "昜"}),
        ("⿲彳山攵", {"彳", "山", "攵"}),
        ("㇯東㇒", {"東"}),
        ("⿰⿾臣臣", {"臣"}),
        ("〾⿱艹⿰？口", {"艹", "口"}),
        ("⿰木︀昜", {"木", "昜"}),  # variation selector
        ("木", {"木"}),
    ],
)
def test_ids_syntax(ids, expected):
    assert ids_syntax.components(ids, strict=True) == expected


def test_ids_syntax_counts():
    assert ids_syntax.component_counts("⿱口⿰口口") == {"口": 3}
    assert ids_syntax.component_counts("⿰木木") == {"木": 2}
    assert ids_syntax.component_counts("㇯⿰木木木") == {"木": 2}


def test_ids_syntax_malformed():
    with pytest.raises(ids_syntax.IDSSyntaxError):
        ids_syntax.components("⿰木", strict=True)
    with pytest.raises(ids_syntax.IDSSyntaxError):
        ids_syntax.components("⿰木日月", strict=True)
    assert ids_syntax.components("⿰木") == {"木"}


def test_cli(capsys):
    assert main(["木日勿"]) == 0
    assert "楊" in capsys.readouterr().out
    assert main(["-d", "--ids", "楊"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "⿰木昜\tGHTJKPV"
    assert "昜" in out[1]
    assert main(["--sort", "strokes", "木日勿"]) == 0
    out = capsys.readouterr().out.strip()
    strokes = [ideograph.total_strokes(c) for c in out]
    assert strokes == sorted(strokes)
