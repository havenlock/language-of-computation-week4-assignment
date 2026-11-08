"""Tests for ingest.py. Every test comes from a rule in rules.md.

Section 10 of rules.md (the examples table) gives one test per example.
The last four tests cover the rules the assignment names explicitly:
no duplicates on a re-run, an append-only log, counts that add up, and the
same database from the same file.
"""
import json

import pytest

from conftest import BATCH2_CSV, BOOKS_CSV


def warnings_for(entry, book_id):
    return [w for w in entry["warnings"] if str(w.get("book_id")) == str(book_id)]


def rejected_for(entry, book_id):
    return [r for r in entry["rejected_rows"] if str(r.get("book_id")) == str(book_id)]


def mentions(records, text):
    return any(text in json.dumps(r, ensure_ascii=False) for r in records)


# ---------------------------------------------------------------------------
# rules.md section 10, examples 1-17: one row, one outcome
# (isbn, isbn13, stored isbn10, stored isbn13, warning expected, text the warning must contain)
# ---------------------------------------------------------------------------
SINGLE_ROW_EXAMPLES = [
    pytest.param("0439139600", "9780439139601", "0439139600", "9780439139601", False, None, id="ex01-valid-and-agree"),
    pytest.param("439023483", "9.78043902348e+12", "0439023483", "9780439023481", True, None, id="ex02-pad-one-zero-and-float"),
    pytest.param("0-450-19827-8", "9780450198274", "0450198278", "9780450198274", False, None, id="ex03-hyphens"),
    pytest.param(" 162 001 4750 ", "9781620014752", "1620014750", "9781620014752", False, None, id="ex04-spaces"),
    pytest.param("031200009x", "9780312000097", "031200009X", "9780312000097", False, None, id="ex05-lowercase-x"),
    pytest.param("043965548X", "", "043965548X", "9780439655484", True, None, id="ex06-derive-isbn13"),
    pytest.param("9781982147600", "", "1982147601", "9781982147600", True, None, id="ex07-isbn13-in-isbn-column"),
    pytest.param("", "9780062398123", "0062398121", "9780062398123", True, None, id="ex08-derive-isbn10"),
    pytest.param("", "9.78043902348e+12", None, None, True, None, id="ex09-float-no-isbn10"),
    pytest.param("04390A3483", "", None, None, True, None, id="ex10-letter-in-digits"),
    pytest.param("1854433017", "", None, None, True, None, id="ex11-bad-checksum"),
    pytest.param("15287463097", "", None, None, True, None, id="ex12-eleven-digits"),
    pytest.param("7442912", "", None, None, True, None, id="ex13-seven-digits-not-padded"),
    pytest.param("", "", None, None, True, "no ISBN", id="ex14-no-isbn"),
    pytest.param("1555550126", "9781555550134", "1555550134", "9781555550134", True, "1555550126", id="ex15-disagree-isbn13-wins"),
    pytest.param("", "76783609419.0", None, None, True, None, id="ex16-malformed-isbn13"),
    pytest.param("", "9790000000001", None, "9790000000001", False, None, id="ex17-979-prefix"),
]


@pytest.mark.parametrize("isbn,isbn13,want10,want13,warn,warn_text", SINGLE_ROW_EXAMPLES)
def test_single_row_example(ws, isbn, isbn13, want10, want13, warn, warn_text):
    entry = ws.run(ws.write_csv([ws.row(1, isbn=isbn, isbn13=isbn13)]))

    assert entry["loaded"] == 1 and entry["rejected"] == 0, "the row must be loaded (rules 3-4)"
    book = ws.book(1)
    assert book is not None
    assert book["isbn10"] == want10
    assert book["isbn13"] == want13

    warns = warnings_for(entry, 1)
    if warn:
        assert warns, "rules.md expects a warning for this row"
        if warn_text:
            assert mentions(warns, warn_text), f"the warning must mention {warn_text!r}"
    else:
        assert not warns, "rules.md expects no warning for this row"


# ---------------------------------------------------------------------------
# rules.md section 10, examples 18-23: rows that depend on other rows
# ---------------------------------------------------------------------------

