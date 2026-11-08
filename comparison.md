# Comparison: my books.db vs. my partner's books.db

**The two databases hold the same data.**

| | Mine (`books.db`) | Partner's (`partner/books.db`) |
|---|---|---|
| Books | 10,014 | 10,014 |
| Books with an ISBN-13 | 8,262 | 8,262 |
| Books with no ISBN at all | 1,752 | 1,752 |

- **Books only in mine:** none
- **Books only in my partner's:** none
- **Books in both with a different value:** none

## How the comparison was done

- **Databases:** mine is `books.db` (sha256 `224dbc38…1632e`). My partner's, Fernando Martinez's, is saved unchanged as `partner/books.db` (sha256 `63601d59…f24ae2`), downloaded from https://github.com/FlightsandGigabytes/language-of-computation-week4-assignment/raw/assignment/books.db.
- **Same book:** rules.md section 5 says two rows are the same book when they have the same `book_id`. Books were matched on `book_id` by value. It is stored as INTEGER in mine and as TEXT in my partner's, so `25` and `"25"` are the same book.
- **Tables and columns:** both databases have one table, `books`, with the same 27 column names in a different order. Each column was matched to the column of the same name.
- **Columns compared (25):** goodreads_book_id, best_book_id, work_id, books_count, isbn_raw, isbn13_raw, isbn10, isbn13, authors, original_publication_year, original_title, title, language_code, average_rating, ratings_count, work_ratings_count, work_text_reviews_count, ratings_1, ratings_2, ratings_3, ratings_4, ratings_5, image_url, small_image_url, last_source_file.
- **Left out:** `last_loaded_at`. It only records when a row was loaded, and rules.md section 8 says it does not count. `book_id` is the matching key, so it isn't compared as a value.
- **Values:** compared as text, so the same value stored as a number in one database and as text in the other counts as equal. An empty value (NULL) matches only another NULL.

## Why our data differs

Our data does not differ. Both databases hold the same 10,014 books, with no book in only one of them and no value that differs in any compared column.

In Module 3 every script followed its own rules, so the same file gave different databases. This time Nando and I worked from one shared rules.md and kept our copies byte-identical, so the same input could only produce the same output. The rules are what prevented differences. The tests and the code only followed what the rules said.

The real risk was questions the rules didn't answer. Each time one came up, we decided it together and added the same line to both copies of rules.md: what "the same database" means when last_loaded_at always differs, which columns count when deciding a re-delivered row has changed, where updated rows and their changed columns go in the log, and where the counts sit in a log entry. If either of us had settled any of those alone in code, our databases or logs could have differed even though our tests passed.

*Written with Claude Code from my own answers, with my professor's permission.*
