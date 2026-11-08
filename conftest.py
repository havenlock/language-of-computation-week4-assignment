"""Shared pytest fixtures for the ingest.py test suite.

Every test runs ingest.py against a database named test.db inside a fresh
temporary folder. The folder, and everything in it, is deleted when the test
ends, whether it passed or failed. The books.db and ingestion-log.json in the
project folder are never touched; a session check fails the run if they change.
"""
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ingest  # noqa: E402

BOOKS_CSV = os.path.join(HERE, "books.csv")
BATCH2_CSV = os.path.join(HERE, "books-batch2.csv")
PROTECTED = [os.path.join(HERE, "books.db"), os.path.join(HERE, "ingestion-log.json")]


def _fingerprint(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def protect_real_files():
    """Fail the run if any test changed the real books.db or ingestion-log.json."""
    before = {p: _fingerprint(p) for p in PROTECTED}
    yield
    after = {p: _fingerprint(p) for p in PROTECTED}
    assert before == after, "a test touched books.db or ingestion-log.json in the project folder"


def csv_header():
    """The column names of the real delivery, read from books.csv."""
    with open(BOOKS_CSV, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


class Workspace:
    """A throwaway folder holding test.db, its log, and any CSVs a test writes."""

    def __init__(self, root):
        self.root = root
        self.db = os.path.join(root, "test.db")
        self.log = os.path.join(root, "test-ingestion-log.json")
        self.header = csv_header()
        self._n = 0

    def row(self, book_id, title="A Book", authors="An Author", isbn="", isbn13="", **extra):
        r = {c: "" for c in self.header}
        r.update(book_id=str(book_id), title=title, authors=authors, isbn=isbn, isbn13=isbn13)
        r.update({k: str(v) for k, v in extra.items()})
        return r

    def write_csv(self, rows, name=None):
        self._n += 1
        path = os.path.join(self.root, name or f"delivery-{self._n}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.header)
            w.writeheader()
            w.writerows(rows)
        return path

    def run(self, path):
        """Run ingest.py on a file; return that run's entry from the log."""
        ingest.ingest(path)
        return self.log_entries()[-1]

    def log_entries(self):
        with open(self.log, encoding="utf-8") as f:
            return json.load(f)

    def book(self, book_id):
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        try:
            r = con.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    def dump(self):
        """Every book and every column except last_loaded_at (rules.md section 8)."""
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("SELECT * FROM books ORDER BY book_id").fetchall()
            return [{k: r[k] for k in r.keys() if k != "last_loaded_at"} for r in rows]
        finally:
            con.close()

    def count(self):
        con = sqlite3.connect(self.db)
        try:
            return con.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        finally:
            con.close()

    def reset(self):
        for p in (self.db, self.log):
            if os.path.exists(p):
                os.remove(p)


@pytest.fixture
def ws(monkeypatch):
    root = tempfile.mkdtemp(prefix="ingest-test-")
    w = Workspace(root)
    monkeypatch.setattr(ingest, "DB_PATH", w.db)
    monkeypatch.setattr(ingest, "LOG_PATH", w.log)
    try:
        yield w
    finally:
        shutil.rmtree(root, ignore_errors=True)
