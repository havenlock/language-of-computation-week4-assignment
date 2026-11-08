#!/usr/bin/env python3
"""ingest.py — load a books CSV into books.db, following rules.md exactly.

Usage:
    python3 ingest.py <file.csv>

Deterministic: no network, no AI, no randomness. The same file always gives
the same result. Running the same file twice creates no duplicates. Every run
appends one entry to ingestion-log.json.
"""
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "books.db")
LOG_PATH = os.path.join(HERE, "ingestion-log.json")

CSV_COLUMNS = [
    "book_id", "goodreads_book_id", "best_book_id", "work_id", "books_count",
    "isbn", "isbn13", "authors", "original_publication_year", "original_title",
    "title", "language_code", "average_rating", "ratings_count",
    "work_ratings_count", "work_text_reviews_count", "ratings_1", "ratings_2",
    "ratings_3", "ratings_4", "ratings_5", "image_url", "small_image_url",
]
# Columns compared to decide "updated" vs "skipped" (rule 7).
COMPARE_COLUMNS = [c for c in CSV_COLUMNS if c not in ("isbn", "isbn13")] + ["isbn10", "isbn13"]


# ---------------------------------------------------------------------------
# ISBN arithmetic (rule 1)
# ---------------------------------------------------------------------------

def isbn10_valid(s):
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
    return total % 11 == 0


def isbn13_valid(s):
    if not re.fullmatch(r"97[89]\d{10}", s):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s))
    return total % 10 == 0


def isbn10_to_13(s10):
    body = "978" + s10[:9]
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(body))
    return body + str((10 - total % 10) % 10)


def isbn13_to_10(s13):
    if not s13.startswith("978"):
        return None
    body = s13[3:12]
    total = sum((10 - i) * int(c) for i, c in enumerate(body))
    check = (11 - total % 11) % 11
    return body + ("X" if check == 10 else str(check))


def normalize(raw):
    """Rule 2: whitespace, hyphens, case. Formatting only."""
    if raw is None:
        return ""
    return re.sub(r"[\s-]", "", raw.strip()).upper()


FLOAT_RE = re.compile(r"\d\.\d+E\+12|\d{13}\.0")


def resolve_isbns(raw10, raw13):
    """Apply rules 2–4 to one row. Returns (isbn10, isbn13, warnings)."""
    warnings = []
    float13 = False
    n10, n13 = normalize(raw10), normalize(raw13)

    # --- evaluate the isbn column -------------------------------------
    v10 = None          # a trusted ISBN-10
    moved13 = None      # a valid ISBN-13 found in the isbn column
    if n10 == "":
        pass
    elif isbn10_valid(n10):
        v10 = n10
    elif re.fullmatch(r"\d{9}", n10) and isbn10_valid("0" + n10):
        v10 = "0" + n10
        warnings.append(("isbn", raw10, v10, "lost leading zero restored"))
    elif isbn13_valid(n10) and n13 == "":
        moved13 = n10
        warnings.append(("isbn13", raw10, n10, "ISBN-13 found in isbn column; moved to isbn13"))
    else:
        warnings.append(("isbn", raw10, None, describe_bad10(n10)))

    # --- evaluate the isbn13 column -----------------------------------
    v13 = None
    if moved13:
        v13 = moved13
    elif n13 == "":
        pass
    elif isbn13_valid(n13):
        v13 = n13
    elif FLOAT_RE.fullmatch(n13):
        float13 = True
    else:
        warnings.append(("isbn13", raw13, None, describe_bad13(n13)))

    # --- reconcile the two (rules 3 and 4) -----------------------------
    if v10 and v13:
        if isbn10_to_13(v10) != v13:
            # Rule 3: isbn13 wins; the ISBN-10 is derived again from it (none for 979).
            discarded = v10
            v10 = isbn13_to_10(v13)
            warnings.append(("isbn", raw10, v10,
                             f"isbn {discarded} disagrees with isbn13 {v13} "
                             f"({discarded} converts to {isbn10_to_13(discarded)}); isbn13 wins, "
                             + ("isbn10 derived from isbn13" if v10 else "no ISBN-10 exists for a 979 ISBN-13")))
    elif v10 and not v13:
        v13 = isbn10_to_13(v10)
        warnings.append(("isbn13", raw13, v13,
                         "float export lost the last digit; replaced by value derived from isbn"
                         if float13 else "derived from isbn"))
    elif v13 and not v10:
        d = isbn13_to_10(v13)
        if d:
            v10 = d
            if n10 != "" and not moved13:
                pass  # the bad isbn was already warned about above
            warnings.append(("isbn", raw10, v10, "derived from isbn13"))
    if float13 and not v13:
        warnings.append(("isbn13", raw13, None, "float export; last digit lost and no valid isbn to derive from"))
    if not v10 and not v13 and n10 == "" and n13 == "":
        warnings.append(("isbn", "", None, "no ISBN"))
    return v10, v13, warnings


