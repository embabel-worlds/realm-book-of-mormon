"""
Build the realm's reference data from its published source.

The stored graph is BomScripture → BomBook → BomChapter → BomVerse. The Book of Mormon was received in
English, so a verse carries one text, `text`, and `original` is left empty, as the scripture
vocabulary says it is where the scripture's own language is English.

Source, downloaded into data/source/ on first run:
  bcbooks/scriptures-json (github.com/bcbooks/scriptures-json), `book-of-mormon.json` — the verse text
  with the 2013 edition's adjustments, public domain. It carries the headings printed in the text
  since 1830 (a book's, and fifteen chapters'), and deliberately leaves out the chapter summaries,
  footnotes and introduction, which are under copyright. Nothing here adds them back.

QUOTATION. The Book of Mormon quotes the Bible at length, in the King James's words — twenty-one
chapters of Isaiah, the Sermon on the Mount, Malachi 3 and 4. Each BomVerse records in `kjvRefs` the
King James verse it quotes, and rules/corresponds.yml draws CORRESPONDS_TO from it when realm-bible is
installed. QUOTED below names, for each chapter that quotes, the King James chapters it quotes FROM;
which verse quotes which is not hand-written but FOUND: each verse is paired with the verse in those
chapters it reads most alike, and kept only when the likeness clears a threshold — so a verse of
Christ's own words to the Nephites set inside the Sermon (3 Nephi 12:1-2) is paired with nothing. The
King James text is read from realm-bible's reference data, which must sit beside this realm.

Run from the realm root:  python scripts/build_reference.py
"""

import json
import math
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "source"
REFERENCE = ROOT / "reference"
BIBLE = ROOT.parent / "realm-bible" / "reference"
URL = "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/book-of-mormon.json"

VERSES = 6604
CHAPTERS = 239

QUOTED = {
    "1 Nephi 20": ["Isaiah 48"],
    "1 Nephi 21": ["Isaiah 49"],
    "1 Nephi 22": ["Isaiah 49"],
    "2 Nephi 6": ["Isaiah 49"],
    "2 Nephi 7": ["Isaiah 50"],
    "2 Nephi 8": ["Isaiah 51", "Isaiah 52"],
    **{f"2 Nephi {n}": [f"Isaiah {n - 10}"] for n in range(12, 25)},
    "2 Nephi 26": ["Isaiah 29"],
    "2 Nephi 27": ["Isaiah 29"],
    "2 Nephi 30": ["Isaiah 11"],
    "Mosiah 12": ["Isaiah 52"],
    "Mosiah 14": ["Isaiah 53"],
    "Mosiah 15": ["Isaiah 52"],
    "3 Nephi 12": ["Matthew 5"],
    "3 Nephi 13": ["Matthew 6"],
    "3 Nephi 14": ["Matthew 7"],
    "3 Nephi 16": ["Isaiah 52"],
    "3 Nephi 20": ["Isaiah 52", "Micah 4", "Micah 5", "Acts 3", "Deuteronomy 18"],
    "3 Nephi 21": ["Micah 5", "Isaiah 52"],
    "3 Nephi 22": ["Isaiah 54"],
    "3 Nephi 24": ["Malachi 3"],
    "3 Nephi 25": ["Malachi 4"],
    "Mormon 9": ["Mark 16"],
    "Moroni 7": ["1 Corinthians 13"],
}
# realm-bible's verse files the chapters above are read from.
BIBLE_FILES = ["bible-03-verses-05-Deut.yml", "bible-03-verses-23-Isa.yml", "bible-03-verses-33-Mic.yml",
               "bible-03-verses-39-Mal.yml", "bible-03-verses-40-Matt.yml", "bible-03-verses-41-Mark.yml",
               "bible-03-verses-44-Acts.yml", "bible-03-verses-46-1Cor.yml"]

