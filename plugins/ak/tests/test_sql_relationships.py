"""Reading relationships out of SQL when the database declares none.

Access databases often declare zero relationships, so this is the only thing that can fill
a catalogue's FK column. It has to be honest about three limits: an alias it cannot
bind, a table that does not exist, and the fact that a join proves use rather than
uniqueness.

One defect here was found by comparing a result against a plainer regex: the alias
pattern read `FROM 元商品マスタC LEFT JOIN` as alias `LEFT` for table `元商品マスタC`,
which put the real table name into the alias values and made the dangling-reference
check report 0 where 5 references were genuinely absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import sql_relationships as sql  # noqa: E402

TABLES = {"受注データ", "商品マスタ", "商品マスタ本", "店舗マスタ", "WK集計"}
QUERIES = {"q受注データ"}


def analyse(**sources: str):
    return sql.analyse(sources, TABLES, QUERIES)


def test_a_plain_join_is_read() -> None:
    result = analyse(one="SELECT * FROM 受注データ INNER JOIN 商品マスタ "
                         "ON 受注データ.商品コード = 商品マスタ.商品コード;")
    assert len(result.relationships) == 1
    relationship = result.relationships[0]
    assert {relationship.left_table, relationship.right_table} == {"受注データ", "商品マスタ"}
    assert relationship.left_column == relationship.right_column == "商品コード"
    assert relationship.occurrences == 1


def test_the_same_join_from_either_direction_is_one_relationship() -> None:
    result = analyse(
        a="SELECT * FROM 受注データ JOIN 商品マスタ ON 受注データ.商品コード = 商品マスタ.商品コード;",
        b="SELECT * FROM 商品マスタ JOIN 受注データ ON 商品マスタ.商品コード = 受注データ.商品コード;",
    )
    assert len(result.relationships) == 1
    assert result.relationships[0].occurrences == 2
    assert sorted(result.relationships[0].seen_in) == ["a", "b"]


def test_an_alias_is_resolved_to_its_table() -> None:
    result = analyse(one="SELECT * FROM 受注データ AS t1 INNER JOIN 商品マスタ AS m1 "
                         "ON t1.商品コード = m1.商品コード;")
    assert len(result.relationships) == 1
    assert {result.relationships[0].left_table,
            result.relationships[0].right_table} == {"受注データ", "商品マスタ"}


def test_a_join_keyword_is_not_mistaken_for_an_alias() -> None:
    """`FROM x LEFT JOIN y` used to bind `LEFT` as the alias of `x`."""
    result = sql.analyse(
        {"one": "SELECT * FROM 元商品マスタC LEFT JOIN 元商品マスタI "
                "ON 元商品マスタC.商品コード = 元商品マスタI.商品コード;"},
        TABLES, QUERIES)
    assert result.dangling == {"one": ["元商品マスタC", "元商品マスタI"]}, (
        "a table that exists nowhere must be reported, not absorbed as an alias"
    )


def test_a_column_joined_on_a_different_name_is_kept_as_written() -> None:
    """`DPマスタ.DPコード = コースマスタ.ＤＰコード` differs by width. Both are real."""
    tables = {"DPマスタ", "コースマスタ"}
    result = sql.analyse(
        {"one": "SELECT * FROM DPマスタ JOIN コースマスタ "
                "ON DPマスタ.DPコード = コースマスタ.ＤＰコード;"}, tables, set())
    relationship = result.relationships[0]
    assert not relationship.same_column_name
    assert {relationship.left_column, relationship.right_column} == {"DPコード", "ＤＰコード"}


def test_a_join_onto_a_saved_query_is_not_a_table_relationship() -> None:
    result = analyse(one="SELECT * FROM 受注データ JOIN q受注データ "
                         "ON 受注データ.商品コード = q受注データ.商品コード;")
    assert result.relationships == []
    assert result.joined_through_query == {"q受注データ": 1}
    assert result.unresolved_aliases == {}


def test_an_unbindable_alias_is_reported_not_guessed() -> None:
    result = analyse(one="SELECT * FROM (SELECT 1) AS t9 JOIN 商品マスタ "
                         "ON t9.商品コード = 商品マスタ.商品コード;")
    assert result.relationships == []
    assert "t9" in result.unresolved_aliases


# --- candidate keys ---------------------------------------------------------


def test_the_most_joined_column_is_the_candidate_key() -> None:
    result = analyse(
        a="SELECT * FROM 受注データ JOIN 商品マスタ ON 受注データ.商品コード = 商品マスタ.商品コード;",
        b="SELECT * FROM 受注データ JOIN 商品マスタ本 ON 受注データ.商品コード = 商品マスタ本.商品コード;",
        c="SELECT * FROM 受注データ JOIN 店舗マスタ ON 受注データ.店舗コード = 店舗マスタ.店舗コード;",
    )
    assert result.candidate_keys["受注データ"][0] == ("商品コード", 2)
    assert result.candidate_keys["商品マスタ"] == [("商品コード", 1)]


def test_a_work_table_is_named_as_one() -> None:
    """A work table with no key is normal; saying otherwise cries wolf 76 times."""
    assert sql.is_work_table("WK集計")
    assert sql.is_work_table("ＢＫ受注データ")
    assert not sql.is_work_table("受注データ")
    assert not sql.is_work_table("商品マスタ")


# --- dangling references ----------------------------------------------------


def test_a_table_created_by_the_statement_is_not_dangling() -> None:
    result = analyse(one="SELECT * INTO WK新規 FROM 受注データ;")
    assert result.dangling == {}


def test_a_missing_table_in_a_record_source_is_reported() -> None:
    """A screen whose record source names nothing cannot open."""
    result = analyse(**{"form 集計分類設定": "select * from 集計分類マスタ"})
    assert result.dangling == {"form 集計分類設定": ["集計分類マスタ"]}


def test_a_query_naming_only_real_objects_is_not_reported() -> None:
    result = analyse(one="SELECT * FROM 受注データ JOIN 店舗マスタ "
                         "ON 受注データ.店舗コード = 店舗マスタ.店舗コード;")
    assert result.dangling == {}


def test_bracketed_names_are_read() -> None:
    result = analyse(one="SELECT * FROM [受注データ] JOIN [店舗マスタ] "
                         "ON [受注データ].[店舗コード] = [店舗マスタ].[店舗コード];")
    assert len(result.relationships) == 1
    assert result.dangling == {}


def test_an_empty_source_is_skipped_rather_than_counted() -> None:
    result = analyse(one="", two="SELECT * FROM 受注データ;")
    assert result.sources_scanned == 1


# --- who writes each table --------------------------------------------------
#
# The business-role column needs a document, and rule EC-03 forbids reading a name as
# a meaning. Who writes a table is evidence, and it is what lets a reader classify
# without the analysis pretending to know.


def test_a_write_statement_names_its_writer() -> None:
    profile = sql.write_profile(
        {"form 集計": "DELETE * FROM WK集計; INSERT INTO WK集計 SELECT * FROM 受注データ"},
        TABLES)
    assert profile.of("WK集計") == ["form 集計 (DELETE)", "form 集計 (INSERT)"]
    assert "DELETE" in profile.summary("WK集計")


def test_a_vba_statement_separator_is_not_part_of_the_table_name() -> None:
    """VBA separates statements with `:`, so `FROM WK集計: rs...` used to attribute
    the write to a table called `WK集計:`, which is to say to nothing."""
    profile = sql.write_profile({"module M": 'DELETE * FROM WK集計: Set rs = x'}, TABLES)
    assert profile.of("WK集計") == ["module M (DELETE)"]


def test_a_table_nothing_writes_says_not_attributable_not_never_written() -> None:
    """Most recordset opens in a real corpus take a built string. Silence is not proof."""
    profile = sql.write_profile({"query q": "SELECT * FROM 商品マスタ"}, TABLES)
    assert profile.summary("商品マスタ") == "no writer attributable"


def test_a_transfer_call_naming_a_table_counts_as_a_write() -> None:
    profile = sql.write_profile(
        {"module AutoExec":
         'DoCmd.TransferDatabase acImport, "Microsoft Access", path, acTable, '
         '"商品マスタ", "商品マスタ"'},
        TABLES)
    assert profile.of("商品マスタ") == ["module AutoExec (TRANSFER)"]


def test_a_recordset_opened_by_name_counts_only_when_something_writes() -> None:
    read_only = sql.write_profile(
        {"form F": 'Set rs = db.OpenRecordset("WK集計")\nx = rs!a'}, TABLES)
    assert read_only.of("WK集計") == []
    writing = sql.write_profile(
        {"form F": 'Set rs = db.OpenRecordset("WK集計")\nrs.AddNew\nrs.Update'}, TABLES)
    assert writing.of("WK集計") == ["form F (RECORDSET)"]


def test_built_string_opens_are_counted_so_the_gap_is_visible() -> None:
    profile = sql.write_profile({"form F": "Set rs = db.OpenRecordset(sql)"}, TABLES)
    assert profile.built_string_opens == 1


# --- A105: composite joins --------------------------------------------------


def test_a_composite_join_is_one_relationship_on_both_columns() -> None:
    """`ON a.x = b.x AND a.y = b.y` used to be read as a join on `x` alone."""
    result = analyse(one="SELECT * FROM 受注データ AS t INNER JOIN 店舗マスタ AS s "
                         "ON t.店舗コード = s.店舗コード AND t.商品コード = s.商品コード;")
    assert len(result.relationships) == 1
    relationship = result.relationships[0]
    assert relationship.is_composite
    assert set(relationship.left_columns) == {"店舗コード", "商品コード"}
    assert relationship.left_columns == relationship.right_columns
    assert result.candidate_keys["店舗マスタ"] == [(relationship.right_column, 1)]


def test_a_composite_join_is_the_same_whichever_column_comes_first() -> None:
    result = analyse(
        a="SELECT * FROM 受注データ JOIN 店舗マスタ ON 受注データ.店舗コード = 店舗マスタ.店舗コード "
          "AND 受注データ.商品コード = 店舗マスタ.商品コード;",
        b="SELECT * FROM 店舗マスタ JOIN 受注データ ON (店舗マスタ.商品コード = 受注データ.商品コード) "
          "AND (店舗マスタ.店舗コード = 受注データ.店舗コード);",
    )
    assert len(result.relationships) == 1
    assert result.relationships[0].occurrences == 2


def test_a_literal_term_does_not_make_a_join_composite() -> None:
    result = analyse(one="SELECT * FROM 受注データ JOIN 店舗マスタ "
                         "ON 受注データ.店舗コード = 店舗マスタ.店舗コード AND 店舗マスタ.区分 = 1 "
                         "WHERE 受注データ.数量 = 店舗マスタ.数量;")
    assert len(result.relationships) == 1
    assert not result.relationships[0].is_composite
    assert result.relationships[0].left_column == "店舗コード"


def test_nested_joins_keep_each_condition_to_its_own_pair() -> None:
    result = analyse(one="SELECT * FROM (受注データ INNER JOIN 店舗マスタ "
                         "ON 受注データ.店舗コード = 店舗マスタ.店舗コード) INNER JOIN 商品マスタ "
                         "ON 受注データ.商品コード = 商品マスタ.商品コード;")
    assert len(result.relationships) == 2
    assert not any(r.is_composite for r in result.relationships)


# --- A105: make-table queries -----------------------------------------------


def test_a_make_table_target_is_read_from_a_whole_statement() -> None:
    assert sql.make_table_target("SELECT a, b INTO [WK集計] FROM 受注データ;") == "WK集計"
    assert sql.make_table_target(
        "PARAMETERS p Long;\nSELECT a INTO WK集計 FROM 受注データ;") == "WK集計"
    assert sql.make_table_target("SELECT [INTO], 'INTO x' FROM 受注データ;") is None
    assert sql.make_table_target("INSERT INTO WK集計 SELECT * FROM 受注データ;") is None
    assert sql.make_table_target("SELECT * FROM 受注データ;") is None


def test_a_make_table_query_is_a_writer_of_its_target() -> None:
    """A long column list put `INTO` past the scan's reach, and the verb read SELECT."""
    columns = ", ".join(f"受注データ.項目{n:02d}" for n in range(30))
    profile = sql.write_profile(
        {"query 集計作成": f"SELECT {columns}, '済' AS 状態 INTO WK集計 FROM 受注データ;"},
        TABLES)
    assert profile.of("WK集計") == ["query 集計作成 (SELECT INTO)"]
    assert profile.summary("WK集計") == "1 writer(s): SELECT INTO"


