# R101ZORDER — why s5i5 level 4 costs 22 more actions on an archived re-render

Raw artefacts for [[.wiki/wiki/rounds/r101_zorder-rider.md]] and `OPERATING_RULES.md` rule **7cd**.
Nothing here is a full-25 gate; these are probe fans, pulled off ceph-build so they exist outside a
session transcript (rule 2).

| file | probe | what it settles |
| --- | --- | --- |
| `games/s5i5xfer.json.txt` | `scripts/_s5i5_xfer.py`, 6 arms | ⛔ NONDETERMINISM REFUTED — live `[13,30,47,39,32,31]` 3/3, archived `[13,30,47,61,32,31]` 3/3 |
| `games/s5i5own2.json.txt` | `scripts/_s5i5_owner.py`, 2 arms | the OWNER of every level is `swivel` (delegating to `telescope` below level 5), plus each level's opening frame hashed on the layer the tools read |
| `games/s5i5tele.json.txt` | `scripts/_s5i5_tele.py`, 2 arms | the reading inside `TelescopeArmTool._begin`: drawn riders `2 1 2 1 2` live vs `0 0 0 0 0` archived, candidate bars `2 4 4 9 5`, plans and pairings refuted |
| `games/s5i5oracle.json.txt` | `scripts/_s5i5_oracle.py`, 3 runs in ONE process | ⭐ THE INTERVENTION — restoring the rider evidence inside `_begin` alone returns the archived board to `[13,30,47,39,32,31]` / 0.583333 |
| `games/srcdiff_and_framecmp.txt` | `scripts/_s5i5_srcdiff.py` + `scripts/_s5i5_framecmp.py` | the two serializations place identical sprites at identical positions on all eight levels and differ only in LIST ORDER; the level in question differs in EXACTLY ONE CELL, `(43,31)`, marker vs bar |

To reproduce the number this round explains:

```
bash scripts/xfergate.sh <name> scripts/rounds/R101SHIPPED 12 4000
```
