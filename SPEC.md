# The Lexic book format

> This is the specification of the `.lexic` file format, also published at [getlexico.com/format](https://getlexico.com/format). Where the text says "this page", it means this document. The schema is in [`schema.sql`](schema.sql), the example below is runnable as [`examples/make_book.py`](examples/make_book.py), and the checklist is automated in [`tools/check_lexic.py`](tools/check_lexic.py).

*An open file format for books you can read with a translation one tap away. Anyone may make Lexic books, and anyone may build a reader for them.*

## Why we are publishing this

A Lexico book is more than a text. Every sentence carries its English translation, every word its dictionary form and meaning, every verb its conjugation table. All of it sits in one file on your device, so a book works on a plane, in a tunnel, and in twenty years.

We think that file should belong to the reader, not to us. So the format is documented here in full, and it is free to use:

- **Your books are yours.** A Lexic book is a plain SQLite database. You can open it with any SQLite tool, copy it, keep it, and read it with software that is not ours.
- **Anyone can make books.** A teacher with a class reader, a publisher with a catalogue, a student with a favourite novel we will never get round to: the format is simple enough to produce with a script, and this page tells you exactly what to write.
- **Anyone can build a reader.** We make Lexico for iPhone, iPad and the web. If you want one for Android, a Kindle-like device or your terminal, the file has everything a reader needs and nothing it has to ask our servers for.
- **It will outlive us.** SQLite is a stable, universal container; the schema below is eight tables and no clever encodings.

The files Lexico publishes come out of our own indexing tool, but this page, not the tool, is the specification. If you find a Lexico book that disagrees with this page, that is a bug in the book.

You may call your files Lexic books and give them the `.lexic` extension. "Lexico" is the name of our app; please do not present a book or a reader as made by us.

## The format in one paragraph

A `.lexic` file is a SQLite 3 database. The text of the book is stored as **chapters** of plain text. Each **sentence** is a character range in its chapter plus an English translation. Each **word** of a sentence is a character range inside the sentence, pointing at a **lemma** (dictionary entry: headword, part of speech, meaning). **Phrases** mark multi-word expressions the same way. Verbs may bring their **conjugation** tables along. Format 1.1 also embeds the original **EPUB**, so a reader can show the publisher's typography while tapping sentences that were indexed from the plain text.

## Container

- A single SQLite 3 database file. Finish it with `PRAGMA journal_mode = DELETE` and `VACUUM`, so there are no `-wal`/`-shm` sidecar files to carry around.
- File extension `.lexic`. On Apple platforms the type identifier is `com.azbouki.lexic.book`, conforming to `public.data` and `public.database`.
- Text is UTF-8, as SQLite stores it. Character offsets, however, count **UTF-16 code units** (see Offsets).
- Nothing in the file is compressed or encrypted. A novel of 120,000 words is 5–10 MB without an EPUB, a few MB more with one.

## Versions

`meta.format_version` says which version the file follows. A reader refuses a version it does not know, with a message like "this book was made with a newer version".

| Version | What it adds |
|----|----|
| `1.0` | Plain-text chapters, sentences, lemmas, words. Readers render the chapter text themselves. |
| `1.1` | The source EPUB embedded in the `epub` table; `chapters.spine_index` and `chapters.spine_href` say which EPUB document each chapter came from. Readers may render the EPUB and anchor the indexed sentences in it. |

Both versions are current. A book made from plain text is a 1.0 file; a book made from an EPUB is normally 1.1. The `phrases` and `conjugations` tables and the `words.context_gloss` column exist in both versions; a reader must work without them.

**Compatibility rule.** Readers ignore tables and columns they do not know, and treat a missing optional table as empty. So a producer may add its own tables or columns without changing the version. The version number changes only when a reader could no longer make sense of a file without knowing about the change.

## Schema

The statements a producer runs, in full. Column notes follow each table.

```sql
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE chapters (
  id           INTEGER PRIMARY KEY,
  order_index  INTEGER NOT NULL,
  title        TEXT NOT NULL,
  content      TEXT NOT NULL,
  spine_index  INTEGER,        -- 1.1, or NULL
  spine_href   TEXT            -- 1.1, or NULL
);
CREATE INDEX idx_chapters_order ON chapters(order_index);

CREATE TABLE sentences (
  id           INTEGER PRIMARY KEY,
  chapter_id   INTEGER NOT NULL REFERENCES chapters(id),
  order_index  INTEGER NOT NULL,
  global_index INTEGER NOT NULL,
  char_start   INTEGER NOT NULL,
  char_end     INTEGER NOT NULL,
  translation  TEXT NOT NULL
);
CREATE INDEX idx_sentences_chapter ON sentences(chapter_id, order_index);
CREATE INDEX idx_sentences_global ON sentences(global_index);

CREATE TABLE lemmas (
  id       INTEGER PRIMARY KEY,
  lemma    TEXT NOT NULL,
  pos      TEXT NOT NULL,
  gloss    TEXT NOT NULL,
  is_verb  INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX idx_lemmas_unique ON lemmas(lemma, pos);

CREATE TABLE words (
  id            INTEGER PRIMARY KEY,
  sentence_id   INTEGER NOT NULL REFERENCES sentences(id),
  lemma_id      INTEGER NOT NULL REFERENCES lemmas(id),
  surface_form  TEXT NOT NULL,
  char_start    INTEGER NOT NULL,
  char_end      INTEGER NOT NULL,
  verb_tense    TEXT,
  context_gloss TEXT
);
CREATE INDEX idx_words_sentence ON words(sentence_id);

CREATE TABLE phrases (                 -- optional
  id           INTEGER PRIMARY KEY,
  sentence_id  INTEGER NOT NULL REFERENCES sentences(id),
  lemma_id     INTEGER NOT NULL REFERENCES lemmas(id),
  surface_form TEXT NOT NULL,
  char_start   INTEGER NOT NULL,
  char_end     INTEGER NOT NULL
);
CREATE INDEX idx_phrases_sentence ON phrases(sentence_id);

CREATE TABLE conjugations (            -- optional
  id     INTEGER PRIMARY KEY,
  lemma  TEXT NOT NULL,
  mood   TEXT NOT NULL,
  tense  TEXT NOT NULL,
  person TEXT,
  form   TEXT NOT NULL,
  lang   TEXT
);
CREATE INDEX idx_book_conjugations_lemma ON conjugations(lemma);

CREATE TABLE epub (                    -- 1.1 only
  id   INTEGER PRIMARY KEY CHECK (id = 1),
  data BLOB NOT NULL
);
```

### meta

Key–value pairs, all values stored as text.

| Key | Required | Meaning |
|----|----|----|
| `format_version` | yes | `1.0` or `1.1`. |
| `title` | yes | The book's title. |
| `author` | yes | The author; may be empty. |
| `source_lang` | yes | Language of the text: `fr`, `es`, `it` or `de`. Lexico shows books in the languages it knows; other codes are allowed in the format and reserved for readers that support them. |
| `target_lang` | yes | Language of the translations and glosses. Lexico reads `en` only. |
| `total_sentences` | yes | Sentences in the whole book, as an integer. |
| `indexed_sentences` | no | Sentences in this file. Equal to `total_sentences` unless the file is partial (see Partial books). |
| `total_chapters`, `indexed_chapters` | no | Likewise for chapters. A reader treats `indexed_chapters < total_chapters` as "more chapters are coming". |
| `has_epub` | no | `1` when the `epub` table holds the source EPUB, `0` otherwise. |
| `processed_at` | no | When the file was made, ISO 8601. |
| `cover_color_hex` | no | A colour such as `#2A3B4C` for a placeholder cover. Lexico no longer uses it; harmless to set. |

### chapters

One row per reading unit, in reading order. `content` is the full plain text of the chapter: paragraphs separated by blank lines, no markup. `id` should be stable across versions of the same book: we use `order_index + 1`, so a later file with more chapters keeps every id and a reader's saved position still resolves.

`spine_index` and `spine_href` are set in 1.1 files for chapters that came from an EPUB document: the document's position in the EPUB's spine, and its path inside the EPUB archive (as in `OEBPS/chapter-3.xhtml`). Either may be NULL; a reader then shows the chapter's plain text.

### sentences

One row per sentence, in reading order. `char_start`/`char_end` cut the sentence out of its chapter's `content` (`end` exclusive). `order_index` counts from 0 within the chapter; `global_index` counts from 0 across the whole book and is what readers use for progress, bookmarks and flashcards, so it must be unique and should never change between versions of the same book. `translation` is the English rendering of the sentence; an empty string is allowed when there is none.

A sentence need not be a grammatical sentence: a heading, a line of verse or a long paragraph can be one. Keep each one short enough to translate as a unit. Everything in `content` that is not covered by a sentence is simply not tappable.

### lemmas

The book's dictionary: one row per (headword, part of speech), shared by every word that belongs to it.

| Column | Meaning |
|----|----|
| `lemma` | The dictionary form: infinitive for verbs, singular for nouns, masculine singular for adjectives. Lower case except proper nouns. |
| `pos` | One of `verb`, `noun_m`, `noun_f`, `noun_n`, `adjective`, `adverb`, `pronoun`, `preposition`, `conjunction`, `determiner`, `other`, `phrase`. The noun codes carry the gender (`noun_n` is for German neuters). `phrase` is used only by rows that `phrases` point at. |
| `gloss` | The meaning in the target language, dictionary style: `to carry`, `girl`, `pretty`. One to a few words. |
| `is_verb` | `1` for verbs, else `0`. Redundant with `pos = 'verb'`, kept for fast queries. |

### words

One row per word of a sentence, in reading order, so that reading the words of a sentence in `char_start` order reconstructs its text minus punctuation. **Punctuation is never a word**: commas, full stops, dashes and quotation marks are not rows and do not belong to a word's `surface_form`. The apostrophe of an elided word stays (`l'`, `qu'`, `c'était`), and so do hyphens inside a word.

| Column | Meaning |
|----|----|
| `surface_form` | The word exactly as it appears in the sentence. |
| `char_start`, `char_end` | Offsets **within the sentence text**, that is relative to the sentence's own `char_start` in the chapter. `sentence_text[char_start:char_end]` must equal `surface_form`. |
| `lemma_id` | The dictionary entry. |
| `verb_tense` | For verbs, the tense label of this occurrence (see Verb tenses); NULL otherwise. |
| `context_gloss` | What the word means in this sentence (`was carrying`), when it differs usefully from the lemma's dictionary gloss (`to carry`). NULL to fall back to the lemma's gloss. |

### phrases

Multi-word expressions whose meaning is not the sum of their words: `tout à coup`, `se mettre à`, `avoir l'air`. They sit on top of the words: every word inside a phrase is still a `words` row of its own. A phrase's `lemma_id` points at a `lemmas` row with `pos = 'phrase'`, whose `lemma` is the expression's dictionary form and whose `gloss` its meaning. Offsets are relative to the sentence text, like words, and must match `surface_form`. A phrase is one contiguous span; discontinuous expressions (`ne … que`) are not phrases.

### conjugations

The full paradigm of each verb in the book, so a reader can show a conjugation table offline. One row per form.

| Column | Meaning |
|----|----|
| `lemma` | The infinitive, as in `lemmas.lemma` (`parler`, `hablar`, `parlare`, `machen`). |
| `mood`, `tense` | Canonical keys, listed under Verb tenses. |
| `person` | The pronoun label of the form, or NULL for forms without a person (participles, infinitives, gerunds). |
| `form` | The conjugated form, with its auxiliary for compound tenses: `ai parlé`, `avons parlé`. |
| `lang` | The language of the paradigm (`fr`, …), because `dire` is both French and Italian. May be NULL in old files. |

The person labels, in paradigm order:

| Language | Persons |
|----|----|
| French | `je`, `tu`, `il/elle`, `nous`, `vous`, `ils/elles` (imperative: `tu`, `nous`, `vous`) |
| Spanish | `yo`, `tú`, `él/ella`, `nosotros`, `vosotros`, `ellos/ellas` (imperative: no `yo`) |
| Italian | `io`, `tu`, `lui/lei`, `noi`, `voi`, `loro` (imperative: no `io`) |
| German | `ich`, `du`, `er/sie/es`, `wir`, `ihr`, `sie/Sie` (imperative: `du`, `ihr`) |

When a verb is tapped, a reader looks its lemma up first as written, then as the bare infinitive (`s'appeler` → `appeler`, `se levantar` → `levantar`, `sich erinnern` → `erinnern`), and highlights the section whose `mood + " " + tense` equals the word's `verb_tense`.

### epub

Format 1.1 only: the complete source EPUB, byte for byte, in the single row with `id = 1`. See Format 1.1.

## Offsets

All character offsets count **UTF-16 code units**, not bytes and not Unicode scalars. This is the native indexing of Swift's `NSString`, of JavaScript strings and of Java/Kotlin strings, so readers on every platform we know of can slice without converting. For text made only of characters in the Basic Multilingual Plane (every European language, including all accented letters, quotation marks and dashes) UTF-16 units and code points coincide; only emoji and a few rare symbols take two units. Python's `len()` counts code points, so a Python producer should check for astral characters or convert (`len(s.encode("utf-16-le")) // 2`).

- `sentences.char_start`/`char_end` index into `chapters.content`.
- `words.*` and `phrases.*` offsets index into the sentence's text, i.e. `content[sentence.char_start:sentence.char_end]`.
- Every range must reproduce its text exactly: `content[s.char_start:s.char_end]` is the sentence; `sentence_text[w.char_start:w.char_end] == w.surface_form`. Readers trust this; a producer should verify it before writing the file and drop the word list of any sentence that fails rather than ship wrong offsets.
- Chapter text may contain line breaks inside a sentence (an EPUB's soft wraps). Readers fold a single `\n` to a space and keep a blank line as a paragraph break when displaying a sentence.

## Verb tenses

`words.verb_tense` and the `conjugations` keys use the same canonical form, so a tap can find its row in the table: **mood, a space, tense**, all lower case; the mood without accents, the tense with its accents; hyphens inside a tense written as spaces. Forms without a tense repeat the mood as the tense. These are the keys in use:

**French** (moods `indicatif`, `subjonctif`, `conditionnel`, `imperatif`, `participe`, `infinitif`, `gerondif`): `indicatif présent`, `indicatif imparfait`, `indicatif passé simple`, `indicatif futur simple`, `indicatif passé composé`, `indicatif plus que parfait`, `indicatif passé antérieur`, `indicatif futur antérieur`, `subjonctif présent`, `subjonctif imparfait`, `subjonctif passé`, `subjonctif plus que parfait`, `conditionnel présent`, `conditionnel passé`, `imperatif présent`, `imperatif passé`, `participe présent`, `participe passé`, `infinitif présent`, `gerondif`.

**Spanish** (`indicativo`, `subjuntivo`, `condicional`, `imperativo`, `participio`, `infinitivo`, `gerundio`): `indicativo presente`, `indicativo pretérito imperfecto`, `indicativo pretérito perfecto simple`, `indicativo futuro`, `indicativo pretérito perfecto compuesto`, `indicativo pretérito pluscuamperfecto`, `indicativo pretérito anterior`, `indicativo futuro perfecto`, `subjuntivo presente`, `subjuntivo pretérito imperfecto`, `subjuntivo pretérito perfecto`, `subjuntivo pretérito pluscuamperfecto`, `subjuntivo futuro`, `subjuntivo futuro perfecto`, `condicional presente`, `condicional perfecto`, `imperativo afirmativo`, `imperativo negativo`, `participio participio`, `infinitivo infinitivo`, `gerundio gerundio`. In the conjugation table the two forms of the imperfect and pluperfect subjunctive (-ra/-se) are separate sections, `subjuntivo pretérito imperfecto 1` and `… 2`; a word labelled without the number highlights both.

**Italian** (`indicativo`, `congiuntivo`, `condizionale`, `imperativo`, `participio`, `infinito`, `gerundio`): `indicativo presente`, `indicativo imperfetto`, `indicativo passato remoto`, `indicativo futuro`, `indicativo passato prossimo`, `indicativo trapassato prossimo`, `indicativo trapassato remoto`, `indicativo futuro anteriore`, `congiuntivo presente`, `congiuntivo imperfetto`, `congiuntivo passato`, `congiuntivo trapassato`, `condizionale presente`, `condizionale passato`, `imperativo affermativo`, `imperativo negativo`, `participio presente`, `participio passato`, `infinito infinito`, `gerundio gerundio`.

**German** (`indikativ`, `konjunktiv-i`, `konjunktiv-ii`, `imperativ`, `infinitiv`, `partizip`): `indikativ präsens`, `indikativ präteritum`, `indikativ perfekt`, `indikativ plusquamperfekt`, `indikativ futur i`, `indikativ futur ii`, `konjunktiv-i präsens`, `konjunktiv-i perfekt`, `konjunktiv-i futur i`, `konjunktiv-i futur ii`, `konjunktiv-ii präteritum`, `konjunktiv-ii plusquamperfekt`, `konjunktiv-ii futur i`, `konjunktiv-ii futur ii`, `imperativ präsens`, `infinitiv präsens`, `partizip i`, `partizip ii`. The mood is one token (`konjunktiv-ii`, with the hyphen), because readers split the key at its first space. In a compound tense (`hatte gemacht`) the main verb carries the tense label and the auxiliary its own simple tense.

## Format 1.1: the embedded EPUB

A 1.0 reader shows the chapter's plain text, which loses the publisher's headings, italics and images. Format 1.1 keeps the EPUB inside the file so a reader can display the original pages and still make every indexed sentence tappable.

- `epub.data` is the EPUB file as uploaded, unchanged. `meta.has_epub` is `1`.
- For each chapter that came from one EPUB document, `spine_href` is that document's path inside the archive and `spine_index` its position in the spine, counting from 0. A chapter may cover a whole spine document, never part of one, and one document may yield one chapter only.
- `content` must be the plain text of that document: the text of its elements in order, paragraphs separated by blank lines, no markup. Boilerplate the producer strips (such as Project Gutenberg's headers) must stay out of the sentences too.

A reader renders the EPUB document and then **finds each sentence by its text**: it walks the sentences in order and searches the rendered text for the sentence's words, ignoring differences in whitespace and line breaks. When the same sentence occurs several times, `char_start` decides which occurrence is meant. So a producer need not reproduce the exact whitespace of the document, but the words and punctuation of a sentence must occur in the document as they stand in `content`. A sentence that cannot be found is displayed as the publisher wrote it but cannot be tapped.

A 1.1 file is also a valid 1.0 file: everything a 1.0 reader needs is still there. A reader that cannot show EPUBs may ignore the `epub` table and the spine columns.

## Partial books

A long book may be published a few chapters at a time. A partial file holds the **leading** chapters of the book, with their final ids and `global_index` values, and says so in `meta`: `total_chapters`/`total_sentences` describe the whole book, `indexed_chapters`/`indexed_sentences` this file. A reader shows "more chapters coming" at the end instead of marking the book finished. Never publish a non-leading subset: a reader must never see chapter 4 before chapter 3 exists, and ids must not move when the next version arrives.

## Making a book

The smallest useful book is a title, one chapter, its sentences with translations, and a word list. Here it is in Python, with no dependencies beyond the standard library:

```python
import sqlite3, datetime

book = sqlite3.connect("petit.lexic")
book.executescript(open("schema.sql").read())   # the CREATE statements above

content = "Il pleuvait. Elle attendait le train."
sentences = [
    ("Il pleuvait.", "It was raining.",
     [("Il", "il", "pronoun", "he/it"), ("pleuvait", "pleuvoir", "verb", "to rain")]),
    ("Elle attendait le train.", "She was waiting for the train.",
     [("Elle", "elle", "pronoun", "she"), ("attendait", "attendre", "verb", "to wait for"),
      ("le", "le", "determiner", "the"), ("train", "train", "noun_m", "train")]),
]
tenses = {"pleuvait": "indicatif imparfait", "attendait": "indicatif imparfait"}

book.executemany("INSERT INTO meta VALUES (?, ?)", [
    ("format_version", "1.0"), ("title", "Un petit livre"), ("author", ""),
    ("source_lang", "fr"), ("target_lang", "en"),
    ("total_sentences", str(len(sentences))), ("indexed_sentences", str(len(sentences))),
    ("total_chapters", "1"), ("indexed_chapters", "1"), ("has_epub", "0"),
    ("processed_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
])
book.execute("INSERT INTO chapters (id, order_index, title, content) VALUES (1, 0, ?, ?)",
             ("Chapitre 1", content))

cursor = 0
for index, (text, translation, words) in enumerate(sentences):
    start = content.index(text, cursor)                 # offsets into the chapter
    end = start + len(text)
    cursor = end
    sentence_id = book.execute(
        "INSERT INTO sentences (chapter_id, order_index, global_index, char_start, char_end, translation)"
        " VALUES (1, ?, ?, ?, ?, ?)", (index, index, start, end, translation)).lastrowid
    at = 0
    for surface, lemma, pos, gloss in words:
        book.execute("INSERT OR IGNORE INTO lemmas (lemma, pos, gloss, is_verb) VALUES (?, ?, ?, ?)",
                     (lemma, pos, gloss, pos == "verb"))
        lemma_id = book.execute("SELECT id FROM lemmas WHERE lemma = ? AND pos = ?", (lemma, pos)).fetchone()[0]
        w_start = text.index(surface, at)               # offsets into the sentence
        at = w_start + len(surface)
        book.execute("INSERT INTO words (sentence_id, lemma_id, surface_form, char_start, char_end, verb_tense)"
                     " VALUES (?, ?, ?, ?, ?, ?)",
                     (sentence_id, lemma_id, surface, w_start, at, tenses.get(surface)))

book.commit()
book.execute("PRAGMA journal_mode = DELETE")
book.execute("VACUUM")
book.close()
```

Where the translations and lemmas come from is up to you: a dictionary, a language model, a teacher's hand. Our own books are produced by an indexing tool that segments the text, asks a language model for the translation and the analysis of every sentence, verifies every offset against the source, corrects headwords against Wiktionary, and copies in the verb paradigms.

Before you ship a book, check:

- `meta` has `format_version`, `title`, `author`, `source_lang`, `target_lang`, `total_sentences`.
- Every sentence's range reproduces its text; every word's and phrase's range reproduces its `surface_form` within the sentence.
- `global_index` is unique, starts at 0 and follows reading order; `order_index` restarts at 0 in each chapter.
- No `words` row is punctuation; no `surface_form` begins or ends with punctuation other than an apostrophe or a hyphen.
- Every `words.lemma_id` and `phrases.lemma_id` exists in `lemmas`; phrases point at `pos = 'phrase'` rows.
- `verb_tense` values are from the lists above, or NULL.
- The file opens after `PRAGMA journal_mode = DELETE` with no sidecar files.

## Building a reader

Everything a reader does is a handful of queries:

- **Open:** read `meta`; refuse a `format_version` you do not support.
- **Table of contents:** `SELECT id, title FROM chapters ORDER BY order_index`.
- **A chapter:** its `content`, and `SELECT * FROM sentences WHERE chapter_id = ? ORDER BY order_index`; slice each sentence out with its offsets (UTF-16).
- **A tap on a sentence:** show `translation`; then `SELECT w.*, l.lemma, l.pos, l.gloss FROM words w JOIN lemmas l ON l.id = w.lemma_id WHERE w.sentence_id = ? ORDER BY w.char_start` for the words, and the same from `phrases` if the table exists. Prefer `context_gloss` over the lemma's `gloss` when it is set.
- **A tap on a verb:** `SELECT * FROM conjugations WHERE lemma = ? AND (lang = ? OR lang IS NULL) ORDER BY id`, trying the lemma as written and then its bare infinitive; group rows by `mood + " " + tense` and highlight the group matching the word's `verb_tense` (treat a key ending in ` 1` or ` 2` as matching the key without it).
- **Progress:** the highest `global_index` reached over `total_sentences`.
- **Flashcards:** a lemma is `(lemma, pos)`; `gloss` is its back side; `words` give the example sentences through `sentence_id`.

Keep the reader's own data (progress, cards, bookmarks) outside the file, keyed by `global_index` and `(lemma, pos)`, so a new version of the same book keeps working.

## Changes to this page

- **1.1** adds the `epub` table and the `spine_index`/`spine_href` columns.
- Since 1.0 the `phrases` table, the `conjugations` table (and its `lang` column) and `words.context_gloss` were added without a version change, under the compatibility rule above.
