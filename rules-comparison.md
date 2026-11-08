# Rules comparison: Alex vs. Nando (Module 3 rules.md)

**Alex (Student A):** https://github.com/havenlock/language-of-computation-week3-assignment/blob/assignment/rules.md
**Nando (Student B):** https://github.com/FlightsandGigabytes/language-of-computation-week3-assignment/blob/assignment/rules.md

This file compares the two sets of rules decision by decision. It does not judge which rules are better.

Key: **Agree** · **Disagree** · **Only Alex** / **Only Nando** (the other file says nothing)

## 1. ISBN problems

| # | Decision | Alex | Nando | Status |
|---|---|---|---|---|
| 1 | What a valid ISBN-10 / ISBN-13 is | 10 chars, X allowed last, mod 11; 13 digits, 978/979, mod 10 | Same | **Agree** |
| 2 | Lower-case `x` check digit | Upper-cased during normalization | Not mentioned | **Only Alex** |
| 3 | Hyphens and spaces | Removed during normalization. Not counted as a repair, not logged | Removed. Called a "repair" | **Agree** on result; differ on whether it counts as a repair |
| 4 | ISBN-10 missing one leading zero (`439023483`) | Pad to 10, keep if checksum passes | Same | **Agree** |
| 5 | Shorter values (`7442912`, 7 digits) | Any ISBN-10 under 10 digits is padded; `0007442912` passes the checksum, so it loads | Listed as wrong length → reject | **Disagree** |
| 6 | `isbn13` as a float (`9.78…e+12`) | Discard; derive ISBN-13 from the ISBN-10 | Same | **Agree** |
| 7 | Float `isbn13` and no usable ISBN-10 | Row loads, ISBNs NULL, warning | No usable ISBN → reject | **Disagree** |
| 8 | 13 digits in the `isbn` column | Move to `isbn13` | Move to `isbn13`; reject if checksum fails | **Agree** |
| 9 | `isbn` empty, valid 978 `isbn13` | Derive and store an ISBN-10 | ISBN-10 not stored at all | **Only Alex** |
| 10 | Letter in the digits, bad checksum, wrong length (11+ digits) | Row **loads**, ISBNs NULL, warning | Row **rejected** | **Disagree** |
| 11 | Both ISBN fields empty | Row **loads**, warning `no ISBN` | Row **rejected** | **Disagree** |
| 12 | `isbn` and `isbn13` both valid but disagree | Neither trusted; both NULL, row loads with warning | `isbn13` wins; row loads with it | **Disagree** |
| 13 | ISBN-10 next to a 979 ISBN-13 | Treated as a disagreement (both NULL) | Not mentioned | **Only Alex** |
| 14 | Malformed non-float `isbn13` (`76783609419.0`) | Unfixable → load, NULL, warning | Not named; falls under "no usable ISBN" → reject | **Only Alex** names it |

## 2. What makes two rows the same book

| # | Decision | Alex | Nando | Status |
|---|---|---|---|---|
| 15 | Identity key | `book_id` | Canonical ISBN-13 | **Disagree** |
| 16 | Row with no usable ISBN | Still a book; loaded | Can't be identified; rejected | **Disagree** |
| 17 | Missing `book_id` or blank title | Rejected | Not mentioned | **Only Alex** |
| 18 | Exact duplicate row in the same file | Second copy **rejected** (`duplicate row in file`) | Loaded once; second copy is "already exists" → **skipped** | **Disagree** |
| 19 | Two books share one ISBN | Newcomer rejected when the ISBN belongs to a different **`book_id`** | Newcomer rejected when the **title or author** differs | **Disagree** on what triggers it; agree the newcomer is rejected |

## 3. When a book arrives again