def describe_bad10(s):
    if re.search(r"[A-WYZ]", s) or re.search(r"X.", s):
        return "letter in digits"
    if len(s) == 10:
        return "checksum fails"
    if re.fullmatch(r"\d{9}", s):
        return "9 digits; restoring one leading zero fails checksum"
    if re.fullmatch(r"\d{1,8}", s):
        return f"{len(s)} digits; only one lost leading zero may be restored"
    if len(s) == 13:
        return "13-digit value in isbn column but isbn13 also present, or checksum fails"
    return f"wrong length ({len(s)} characters)"


def describe_bad13(s):
    if len(s) == 13 and s.isdigit():
        return "checksum fails" if s[:3] in ("978", "979") else "does not start with 978/979"
    return f"not a 13-digit ISBN ({s})"


# ---------------------------------------------------------------------------
# Database (rule 8)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    book_id                 INTEGER PRIMARY KEY,
    goodreads_book_id       TEXT,
    best_book_id            TEXT,
    work_id                 TEXT,
    books_count             TEXT,
    isbn_raw                TEXT,
    isbn13_raw              TEXT,
    isbn10                  TEXT,
    isbn13                  TEXT,
    authors                 TEXT,
    original_publication_year TEXT,
    original_title          TEXT,
    title                   TEXT NOT NULL,
    language_code           TEXT,
    average_rating          TEXT,
    ratings_count           TEXT,
    work_ratings_count      TEXT,
    work_text_reviews_count TEXT,
    ratings_1               TEXT,
    ratings_2               TEXT,
    ratings_3               TEXT,
    ratings_4               TEXT,
    ratings_5               TEXT,
    image_url               TEXT,
    small_image_url         TEXT,
    last_source_file        TEXT,
    last_loaded_at          TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS books_isbn13_unique ON books(isbn13) WHERE isbn13 IS NOT NULL;