# Likeness is shared words weighted by rarity, and on this text it falls in two clusters with a band
# between, measured on the build (it prints the pairs nearest each line, so a change of source can be
# judged). At 0.4 and above a verse QUOTES — near-verbatim, the King James's words with the Book of
# Mormon's additions. Below 0.25 it shares nothing but the chapter's vocabulary ("and it shall come
# to pass"). Between, it ALLUDES: Mosiah 15:14-18 turning Isaiah 52:7's "how beautiful upon the
# mountains" into a sermon, Moroni 7:45 on charity in 1 Corinthians 13:4. An allusion is found by
# words alone, so it is a candidate for a reader, not a finding; the two are kept apart for that.
QUOTES = 0.4
ALLUDES = 0.26


def fetch() -> dict:
    SOURCE.mkdir(parents=True, exist_ok=True)
    path = SOURCE / "book-of-mormon.json"
    if not path.exists():
        print("downloading book-of-mormon.json")
        request = urllib.request.Request(URL, headers={"User-Agent": "realm-book-of-mormon build_reference"})
        with urllib.request.urlopen(request) as response:
            path.write_bytes(response.read())
    return json.loads(path.read_text(encoding="utf-8"))


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower().replace("-", "")))


RARITY: dict[str, float] = {}
OSIS: dict[str, str] = {}


