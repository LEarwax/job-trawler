# Slice 3 notes: the Notion board

## 1. Live sync (on the Mac)
After the token is in `.env` and the integration is connected to the Job Board:

    uv run trawl sync --limit 3     # small first push; check the board
    uv run trawl sync               # the rest
    uv run trawl sync               # should say "board is up to date"

- Pushed: ___  Failed: ___  Any errors? ___
- Open one row on the board. Anything wrong or missing? ___
- Set one row to Pass with a reason, then run `trawl sync` again. Did anything change on that row? ___

## 2. Explain it back (2-4 sentences each)

a) `save_postings` uses one transaction for the whole batch. `sync` commits after every single
   row. Why is each right for its own job? What would go wrong if you swapped them?

> 

b) A 401 stops the sync immediately, but a 400 on one row just skips that row. Why treat them
   differently?

> 

c) The guard refuses any payload that contains Status. Nothing in the code tries to write Status
   today. So why have the check?

> 

## 3. 60-second version
What slice 3 adds, one thing you saw on the live board, one limit.

> 
