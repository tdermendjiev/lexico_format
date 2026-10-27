# The Lexic book format (`.lexic`)

An open file format for books you read in a foreign language with the translation one tap away.
A `.lexic` file is a single SQLite database that holds a book's text, an English translation of every
sentence, the dictionary form and meaning of every word, and the conjugation tables of its verbs.
Everything a reader needs is in the file, so books work offline and outlive any app.

The format is used by [Lexico](https://getlexico.com/), an app for learning French, Spanish, Italian
or German by reading real books. It is free to use: anyone may make Lexic books, and anyone may build
a reader for them.

- **Specification:** [SPEC.md](SPEC.md), also at [getlexico.com/format](https://getlexico.com/format)
- **Schema:** [schema.sql](schema.sql)
- **Example producer:** [examples/make_book.py](examples/make_book.py)
- **Validator:** [tools/check_lexic.py](tools/check_lexic.py)
- **See it in use:** [free classics with English translation](https://getlexico.com/books/), each page
  showing a book's opening the way a Lexic reader displays it, for example
  [Bel-Ami in French](https://getlexico.com/books/bel-ami/) or
  [Kafka's In der Strafkolonie in German](https://getlexico.com/books/in-der-strafkolonie/)

## What is in a file

| Table | Holds |
|----|----|
| `meta` | Title, author, source and target language, format version, sentence and chapter counts |
| `chapters` | The plain text of each chapter, in reading order |
| `sentences` | A character range in its chapter plus its English translation |
| `lemmas` | The book's dictionary: headword, part of speech with gender, meaning |
| `words` | Each word of a sentence as a range inside it, pointing at its lemma, with the verb tense |
| `phrases` | Multi-word expressions such as *tout à coup* or *avoir l'air* (optional) |
| `conjugations` | Full verb paradigms for offline conjugation tables (optional) |
| `epub` | The source EPUB, so a reader can show the original typography (format 1.1) |

Offsets count UTF-16 code units, which is how JavaScript, Swift and Java/Kotlin index strings.

## Quick start

Make the smallest valid book and check it (Python 3.8+, standard library only):

```sh
python3 examples/make_book.py          # writes petit.lexic
python3 tools/check_lexic.py petit.lexic
```

Look inside any Lexic book with the `sqlite3` shell:

```sh
sqlite3 petit.lexic "SELECT key, value FROM meta"
sqlite3 petit.lexic "SELECT s.translation, w.surface_form, l.lemma, l.pos, l.gloss
                     FROM sentences s JOIN words w ON w.sentence_id = s.id
                     JOIN lemmas l ON l.id = w.lemma_id ORDER BY s.global_index, w.char_start"
```

## Building a reader

A reader needs a handful of queries: read `meta`, list `chapters`, slice each chapter's sentences by
their offsets, and on a tap show the sentence's translation and its words joined to `lemmas`. Keep
the reader's own data (progress, flashcards, bookmarks) outside the file, keyed by
`sentences.global_index` and `(lemma, pos)`, so a newer version of the same book keeps working.
The full list is in [SPEC.md, "Building a reader"](SPEC.md#building-a-reader).

## Names

You may call your files Lexic books and give them the `.lexic` extension. "Lexico" is the name of the
app; please do not present a book or a reader as made by the Lexico team.

## Contributing

Found a Lexico book that disagrees with the spec, or a part of the spec that is unclear? Open an issue.
The spec, not any tool, is the reference: a file that disagrees with it is a bug in the file.