def test_ex18_isbn_already_owned_by_another_book(ws):
    entry = ws.run(ws.write_csv([
        ws.row(9, title="Angels & Demons", isbn="1416524797"),
        ws.row(10013, title="Paper Moons", isbn="1416524797"),
    ]))
    assert entry["loaded"] == 2 and entry["rejected"] == 0, "rule 5: the second book is still loaded"
    assert ws.book(9)["isbn13"] == "9781416524793"
    second = ws.book(10013)
    assert second["isbn10"] is None and second["isbn13"] is None
    assert mentions(warnings_for(entry, 10013), "ISBN already assigned to book 9")


def test_ex19_exact_duplicate_row_in_file_is_rejected(ws):
    row = ws.row(10001, title="Dup", isbn="0439139600", isbn13="9780439139601")
    entry = ws.run(ws.write_csv([row, dict(row)]))
    assert entry["loaded"] == 1
    assert entry["rejected"] == 1
    assert mentions(rejected_for(entry, 10001), "duplicate row in file")
    assert ws.count() == 1


def test_ex20_redelivery_with_changed_counts_is_updated(ws):
    ws.run(ws.write_csv([ws.row(132, title="Book 132", ratings_count=100)]))
    entry = ws.run(ws.write_csv([ws.row(132, title="Book 132", ratings_count=200)]))
    assert entry["updated"] == 1
    assert ws.book(132)["ratings_count"] == "200"
    rows = [r for r in entry["updated_rows"] if str(r["book_id"]) == "132"]
    assert rows, "rule 9: every updated row is listed in updated_rows"
    assert "ratings_count" in rows[0]["changed_columns"], "rule 7: the log lists the changed columns"


def test_ex21_redelivery_with_new_title_is_rejected_as_collision(ws):
    ws.run(ws.write_csv([ws.row(25, title="Original Title")]))
    entry = ws.run(ws.write_csv([ws.row(25, title="A Different Title")]))
    assert entry["rejected"] == 1 and entry["updated"] == 0
    assert mentions(rejected_for(entry, 25), "collision: title or author changed for book 25")
    assert ws.book(25)["title"] == "Original Title", "the stored row is left unchanged"


def test_ex22_redelivery_without_isbn_keeps_stored_isbn(ws):
    ws.run(ws.write_csv([ws.row(25, isbn="0439139600", isbn13="9780439139601")]))
    entry = ws.run(ws.write_csv([ws.row(25, isbn="", isbn13="")]))
    assert entry["skipped"] == 1 and entry["updated"] == 0
    book = ws.book(25)
    assert book["isbn10"] == "0439139600"
    assert book["isbn13"] == "9780439139601"


def test_ex23_blank_title_is_rejected(ws):
    entry = ws.run(ws.write_csv([ws.row(500, title="")]))
    assert entry["rejected"] == 1 and entry["loaded"] == 0
    assert rejected_for(entry, 500)
    assert ws.book(500) is None


# ---------------------------------------------------------------------------
# The four rules the assignment names explicitly
# ---------------------------------------------------------------------------

def test_same_file_twice_creates_no_duplicates(ws):
    ws.run(BOOKS_CSV)
    first_count = ws.count()
    second = ws.run(BOOKS_CSV)
    assert ws.count() == first_count, "rule 7: a re-run adds no books"
    assert second["loaded"] == 0 and second["updated"] == 0, "rule 7: every row is skipped the second time"


def test_every_run_appends_to_the_log(ws):
    path = ws.write_csv([ws.row(1, isbn="0439139600")])
    ws.run(path)
    first = ws.log_entries()
    assert len(first) == 1
    ws.run(path)
    both = ws.log_entries()
    assert len(both) == 2, "rule 9: each run appends one entry"
    assert both[0] == first[0], "rule 9: earlier entries are never overwritten"


def test_counts_add_up_to_rows_read(ws):
    for path in (BOOKS_CSV, BATCH2_CSV, BOOKS_CSV):
        e = ws.run(path)
        assert e["loaded"] + e["updated"] + e["skipped"] + e["rejected"] == e["rows_read"], path


def test_same_file_on_empty_database_gives_same_database(ws):
    ws.run(BOOKS_CSV)
    first = ws.dump()
    ws.reset()
    ws.run(BOOKS_CSV)
    assert ws.dump() == first, "rules.md section 8: same data, ignoring last_loaded_at"
