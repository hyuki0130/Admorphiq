"""`induce.discover_lattice` across every sample game — where does a click do something?

64 probes per game on a stride-8 grid, counter cells filtered. The footprint column is the
interesting one: a board where every response flips the SAME number of cells is running a
uniform operator (a toggle or parity rule), which is what the stencil family looks like.

⛔ Two limits, both about this instrument rather than the games, and both measured:
  * it reads ONE layer (`canonical_layer`), so a game whose response is drawn on another layer
    reads as inert — sp80 scores 0 here and is known to answer a placement with a 20-layer spill;
  * it probes stride 8, so controls finer or offset from that grid are invisible.
A zero is "no response found by THIS sweep", never "this game ignores clicks".
"""

import sys

sys.path.insert(0,"src")
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.base import canonical_layer
from admorphiq.tools.induce import discover_lattice


def _kind(delta):
    """MOVE or EDIT? A uniform footprint means one operator OR one object translating.

    ⛔ Measured on cn04, which the footprint column alone called "a single 135-cell operator":
    the 135 cells are a 15x15 shape TRANSLATING three cells per action. The discriminator is that
    a move leaves two disjoint congruent blobs (vacated + occupied) while an edit leaves one.
    """
    cells=set(delta)
    seenc=set(); blobs=[]
    for c in cells:
        if c in seenc: continue
        st=[c]; seenc.add(c); blob=[]
        while st:
            y,x=st.pop(); blob.append((y,x))
            for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                n=(y+dy,x+dx)
                if n in cells and n not in seenc:
                    seenc.add(n); st.append(n)
        blobs.append(blob)
    if len(blobs)==2 and abs(len(blobs[0])-len(blobs[1]))<=max(2,len(cells)//10):
        return "move"
    return "edit"


arcade=Arcade(operation_mode=OperationMode.OFFLINE)
seen=set()
print(f"{'game':6s} {'resp':>4s} {'pitch':>5s} {'hud':>4s}  footprints / kind")
for info in arcade.get_environments():
    title=(info.title or info.game_id).split('-')[0].lower()
    if title in seen: continue
    seen.add(title)
    env=arcade.make(info.game_id); box=[env.reset()]
    def probe(cell):
        b=canonical_layer(box[0])
        box[0]=env.step(GameAction.ACTION6, data={"x":cell[1],"y":cell[0]})
        return b, canonical_layer(box[0])
    try:
        r=discover_lattice(probe, 64, coarse=8, budget=64)
    except Exception as e:
        print(f"{title:6s} ERROR {type(e).__name__}"); continue
    sizes=sorted({len(v) for v in r["live"].values()})
    kinds={_kind(v) for v in r["live"].values()}
    print(f"{title:6s} {len(r['live']):4d} {str(r['stride']):>5s} {r['hud_cells']:4d}  "
          f"{sizes[:6]:} {sorted(kinds)}")