def likeness(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    weight = lambda ws: sum(RARITY.get(w, 1.0) for w in ws)
    return weight(wa & wb) / max(1e-9, weight(wa | wb))


def kjv_chapters() -> dict[str, list[tuple[str, str]]]:
    """King James verses by chapter name (`Isaiah 2`), for the chapters QUOTED names."""
    wanted = {c for chapters in QUOTED.values() for c in chapters}
    out: dict[str, list[tuple[str, str]]] = {}
    count: dict[str, int] = {}
    total = 0
    for file in BIBLE_FILES:
        path = BIBLE / file
        if not path.exists():
            sys.exit(f"{path} not found: realm-bible's reference data must sit beside this realm")
        for record in yaml.safe_load(path.read_text(encoding="utf-8")):
            d = record["data"]
            total += 1
            for w in words(d["text"]):
                count[w] = count.get(w, 0) + 1
            OSIS[d["name"]] = d["osis"]
            chapter = d["name"].rsplit(":", 1)[0]
            if chapter in wanted:
                out.setdefault(chapter, []).append((d["name"], d["text"]))
    for w, c in count.items():
        RARITY[w] = math.log(total / c)
    missing = wanted - set(out)
    if missing:
        sys.exit(f"King James chapters not found: {sorted(missing)}")
    return out


def slug(book: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", book.lower()).strip("-")


def header(lines: str) -> str:
    return "\n".join(f"# {line}" if line else "#" for line in lines.strip().splitlines()) + "\n\n"


def write(name: str, comment: str, records: list[dict]) -> None:
    body = yaml.dump(records, allow_unicode=True, sort_keys=False, width=100_000)
    (REFERENCE / name).write_text(header(comment) + body, encoding="utf-8")


def main() -> None:
    source = fetch()
    kjv = kjv_chapters()
    REFERENCE.mkdir(exist_ok=True)
    for old in REFERENCE.glob("bom-*.yml"):
        old.unlink()

    books, chapters, verse_files = [], [], []
    ordinal, near_line, quoting, alluding = 0, [], 0, 0
    for order, book in enumerate(source["books"], start=1):
        name, key = book["book"], slug(book["book"])
        verses = []
        for chapter in book["chapters"]:
            n = chapter["chapter"]
            pool = [v for c in QUOTED.get(chapter["reference"], []) for v in kjv[c]]
            quotes: list[str] = []
            for verse in chapter["verses"]:
                ordinal += 1
                refs: list[str] = []
                alludes: list[str] = []
                if pool:
                    score, ref = max((likeness(verse["text"], text), ref) for ref, text in pool)
                    if any(abs(score - line) < 0.04 for line in (QUOTES, ALLUDES)):
                        near_line.append(f"{score:.2f} {verse['reference']} ↔ {ref}")
                    if score >= QUOTES:
                        refs = [ref]
                        quoting += 1
                        if ref.rsplit(":", 1)[0] not in quotes:
                            quotes.append(ref.rsplit(":", 1)[0])
                    elif score >= ALLUDES:
                        alludes = [ref]
                        alluding += 1
                data = {
                    "ref": f"{key}.{n}.{verse['verse']}", "scripture": "book-of-mormon",
                    "name": verse["reference"], "book": name, "chapter": n, "verse": verse["verse"],
                    "ordinal": ordinal, "text": verse["text"], "translation": "2013 edition",
                    "original": "",
                }
                if refs:
                    data["kjvRefs"] = refs
                    data["kjvOsis"] = [OSIS[r] for r in refs]
                if alludes:
                    data["kjvAllusions"] = alludes
                    data["kjvAllusionOsis"] = [OSIS[r] for r in alludes]
                verses.append({"type": "BomVerse", "data": data,
                               "relations": [{"predicate": "IN", "to": {"type": "BomChapter", "ref": f"{key}.{n}"}}]})
            data = {"ref": f"{key}.{n}", "scripture": "book-of-mormon", "name": chapter["reference"],
                    "book": name, "chapter": n, "verseCount": len(chapter["verses"]),
                    "documentUri": f"bom://text/{key}.{n}"}
            if chapter.get("heading"):
                data["heading"] = chapter["heading"]
            if quotes:
                data["quotes"] = quotes
            chapters.append({"type": "BomChapter", "data": data,
                             "relations": [{"predicate": "IN", "to": {"type": "BomBook", "slug": key}}]})
        data = {"slug": key, "scripture": "book-of-mormon", "name": name, "bookOrder": order,
                "fullTitle": book["full_title"], "chapterCount": len(book["chapters"]), "verseCount": len(verses)}
        if book.get("heading"):
            data["heading"] = book["heading"]
        books.append({"type": "BomBook", "data": data,
                      "relations": [{"predicate": "IN", "to": {"type": "BomScripture", "scripture": "book-of-mormon"}}]})
        verse_files.append((order, key, name, verses))

    if ordinal != VERSES or len(chapters) != CHAPTERS:
        sys.exit(f"{ordinal} verses in {len(chapters)} chapters, not {VERSES} in {CHAPTERS}: refusing to build")

    write("bom-01-scripture.yml", """
The Book of Mormon as one holy book. Generated by scripts/build_reference.py — do not edit by hand.
""", [{"type": "BomScripture", "data": {
        "scripture": "book-of-mormon", "name": "The Book of Mormon", "tradition": "Latter-day Saint",
        "originalLanguage": "English", "translation": "2013 edition", "chapterCount": CHAPTERS,
        "verseCount": VERSES,
        "textSource": "bcbooks/scriptures-json (public domain): the verse text with the 2013 adjustments; no chapter summaries or footnotes",
    }}])
    write("bom-02-books.yml", """
The fifteen books, with the headings printed in the text. Generated by scripts/build_reference.py —
do not edit by hand.
""", books)
    write("bom-03-chapters.yml", """
Every chapter, with the King James chapters it quotes (`quotes`) where it quotes the Bible.
Generated by scripts/build_reference.py — do not edit by hand.
""", chapters)
    for order, key, name, verses in verse_files:
        write(f"bom-04-verses-{order:02d}-{key}.yml", f"""
Every verse of {name}, public domain, from bcbooks/scriptures-json. `kjvRefs` names the King James
verse a verse quotes, `kjvAllusions` one it only alludes to. Generated by scripts/build_reference.py — do not edit by hand.
""", verses)

    print(f"{len(books)} books, {len(chapters)} chapters, {ordinal} verses; {quoting} verses quote the King James, "
          f"{alluding} allude to it")
    print("pairs nearest the line:\n  " + "\n  ".join(sorted(near_line)))


if __name__ == "__main__":
    main()