def test_a_short_make_table_statement_in_vba_is_named_select_into() -> None:
    profile = sql.write_profile(
        {"module M": 'CurrentDb.Execute "SELECT * INTO WK集計 FROM 受注データ"'}, TABLES)
    assert profile.of("WK集計") == ["module M (SELECT INTO)"]


# --- A105: recordset writers ------------------------------------------------


def test_a_recordset_write_is_attributed_to_its_procedure() -> None:
    code = ('Private Sub 読込()\n'
            '    Set rs = CurrentDb.OpenRecordset("商品マスタ")\n'
            '    x = rs!名称\n'
            'End Sub\n'
            'Private Sub 追加()\n'
            '    Set rs2 = CurrentDb.OpenRecordset("[WK集計]", dbOpenDynaset)\n'
            '    rs2.AddNew\n'
            '    rs2.Update\n'
            'End Sub\n')
    profile = sql.write_profile({"module M": code}, TABLES)
    assert profile.of("WK集計") == ["module M.追加 (RECORDSET)"]
    assert profile.of("商品マスタ") == [], "a recordset only read is not a writer"


def test_a_recordset_on_a_select_of_one_table_is_a_writer() -> None:
    code = ('Sub 更新()\n'
            '    Set rs = db.OpenRecordset("SELECT * FROM 受注データ WHERE 番号 = " & n)\n'
            '    rs.Edit\n'
            '    rs!数量 = 0\n'
            '    rs.Update\n'
            'End Sub\n')
    profile = sql.write_profile({"form F": code}, TABLES)
    assert profile.of("受注データ") == ["form F.更新 (RECORDSET)"]