| # | Decision | Alex | Nando | Status |
|---|---|---|---|---|
| 20 | Nothing changed | `skipped` | `skipped` (already exists) | **Agree** |
| 21 | Something changed | Any changed column is overwritten → `updated`; log lists the columns | Only publication year can change → `updated`. Title or author change → **collision, rejected** | **Disagree** |
| 22 | Incoming row has no ISBN, stored row does | Stored ISBN kept | Incoming row rejected (no usable ISBN) | **Disagree** (Alex states it; Nando's result follows from rule 16) |
| 23 | Compare raw values or cleaned values | After normalization/repair | Not mentioned | **Only Alex** |
| 24 | Same file run twice | Zero inserts, zero updates | No duplicates | **Agree** |

## 4. Database and report

| # | Decision | Alex | Nando | Status |
|---|---|---|---|---|
| 25 | Columns stored | Every CSV column, plus `isbn10`, `isbn13`, raw ISBN strings, source file, load time | `canonical_isbn13`, title, authors, publication year, `book_id` only | **Disagree** |
| 26 | Per-run facts | Timestamp, file, rows read, loaded / updated / skipped / rejected | Same | **Agree** |
| 27 | Rejected rows | `book_id`, title, reason | `book_id`, title, raw `isbn`/`isbn13`, reason as a sentence with the value | **Agree**, Nando adds raw values |
| 28 | Warnings on loaded rows (repairs, before → after) | Required | Not mentioned (no warnings concept) | **Only Alex** |
| 29 | Log file and report format | Append-only `ingestion-log.json`, plus `report.html` opened from disk, plus database totals | "The report"; format not specified | **Only Alex** |
| 30 | Deterministic, offline, no AI | Yes | Yes | **Agree** |

**Tally:** 10 agree · 12 disagree · 8 only Alex · 0 only Nando

## 5. Alex's examples under Nando's rules

| # | Value(s) | Alex's outcome | Under Nando's rules | Same? |
|---|---|---|---|---|
| 1 | `1416524797` / float | Load, ISBN-13 derived, warning | Load, ISBN-13 derived | Same |
| 2 | `439023483` / float | Pad, derive, load, warning | Pad, derive, load | Same |
| 3 | `0439139600` / `9780439139601` | Load | Load | Same |
| 4 | `0-450-19827-8` | Load (normalization) | Load (repair) | Same |
| 5 | ` 162 001 4750 ` | Load | Load | Same |
| 6 | `031200009x` | Upper-case → load | Lower-case `x` not covered | **Unclear** |
| 7 | `9781982147600` in `isbn` | Move, derive ISBN-10, load | Move, load | Same |
| 8 | empty / `9780062398123` | Derive ISBN-10, load | Load on ISBN-13 | Same |
| 9 | `04390A3483` | Load, NULL, warning | **Reject** | **Differs** |
| 10 | `15287463097` | Load, NULL, warning | **Reject** | **Differs** |
| 11 | `1854433017` | Load, NULL, warning | **Reject** | **Differs** |
| 12 | `1555550126` / `9781555550134` | Load, both NULL | **Load with `9781555550134`** | **Differs** |
| 13 | both empty | Load, warning `no ISBN` | **Reject** | **Differs** |
| 14 | `1416524797` on book 10013 | Reject (ISBN belongs to book 9) | Reject (different title) | Same |
| 15 | Book 10001, second identical row | Reject (duplicate row) | **Skip** | **Differs** |
| 16 | Book 24 re-delivered, clean ISBNs | Skip | Skip | Same |
| 17 | Book 132, higher `ratings_count` | Update | **Skip** (ratings not stored) | **Differs** |
| 18 | Book 25, both ISBNs empty | Skip, stored ISBNs kept | **Reject** | **Differs** |
| 19 | `76783609419.0` in `isbn13` | Load, NULL, warning | **Reject** | **Differs** |
| 20 | `9790000000001` | Load, `isbn10` NULL | Load | Same |

**9 of 20 differ, 1 unclear.**

## 6. Nando's examples under Alex's rules

| # | Value(s) | Nando's outcome | Under Alex's rules | Same? |
|---|---|---|---|---|
| 1 | `0439139600` | Load | Load | Same |
| 2 | `439023483` | Pad, load | Pad, load, warning | Same |
| 3 | `0-450-19827-8` | Repair, load | Normalize, load | Same |
| 4 | ` 162 001 4750 ` | Repair, load | Normalize, load | Same |
| 5 | `043965548X` | Load | Load | Same |
| 6 | `9780439139601` | Load | Load | Same |
| 7 | `9.78043902348e+12` | Ignore; rebuild from ISBN-10 if present | Same if ISBN-10 present. If not: **load with NULL** (Nando: reject) | Same / **differs** with no ISBN-10 |
| 8 | `9781982147600` in `isbn` | Move, load | Move, load | Same |
| 9 | `04390A3483` | Reject | **Load, NULL, warning** | **Differs** |
| 10 | `1854433017` | Reject | **Load, NULL, warning** | **Differs** |
| 11 | `15287463097` | Reject | **Load, NULL, warning** | **Differs** |
| 12 | `7442912` | Reject (wrong length) | **Pad → `0007442912`, checksum passes, load** | **Differs** |
| 13 | both empty | Reject | **Load, warning** | **Differs** |
| 14 | `1416524797` on a second title | Reject (collision) | Reject (ISBN belongs to another `book_id`) | Same |
| 15 | `1555550126` / `9781555550134` | Load with `9781555550134` | **Load, both NULL** | **Differs** |
| 16 | Same book, identical, seen again | Skip | Skip | Same |
| 17 | Same ISBN-13, new title | Update | Update if same `book_id`; **reject** if a different `book_id` | **Depends** |

**7 of 17 differ, 2 conditional.**

## 7. Notes for agreeing the final rules

- **Nando's file contradicts itself on example 17.** Section 5 says a changed title is a collision and is rejected. Example 17 says it is an update.
- **Nando's file also contradicts itself on example 12.** Section 2 pads ISBN-10s that lost their leading zeros. `7442912` pads to `0007442912`, which passes the checksum, but example 12 rejects it as wrong length.
- **Four decisions drive most of the differences:**
  1. the identity key (#15)
  2. load-or-reject for unfixable ISBNs (#10, #11, #16)
  3. disagreeing ISBN pairs (#12)
  4. what a re-delivery may change (#21)
- **Some example values appear in only one file.** The final table needs at least 12 rows and could merge both lists: `031200009x`, `7442912`, `76783609419.0`, the 979 prefix, and the duplicate-row and missing-ISBN re-delivery cases.
