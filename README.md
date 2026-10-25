# realm-book-of-mormon

> **Experimental.** Its types are children of
> [realm-scripture-vocabulary](https://github.com/embabel-worlds/realm-scripture-vocabulary), which must be installed first — a
> child whose parent's realm is missing is refused at load. It also needs a host that writes a child
> type's inherited properties (Embabel hosts from October 2026): a `BomVerse` declares little of its own.

The Book of Mormon as a queryable graph: read a verse or a chapter, search it, compare its books,
and read every chapter that quotes the Bible beside its King James source. Because a `BomVerse` is a
`Verse`, a question asked of every scripture is answered here too.

## Shape

```
BomScripture ◀─IN─ BomBook ◀─IN─ BomChapter ◀─IN─ BomVerse
(HolyBook)         (ScriptureBook) (ScriptureChapter) (Verse)
                                                        │
                                                        └─CORRESPONDS_TO─▶ BibleVerse   (with realm-bible)
```

| | Count |
|---|---|
| BomScripture | 1 |
| BomBook | 15 (1 Nephi … Moroni) |
| BomChapter | 239 |
| BomVerse | 6,604 |

It was received in English, so a verse has one text: `text` is the scripture and `original` is
empty, as the vocabulary says it is for a scripture whose own language is English. No book shares a
name with a book of the Bible, so references are as a reader writes them: `1 Nephi 3:7`.

The headings printed in the text since 1830 are kept: one at the head of most books, and fifteen on
chapters (Mosiah 9, Alma 5, …). The chapter summaries of later editions are not; they are under
copyright, and the source leaves them out.

## Where it quotes the Bible

The Book of Mormon quotes the King James at length: twenty-one chapters of Isaiah, most of them whole, the Sermon on the
Mount (3 Nephi 12–14), Malachi 3 and 4 (3 Nephi 24–25), and shorter passages from Micah, Acts, Mark
and 1 Corinthians. The build finds which verse quotes which. It does not take them from a
hand-written table.

1. `QUOTED` in `scripts/build_reference.py` names, for each chapter that quotes, the King James
   chapters it draws on.
2. Each verse in that chapter is paired with the verse in those chapters it reads most like.
   Likeness is shared words, weighted by rarity.
3. The pair is kept as a **quotation** at 0.4 or above, and as an **allusion** from 0.26 to 0.4.
   Below that the verse is unpaired.

The two thresholds were set from the measured distribution, which splits in two with a band between.
Quotations sit above 0.4, almost all near 1.0. Verses that only share the chapter's vocabulary ("and
it shall come to pass") sit below 0.25. The band between holds real paraphrase: Mosiah 15:14–18 on
Isaiah 52:7, and Moroni 7:45 on 1 Corinthians 13:4. Words alone found it, so an allusion is a
candidate for a reader, not a finding.

The result is 580 verses quoting and 15 alluding. Each stores `kjvRefs` or `kjvAllusions`, and
`rules/corresponds.yml` derives `CORRESPONDS_TO {kind}` to realm-bible's `BibleVerse`. It is empty if
realm-bible is not installed. A chapter's `quotes` lists the King James chapters it quotes.

## Views

| View | Answers |
|---|---|
| `ReadBomVerse` | one verse, with the King James verse it quotes or alludes to |
| `ReadBomChapter` | a whole chapter, with its printed heading and the chapters it quotes |
| `BomBooks` | the fifteen books, their titles, sizes and headings |
| `SearchBookOfMormon` | verses containing a word |
| `BooksMentioning` | which books use a word most, per thousand verses |
| `QuotedChapters` | every chapter that quotes the King James, and how many of its verses do |
| `BomBesideKingJames` | a quoting chapter verse by verse beside its source, through `CORRESPONDS_TO` (needs realm-bible) |

Searching across scriptures, by word and by meaning, is in realm-scripture-vocabulary.

`sources.yml` declares the text as documents too — one per chapter (`bom://text/1-nephi.1`), tagged
`scripture` so the vocabulary's meaning search ranks it beside every other scripture — embedded on
install.

## Rebuilding the reference data

```
python scripts/build_reference.py
```

Downloads into `data/source/` (ignored by git) and rewrites `reference/`. It reads the King James from
`../realm-bible/reference/` and refuses to build without it, because the quotations cannot be found
without their source. It prints the pairs nearest each threshold, so the effect of a new source on
the thresholds can be judged.

## Licences

- **Text**: [bcbooks/scriptures-json](https://github.com/bcbooks/scriptures-json), public domain.
  The verse text carries the 2013 edition's typographic adjustments, which the source judges too
  slight to be copyrightable. It has no chapter summaries, footnotes or introduction.
- **Code**: GPL-3.0, as realm-bible.