def test_a_recordset_on_a_join_is_not_attributed() -> None:
    code = ('Sub 更新()\n'
            '    Set rs = db.OpenRecordset("SELECT * FROM 受注データ INNER JOIN 店舗マスタ '
            'ON 受注データ.店舗コード = 店舗マスタ.店舗コード")\n'
            '    rs.Edit\n'
            'End Sub\n')
    profile = sql.write_profile({"form F": code}, TABLES)
    assert profile.of("受注データ") == [] and profile.of("店舗マスタ") == []


def test_an_ado_recordset_and_a_with_block_are_read() -> None:
    code = ('Function 登録() As Boolean\n'
            '    rs.Open "WK集計", cn, adOpenKeyset, adLockOptimistic\n'
            '    rs.AddNew\n'
            'End Function\n'
            'Sub 補正()\n'
            '    strSQL = "SELECT * FROM 店舗マスタ"\n'
            '    Set rs = CurrentDb.OpenRecordset(strSQL)\n'
            '    With rs\n'
            '        .Edit\n'
            '        .Update\n'
            '    End With\n'
            'End Sub\n')
    profile = sql.write_profile({"module M": code}, TABLES)
    assert profile.of("WK集計") == ["module M.登録 (RECORDSET)"]
    assert profile.of("店舗マスタ") == ["module M.補正 (RECORDSET)"]


def test_a_commented_recordset_write_is_not_a_writer() -> None:
    code = ('Sub 追加()\n'
            '    Set rs = CurrentDb.OpenRecordset("WK集計")\n'
            "    'rs.AddNew\n"
            '    Rem rs.Edit\n'
            'End Sub\n')
    profile = sql.write_profile({"module M": code}, TABLES)
    assert profile.of("WK集計") == []
