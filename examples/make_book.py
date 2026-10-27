"""The smallest useful Lexic book, as in SPEC.md "Making a book".

Run: python3 examples/make_book.py   (writes petit.lexic in the current directory)
"""
import sqlite3, datetime, os

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schema.sql")

if os.path.exists("petit.lexic"):
    os.remove("petit.lexic")
book = sqlite3.connect("petit.lexic")
book.executescript(open(SCHEMA).read())   # the CREATE statements above

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
