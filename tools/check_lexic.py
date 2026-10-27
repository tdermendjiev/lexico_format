#!/usr/bin/env python3
"""Check a .lexic file against the Lexic book format (SPEC.md, "Before you ship a book").

Usage: python3 tools/check_lexic.py book.lexic [more.lexic ...]
Exit status 0 when every file passes, 1 otherwise. Standard library only, Python 3.8+.
"""
import io
import sqlite3
import sys
import unicodedata
import zipfile

REQUIRED_META = ["format_version", "title", "author", "source_lang", "target_lang", "total_sentences"]
VERSIONS = {"1.0", "1.1"}
POS = {"verb", "noun_m", "noun_f", "noun_n", "adjective", "adverb", "pronoun", "preposition",
       "conjunction", "determiner", "other", "phrase"}
TENSES = {
    "fr": """indicatif présent|indicatif imparfait|indicatif passé simple|indicatif futur simple|indicatif passé composé|
indicatif plus que parfait|indicatif passé antérieur|indicatif futur antérieur|subjonctif présent|subjonctif imparfait|
subjonctif passé|subjonctif plus que parfait|conditionnel présent|conditionnel passé|imperatif présent|imperatif passé|
participe présent|participe passé|infinitif présent|gerondif""",
    "es": """indicativo presente|indicativo pretérito imperfecto|indicativo pretérito perfecto simple|indicativo futuro|
indicativo pretérito perfecto compuesto|indicativo pretérito pluscuamperfecto|indicativo pretérito anterior|
indicativo futuro perfecto|subjuntivo presente|subjuntivo pretérito imperfecto|subjuntivo pretérito perfecto|
subjuntivo pretérito pluscuamperfecto|subjuntivo futuro|subjuntivo futuro perfecto|condicional presente|
condicional perfecto|imperativo afirmativo|imperativo negativo|participio participio|infinitivo infinitivo|gerundio gerundio""",
    "it": """indicativo presente|indicativo imperfetto|indicativo passato remoto|indicativo futuro|indicativo passato prossimo|
indicativo trapassato prossimo|indicativo trapassato remoto|indicativo futuro anteriore|congiuntivo presente|
congiuntivo imperfetto|congiuntivo passato|congiuntivo trapassato|condizionale presente|condizionale passato|
imperativo affermativo|imperativo negativo|participio presente|participio passato|infinito infinito|gerundio gerundio""",
    "de": """indikativ präsens|indikativ präteritum|indikativ perfekt|indikativ plusquamperfekt|indikativ futur i|
indikativ futur ii|konjunktiv-i präsens|konjunktiv-i perfekt|konjunktiv-i futur i|konjunktiv-i futur ii|
konjunktiv-ii präteritum|konjunktiv-ii plusquamperfekt|konjunktiv-ii futur i|konjunktiv-ii futur ii|imperativ präsens|
infinitiv präsens|partizip i|partizip ii""",
}
TENSES = {lang: {t.strip() for t in s.replace("\n", "").split("|")} for lang, s in TENSES.items()}
KEEP_AT_EDGE = {"'", "’", "-", "‐", "‑"}  # apostrophes and hyphens may stay

MAX_REPORTS = 10  # per kind of problem


def u16_slice(text, start, end):
    """Slice by UTF-16 code units, as the spec requires."""
    raw = text.encode("utf-16-le")
    if start < 0 or end > len(raw) // 2 or start > end:
        return None
    return raw[2 * start:2 * end].decode("utf-16-le", errors="replace")


def is_punct(ch):
    return unicodedata.category(ch)[0] == "P" and ch not in KEEP_AT_EDGE


class Report:
    def __init__(self):
        self.errors, self.warnings, self.counts = [], [], {}

    def _add(self, bucket, kind, msg):
        self.counts[kind] = self.counts.get(kind, 0) + 1
        if self.counts[kind] <= MAX_REPORTS:
            bucket.append(msg)
        elif self.counts[kind] == MAX_REPORTS + 1:
            bucket.append(f"... more '{kind}' problems not shown")

    def error(self, kind, msg):
        self._add(self.errors, kind, msg)

    def warn(self, kind, msg):
        self._add(self.warnings, kind, msg)


def tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def check(path):
    r = Report()
    with open(path, "rb") as f:
        header = f.read(100)
    if not header.startswith(b"SQLite format 3\x00"):
        r.error("container", "not a SQLite 3 database")
        return r
    if header[18] == 2 or header[19] == 2:
        r.error("container", "database is in WAL mode; finish with PRAGMA journal_mode = DELETE and VACUUM")

    db = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    have = tables(db)
    for t in ["meta", "chapters", "sentences", "lemmas", "words"]:
        if t not in have:
            r.error("schema", f"missing table {t}")
    if r.errors:
        return r

    meta = dict(db.execute("SELECT key, value FROM meta"))
    for key in REQUIRED_META:
        if key not in meta:
            r.error("meta", f"meta.{key} is missing")
    version = meta.get("format_version")
    if version is not None and version not in VERSIONS:
        r.error("meta", f"unknown format_version {version!r} (expected 1.0 or 1.1)")
    lang = meta.get("source_lang", "")

    # Chapters and sentences
    chapters = {cid: (order, content) for cid, order, content in
                db.execute("SELECT id, order_index, content FROM chapters")}
    rows = db.execute("""SELECT s.id, s.chapter_id, s.order_index, s.global_index, s.char_start, s.char_end
                         FROM sentences s JOIN chapters c ON c.id = s.chapter_id
                         ORDER BY c.order_index, s.order_index""").fetchall()
    orphan = db.execute("SELECT COUNT(*) FROM sentences WHERE chapter_id NOT IN (SELECT id FROM chapters)").fetchone()[0]
    if orphan:
        r.error("sentences", f"{orphan} sentences point at a missing chapter")

    sentence_text, seen_global, expected_order = {}, set(), {}
    last_global = -1
    for sid, cid, order, gidx, start, end in rows:
        text = u16_slice(chapters[cid][1], start, end)
        if text is None or start == end:
            r.error("sentence range", f"sentence {sid}: range {start}-{end} is outside its chapter or empty")
            continue
        sentence_text[sid] = text
        want = expected_order.get(cid, 0)
        if order != want:
            r.error("order_index", f"sentence {sid}: order_index {order}, expected {want} (restarts at 0 per chapter)")
        expected_order[cid] = order + 1
        if gidx in seen_global:
            r.error("global_index", f"sentence {sid}: global_index {gidx} is not unique")
        if gidx <= last_global:
            r.error("global_index", f"sentence {sid}: global_index {gidx} does not follow reading order")
        seen_global.add(gidx)
        last_global = max(last_global, gidx)
    if rows and min(seen_global) != 0:
        r.error("global_index", "global_index does not start at 0")

    total = meta.get("total_sentences")
    indexed = meta.get("indexed_sentences", total)
    if indexed is not None and indexed.isdigit() and int(indexed) != len(rows):
        r.warn("meta", f"meta says {indexed} sentences in this file, found {len(rows)}")
    if total and indexed and total.isdigit() and indexed.isdigit() and int(indexed) > int(total):
        r.error("meta", "indexed_sentences is larger than total_sentences")

    # Lemmas
    lemmas = {lid: (lemma, pos) for lid, lemma, pos in db.execute("SELECT id, lemma, pos FROM lemmas")}
    for lid, (lemma, pos) in lemmas.items():
        if pos not in POS:
            r.error("lemma pos", f"lemma {lid} ({lemma}): unknown pos {pos!r}")

    # Words and phrases
    def spans(table, phrase):
        cols = "id, sentence_id, lemma_id, surface_form, char_start, char_end"
        cols += ", NULL" if phrase else ", verb_tense"
        for wid, sid, lid, surface, start, end, tense in db.execute(f"SELECT {cols} FROM {table}"):
            where = f"{table[:-1]} {wid} ({surface!r})"
            if sid not in sentence_text:
                r.error(f"{table} sentence", f"{where}: sentence {sid} is missing or broken")
                continue
            if u16_slice(sentence_text[sid], start, end) != surface:
                r.error(f"{table} range", f"{where}: offsets {start}-{end} do not reproduce surface_form")
            if lid not in lemmas:
                r.error(f"{table} lemma", f"{where}: lemma_id {lid} does not exist")
            elif phrase and lemmas[lid][1] != "phrase":
                r.error("phrase lemma", f"{where}: points at a lemma with pos {lemmas[lid][1]!r}, not 'phrase'")
            if not phrase:
                if surface and (is_punct(surface[0]) or is_punct(surface[-1])):
                    r.error("punctuation", f"{where}: punctuation is never part of a word")
                if tense is not None and lang in TENSES:
                    key = tense[:-2] if tense.endswith((" 1", " 2")) else tense
                    if key not in TENSES[lang]:
                        r.error("verb_tense", f"{where}: unknown verb_tense {tense!r}")
    spans("words", False)
    if "phrases" in have:
        spans("phrases", True)

    # Format 1.1: embedded EPUB
    if meta.get("has_epub") == "1" or version == "1.1":
        if "epub" not in have or not db.execute("SELECT 1 FROM epub WHERE id = 1").fetchone():
            r.error("epub", "has_epub / format 1.1 but the epub table has no row with id = 1")
        else:
            data = db.execute("SELECT data FROM epub WHERE id = 1").fetchone()[0]
            try:
                names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
            except zipfile.BadZipFile:
                r.error("epub", "epub.data is not a valid EPUB (zip) archive")
                names = None
            if names is not None:
                for cid, href in db.execute("SELECT id, spine_href FROM chapters WHERE spine_href IS NOT NULL"):
                    if href not in names:
                        r.error("spine_href", f"chapter {cid}: spine_href {href!r} is not in the EPUB")
    db.close()
    return r


def main(paths):
    if not paths:
        print(__doc__.strip())
        return 2
    failed = False
    for path in paths:
        try:
            r = check(path)
        except (OSError, sqlite3.DatabaseError) as e:
            print(f"{path}: cannot read: {e}")
            failed = True
            continue
        status = "FAIL" if r.errors else "ok"
        print(f"{path}: {status} ({len(r.errors)} errors, {len(r.warnings)} warnings)")
        for m in r.errors:
            print(f"  error: {m}")
        for m in r.warnings:
            print(f"  warning: {m}")
        failed |= bool(r.errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
