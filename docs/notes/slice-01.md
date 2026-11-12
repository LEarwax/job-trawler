# Slice 1 notes: one lane, one source, print to terminal

## 1. Live run (fill in after running on the Mac)
Command: `uv run trawl run --lane bridge-hospitality`

- Postings shown: ___   Fetched before dedup: ___
- Newest posting date: ___   Oldest: ___
- How many have pay listed? ___
- Any source errors? ___
- Look at 3 links. Are they real bartender jobs within ~25 mi? ___
- One thing that surprised you: ___

## 2. Explain it back (your words, 2-4 sentences each)

a) Trace one bartender posting from Indeed to your terminal. Name each file it passes through
   and the DTO it's in at each step.

> 

b) Tomorrow you want to add Craigslist. Which files change, and which don't? Why is the "don't"
   list the point of the design?

> 

c) `pipeline.py` catches every exception from a source and keeps going. Give one way this
   could hide a real problem from you, and what slice 4 (heartbeat) should do about it.

> 

## 3. Decision for slice 2: SQLite or Notion-only?
Write your call and the one reason that decided it. (Context is in the chat on 2026-11-12.)

> 

## 4. 60-second version
What slice 1 does, one concrete result from your live run, and one limit.

> 
