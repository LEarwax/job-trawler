# Slice 2 notes: memory, dedup, freshness

## 1. Live run (on the Mac)
Run these back to back:

    uv run trawl run --lane bridge-hospitality
    uv run trawl run --lane bridge-hospitality
    uv run trawl runs

- Run 1: fetched ___ -> in-run duplicates ___, stale ___ -> new ___
- Run 2: new ___ (should be 0; if not, note which posting came back and why you think it did)
- Run `sqlite3 data/trawler.db "SELECT company, title, times_seen FROM postings ORDER BY times_seen DESC LIMIT 5"`.
  Anything with times_seen > 2 after two runs? ___ What does that tell you? ___
- One duplicate the fingerprint missed, or one false match, if you spot any: ___

## 2. Explain it back (2-4 sentences each)

a) `save_postings` runs inside `with conn:`. What exactly happens to posting 1 if posting 2 throws?
   Why does that make "just run it again" safe? Which test proves it?

> 

b) Your first instinct for duplicates was a human or a judge agent. In your words: why is a
   fingerprint enough here, and name one case where it gets the answer wrong.

> 

c) `pipeline.py` takes `today` as a parameter and `service.py` takes a `clock`. Why not just call
   `date.today()` inside the core?

> 

## 3. Design question for slice 3 (Notion sync)
Each field has one owner. List the Notion columns you want on the board, and next to each write
"trawler" or "me". Any column where you're unsure who owns it?

> 

## 4. 60-second version
What slice 2 adds, one number from your live run, one limit.

> 
