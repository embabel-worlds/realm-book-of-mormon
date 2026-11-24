#!/bin/sh
# Ground truth for realm-book-of-mormon, against the text it was built from.
#
#   L1  every view answers BY NAME on its defaults, and the ones that read stored text are not empty
#   L2  the graph against bcbooks/scriptures-json, fetched fresh: every book, every chapter's verse
#       count, and every verse's text, exactly; the holy book's counts; the stored reference/ loaded whole
#   L3  views against the graph: a chapter, a search and a per-book count agree with direct Cypher
#   L4  with realm-bible installed: a quoting chapter is paired with exactly the King James verses its
#       stored `kjvRefs` name (skipped, and said so, when realm-bible is absent)
#
# No producers and no source calls at query time — the text is stored — so there is no pushdown or
# cost check to make. Keyless: the source is a public file.
#
#   APPLIANCE=http://127.0.0.1:11043 AUTH=user:pass sh tests/verify.sh
#
# The last line on success is exactly `ALL CHECKS PASS`; any failure exits non-zero.
set -e
AUTHCFG=$(mktemp); trap 'rm -f "$AUTHCFG"' EXIT
if [ -n "${TOKEN:-}" ]; then printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" > "$AUTHCFG"
else printf 'user = "%s"\n' "${AUTH:?set AUTH (user:pass) or TOKEN}" > "$AUTHCFG"; fi
APPLIANCE="${APPLIANCE:-http://127.0.0.1:11043}"
APPLIANCE="$APPLIANCE" AUTHCFG="$AUTHCFG" python3 - "$(dirname "$0")/.." <<'PY'
import glob, json, os, subprocess, sys, urllib.request, yaml
base, auth, realm = os.environ["APPLIANCE"], os.environ["AUTHCFG"], sys.argv[1]
SOURCE = "https://raw.githubusercontent.com/bcbooks/scriptures-json/master/book-of-mormon.json"
fail = 0

def post(path, body):
    out = subprocess.run(["curl", "-s", "--max-time", "600", "-K", auth, "-X", "POST", base + path,
                          "-H", "Content-Type: application/json", "-d", json.dumps(body)],
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out, strict=False)
    except ValueError:
        return {"error": "not JSON: " + out[:200]}
def kg(cypher):
    r = post("/api/v1/admin/kg/execute", {"cypher": cypher})
    if r.get("error"):
        raise SystemExit("  FAIL query REFUSED: %s\n    %s" % (str(r["error"])[:200], cypher))
    return r.get("rows") or []
def view(name, args=None):
    return post("/api/v1/views/%s/invoke" % name, {"args": args or {}})
def check(what, want, got):
    global fail
    if want == got: print("  ok   %s = %s" % (what, got if len(str(got)) < 80 else str(got)[:77] + "..."))
    else: print("  FAIL %s: expected %s, got %s" % (what, str(want)[:300], str(got)[:300])); fail = 1
def records(kind):
    out = []
    for f in sorted(glob.glob(os.path.join(realm, "reference", "*.yml"))):
        out += [r["data"] for r in yaml.safe_load(open(f)) or [] if r.get("type") == kind]
    return out

# The stored reference is written in the background after the realm reports active, so a battery that
# starts at once reads a half-written graph. Wait until every stored verse of this realm, and of
# realm-bible (which it requires), is there: the counts the stored files and the holy book declare.
import time
def wait_seeded(what, query, want):
    deadline = time.time() + 1800
    while True:
        got = kg(query)[0]["n"]
        if got == want: return
        if time.time() > deadline:
            raise SystemExit("  FAIL %s: %d of %d written after 30 minutes" % (what, got, want))
        print("  wait %s: %d of %d written" % (what, got, want)); time.sleep(30)
for label in ['BomVerse']:
    wait_seeded(label, "MATCH (v:%s) RETURN count(v) AS n" % label, len(records(label)))
# realm-bible is required, so it is always installed; its canon node may itself still be on its way.
wait_seeded("the Bible's holy book", "MATCH (h:HolyBook {scripture: 'bible'}) RETURN count(h) AS n", 1)
wait_seeded("BibleVerse", "MATCH (b:BibleVerse) RETURN count(b) AS n",
            kg("MATCH (h:HolyBook {scripture: 'bible'}) RETURN h.verseCount AS n")[0]["n"])
