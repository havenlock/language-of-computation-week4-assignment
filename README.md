# Module 4 Assignment – MSAI-5523

This is my Module 4 assignment for MSAI-5523 Language of Computation.

Partner: Fernando Martinez

## Get the code onto your computer (first time only)

```bash
mkdir -p ~/workspace/language-of-computation
cd ~/workspace/language-of-computation
git clone -b assignment https://github.com/havenlock/language-of-computation-week4-assignment.git week4-assignment
cd week4-assignment
```

## Install what the tests need

```bash
cd ~/workspace/language-of-computation/week4-assignment
python3 -m pip install --user pytest
```

## Run the tests

```bash
cd ~/workspace/language-of-computation/week4-assignment
python3 -m pytest -v
```

To save what the terminal prints, use `test-results-before.txt` for the first run (before `ingest.py` is changed) and `test-results.txt` for the final run:

```bash
python3 -m pytest -v 2>&1 | tee test-results-before.txt
python3 -m pytest -v 2>&1 | tee test-results.txt
```

The tests use a temporary `test.db` and delete it afterwards. They never touch `books.db` or `ingestion-log.json` in this folder.

## Test runs

**First run (before changing `ingest.py`), 8 Nov 2026:** I ran the suite myself in my own terminal and got the same result Claude Code recorded in `test-results-before.txt`: **23 passed, 4 failed**. The four failures are the rules my partner and I changed in Part 1:

- example 13: a 7-digit ISBN must not be padded
- example 15: when the two ISBNs disagree, `isbn13` wins
- example 18: a book whose ISBN is already taken still loads, without the ISBN
- example 21: a re-delivery with a new title is rejected as a collision

## Run the ingestion

Start clean, then load the original file, the same file again, and the second delivery:

```bash
cd ~/workspace/language-of-computation/week4-assignment
rm -f books.db ingestion-log.json
python3 ingest.py books.csv
python3 ingest.py books.csv
python3 ingest.py books-batch2.csv
```

Open `report.html` in a browser and pick `ingestion-log.json` to see the runs.