"""


def open_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest(path):
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    source = os.path.basename(path)
    con = open_db()

    counts = dict(rows_read=0, loaded=0, updated=0, skipped=0, rejected=0)
    rejected_rows, warnings_out, updated_rows = [], [], []
    seen_rows = set()              # exact rows seen in this file (rule 6.2)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts["rows_read"] += 1
            row = {k: (v if v is not None else "") for k, v in row.items()}
            title = row.get("title", "").strip()
            bid_raw = row.get("book_id", "").strip()

            raw10, raw13 = row.get("isbn", ""), row.get("isbn13", "")

            # Rule 6.1
            if not bid_raw.isdigit():
                reject(rejected_rows, counts, bid_raw, title, raw10, raw13,
                       f"missing or invalid book_id ({bid_raw!r})")
                continue
            if not title:
                reject(rejected_rows, counts, bid_raw, title, raw10, raw13, "missing title")
                continue
            book_id = int(bid_raw)

            # Rule 6.2
            sig = tuple(row.get(c, "") for c in CSV_COLUMNS)
            if sig in seen_rows:
                reject(rejected_rows, counts, book_id, title, raw10, raw13, "duplicate row in file")
                continue
            seen_rows.add(sig)

            isbn10, isbn13, warns = resolve_isbns(raw10, raw13)

            # Rule 5: an ISBN owned by another book is not stored; the row still loads.
            if isbn13:
                owner = con.execute(
                    "SELECT book_id FROM books WHERE isbn13 = ? AND book_id != ?", (isbn13, book_id)
                ).fetchone()
                if owner:
                    warns.append(("isbn13", isbn13, None,
                                  f"ISBN already assigned to book {owner['book_id']}"))
                    isbn10 = isbn13 = None

            incoming = {c: row.get(c, "") for c in CSV_COLUMNS if c not in ("isbn", "isbn13")}
            incoming.update(isbn_raw=row.get("isbn", ""), isbn13_raw=row.get("isbn13", ""),
                            isbn10=isbn10, isbn13=isbn13)

            existing = con.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
            if existing is None:
                incoming.update(last_source_file=source, last_loaded_at=run_at)
                cols = ", ".join(incoming)
                con.execute(f"INSERT INTO books ({cols}) VALUES ({', '.join('?' * len(incoming))})",
                            list(incoming.values()))
                counts["loaded"] += 1
                record_warnings(warnings_out, book_id, title, "loaded", warns)
                continue

            # Rule 7: re-delivery. A changed title or author is a collision (rule 6.3).
            if (existing["title"] or "") != incoming["title"] or (existing["authors"] or "") != incoming["authors"]:
                reject(rejected_rows, counts, book_id, title, raw10, raw13,
                       f"collision: title or author changed for book {book_id}")
                continue
            if incoming["isbn13"] is None and existing["isbn13"] is not None:
                incoming["isbn10"], incoming["isbn13"] = existing["isbn10"], existing["isbn13"]
                warns = [w for w in warns if w[3] != "no ISBN"]
                warns.append(("isbn", row.get("isbn", ""), existing["isbn13"],
                              "incoming ISBN empty/unusable; stored ISBN kept"))
            changed = [c for c in COMPARE_COLUMNS
                       if str(existing[c] if existing[c] is not None else "") !=
                          str(incoming[c] if incoming[c] is not None else "")]
            if not changed:
                counts["skipped"] += 1
                continue
            incoming.update(last_source_file=source, last_loaded_at=run_at)
            sets = ", ".join(f"{c} = ?" for c in incoming)
            con.execute(f"UPDATE books SET {sets} WHERE book_id = ?", list(incoming.values()) + [book_id])
            counts["updated"] += 1
            updated_rows.append(dict(book_id=book_id, title=title, changed_columns=changed))
            record_warnings(warnings_out, book_id, title, "updated", warns)

    con.commit()
    totals = dict(
        books=con.execute("SELECT COUNT(*) FROM books").fetchone()[0],
        with_isbn13=con.execute("SELECT COUNT(*) FROM books WHERE isbn13 IS NOT NULL").fetchone()[0],
        without_any_isbn=con.execute(
            "SELECT COUNT(*) FROM books WHERE isbn13 IS NULL AND isbn10 IS NULL").fetchone()[0],
    )
    con.close()

    entry = dict(run_at=run_at, source_file=source, **counts,
                 rejected_rows=rejected_rows, warnings=warnings_out, updated_rows=updated_rows,
                 database_totals=totals)
    append_log(entry)
    return entry


def reject(rejected_rows, counts, book_id, title, isbn, isbn13, reason):
    counts["rejected"] += 1
    rejected_rows.append(dict(book_id=book_id, title=title, isbn=isbn, isbn13=isbn13, reason=reason))


def record_warnings(out, book_id, title, action, warns):
    for field, before, after, reason in warns:
        out.append(dict(book_id=book_id, title=title, action=action, field=field,
                        before=before, after=after, reason=reason))


def append_log(entry):
    log = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8") as f:
            log = json.load(f)
        if not isinstance(log, list):
            raise SystemExit(f"{LOG_PATH} is not a JSON list; refusing to overwrite it")
    log.append(entry)
    tmp = LOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    os.replace(tmp, LOG_PATH)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = argv[1]
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 1
    e = ingest(path)
    print(f"{e['source_file']}: read {e['rows_read']}, loaded {e['loaded']}, "
          f"updated {e['updated']}, skipped {e['skipped']}, rejected {e['rejected']}  "
          f"(db: {e['database_totals']['books']} books, "
          f"{e['database_totals']['with_isbn13']} with ISBN-13)")
    for r in e["rejected_rows"]:
        print(f"  REJECTED {r['book_id']} {r['title'][:40]!r}: {r['reason']}")
    print(f"  {len(e['warnings'])} warnings — see ingestion-log.json / report.html")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