bible = True

print("== L1: every view answers by name ==")
NEEDS_BIBLE = {"BomBesideKingJames"}
for f in sorted(glob.glob(os.path.join(realm, "views", "*.yml"))):
    for v in yaml.safe_load(open(f)):
        r = view(v["name"])
        rows = r.get("data") or []
        if r.get("status") != "SUCCEEDED":
            print("  FAIL %s: %s %s" % (v["name"], r.get("status"), str(r.get("error") or r)[:200])); fail = 1
        elif not rows:
            print("  FAIL %s answered no rows on its defaults" % v["name"]); fail = 1
        else:
            print("  ok   %-22s %d rows" % (v["name"], len(rows)))

print("== L2: the graph against bcbooks/scriptures-json ==")
src = json.load(urllib.request.urlopen(SOURCE, timeout=120))
books = src["books"]
check("books", [b["book"] for b in books],
      [r["book"] for r in kg("MATCH (b:BomBook) RETURN b.name AS book ORDER BY b.bookOrder")])
want_chapters = {c["reference"]: len(c["verses"]) for b in books for c in b["chapters"]}
got_chapters = {r["c"]: r["n"] for r in kg("MATCH (c:BomChapter)<-[:IN]-(v:BomVerse) RETURN c.name AS c, count(v) AS n")}
check("chapters", len(want_chapters), len(got_chapters))
check("verses in every chapter", want_chapters, got_chapters)
total = sum(want_chapters.values())
h = kg("MATCH (h:BomScripture) RETURN h.chapterCount AS chapters, h.verseCount AS verses")
check("holy book's counts", [{"chapters": len(want_chapters), "verses": total}], h)
for b in books:
    want = {v["reference"]: v["text"] for c in b["chapters"] for v in c["verses"]}
    got = {r["n"]: r["t"] for r in kg("MATCH (v:BomVerse {book: '%s'}) RETURN v.name AS n, v.text AS t" % b["book"])}
    bad = sorted(k for k in want if want[k] != got.get(k)) + sorted(set(got) - set(want))
    check("%s: every verse's text, exactly (%d)" % (b["book"], len(want)), [], bad[:5])
check("the stored reference/ loaded whole (verses)", len(records("BomVerse")),
      kg("MATCH (v:BomVerse) RETURN count(v) AS n")[0]["n"])

print("== L3: views against the graph ==")
r = view("ReadBomChapter", {"chapter": "Alma 32"})
check("ReadBomChapter Alma 32 verses", want_chapters["Alma 32"], len(r.get("data") or []))
n = kg("MATCH (v:BomVerse) WHERE toLower(v.text) CONTAINS 'faith' RETURN count(v) AS n")[0]["n"]
r = view("SearchBookOfMormon", {"term": "faith", "limit": 10000})
check("SearchBookOfMormon 'faith' = Cypher count", n, len(r.get("data") or []))
check("  ...and = the source's count", sum(1 for b in books for c in b["chapters"] for v in c["verses"]
                                          if "faith" in v["text"].lower()), n)
per = {}
for b in books:
    for c in b["chapters"]:
        for v in c["verses"]:
            if "repent" in v["text"].lower(): per[b["book"]] = per.get(b["book"], 0) + 1
r = view("BooksMentioning", {"term": "repent"})
check("BooksMentioning 'repent', per book, from the source", per, {x["book"]: x["verses"] for x in r.get("data") or []})

print("== L4: quotations paired with the King James ==")
if not bible:
    print("  skip realm-bible is not installed, so CORRESPONDS_TO is empty by design")
else:
    for chapter in ("2 Nephi 12", "3 Nephi 13", "Mosiah 14"):
        want = sorted((v["verse"], k) for v in records("BomVerse") if v["name"].startswith(chapter + ":")
                      for k in v.get("kjvRefs") or [])
        rows = view("BomBesideKingJames", {"chapter": chapter}).get("data") or []
        got = sorted((x["verse"], x["kingJames"]) for x in rows if x.get("kind") == "quotation")
        check("%s quotes exactly its stored kjvRefs (%d)" % (chapter, len(want)), want, got)

if fail: print("FAILED"); sys.exit(1)
print("ALL CHECKS PASS")
PY
