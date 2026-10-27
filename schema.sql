-- Lexic book format: the CREATE statements a producer runs.
-- Specification: SPEC.md (canonical copy: https://getlexico.com/format)

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
