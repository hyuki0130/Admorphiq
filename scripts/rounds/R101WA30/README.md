# R101WA30 — wa30's last level

Two rounds of work on the same board, in order.

## What is here

* `WITNESS.txt` — a **verified 70-action clear of level 9**, replayed outside the search that
  found it. `schedule_search.jsonl` holds 66- and 69-action variants. ⛔ These came from a
  hill-climb over the carrier's schedule scored by the REAL ENGINE, reading sprite tags and the
  bay set directly, so they are proof that a <=70-action solution EXISTS and nothing more. They
  are not a plan a frame-only tool can follow and they were never shipped.
* `schedule_search.jsonl` — the schedule search's results (`scripts/_wa30_search.py`).
* `searches.jsonl` — the earlier beam over whole deliveries (`scripts/_wa30_macro.py`) and the
  left/right partition runs (`scripts/_wa30_plan.py`). Best 7 of 9; the partition alone does not
  do it.
* `policy_sweep.jsonl` — six fixed policies against the game's own win predicate
  (`scripts/_wa30_l9.py`): pass / kill+pass / random / the shipped harness / haul / kill+haul.
  Best 8 of 9, and the census that pins the board: 9 pieces, 2 movers, 1 thief, 208 bay cells,
  64 den cells, 6 no-go, **70 steps**.

## What actually cleared it

Not a better schedule. `scripts/_wa30_l9diag.py` ran the whole game through the real harness and
found that level 9 gets **eight attempts** — the counter restarts the level rather than ending the
game — and that six of the eight were the SAME attempt, because the tool had nothing watching for
a restart. `scripts/_wa30_l9var.py` measured five candidate mechanisms; two of them together clear
the board and neither does alone. Full account: `.wiki/wiki/rounds/r101_wa30-level-restart.md`.

⛔ Every search in this directory searched INSIDE one attempt, which is why none of them found it.

⚠️ The three `.jsonl` files here are FORCE-ADDED past `.gitignore`'s repo-wide `*.jsonl` (that rule
exists for transient fan output; these are 21 KB of measurement and the verified witnesses are in
them). A measurement that lives only on the box does not exist — `OPERATING_RULES.md` rule 2.
