"""g50t L1 SOURCE-DECODE (task #82): read the engine's own wired circuit graph
and do a TRUE-passability BFS (engine collision test, offset-free) to answer:
  1. Which plate gates which barrier, and WHERE is each plate/barrier (engine coords).
  2. Is any plate reachable by the live player? (the DECISIVE NEGATIVE said no
     FRAME-observable reachable plate; this checks ENGINE reachability directly.)
  3. What opens the barrier: standing on the plate, or the ghost path, or a
     different trigger?
This is a dev-time source read (decode), NOT a runtime adapter change.
"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}


def find_game(env):
    """Locate the underlying G50t instance from the Arcade env wrapper."""
    seen = set()
    stack = [env]
    while stack:
        o = stack.pop()
        oid = id(o)
        if oid in seen:
            continue
        seen.add(oid)
        if type(o).__name__ == "G50t":
            return o
        for attr in ("_game", "game", "_env", "env", "arcade", "_arcade",
                     "vynnrceibs", "hejgkplfbj", "_impl", "impl"):
            child = getattr(o, attr, None)
            if child is not None and id(child) not in seen:
                stack.append(child)
    return None


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"levels_completed={lvl}")
    game = find_game(env)
    print(f"game object: {type(game).__name__ if game else None}")
    if game is None:
        # dump env attribute tree shallowly
        print("env type:", type(env).__name__)
        print("env attrs:", [a for a in dir(env) if not a.startswith('__')][:60])
        return
    ctrl = game.vgwycxsxjz
    JV = 6  # jarvstobjt cell pitch
    player = ctrl.dzxunlkwxt
    floor_sprite = ctrl.afbbgvkpip
    # real goal = gilbljmfbc sprite (tag ofihnvwckg is the timer/border)
    goal = next(s for s in ctrl.current_level._sprites if "gilbljmfbc" in getattr(s, "tags", []))
    print(f"controller: {type(ctrl).__name__}")
    print(f"PLAYER type={type(player).__name__} pos=({player.x},{player.y}) size=({player.width}x{player.height})")
    print(f"GOAL   type={type(goal).__name__} pos=({goal.x},{goal.y}) size=({goal.width}x{goal.height})")
    print(f"FLOOR  sprite type={type(floor_sprite).__name__} pos=({floor_sprite.x},{floor_sprite.y}) size=({floor_sprite.width}x{floor_sprite.height})")

    # --- circuit graph -------------------------------------------------------
    plates = [o for o in ctrl.hamayflsib if type(o).__name__ == "lqtxaumfed"]
    relays = [o for o in ctrl.hamayflsib if type(o).__name__ == "ulhhdeoyok"]
    blocks = list(ctrl.uwxkstolmf)
    print(f"\n=== CIRCUIT ({len(plates)} plates, {len(relays)} relays, {len(blocks)} toggle-blocks) ===")
    for i, p in enumerate(plates):
        gate = p.nexhtmlmxh
        ginfo = f"gate@({gate.x},{gate.y}) rot={gate.rotation}" if gate else "NO GATE"
        outs = []
        if gate is not None:
            for b in getattr(gate, "ytztewxdin", []):
                outs.append(f"{type(b).__name__}@({b.x},{b.y}) rot={b.rotation} vis={b.is_visible} "
                            f"special={getattr(b,'dpdubazedr',None)}")
        print(f"  PLATE[{i}] @({p.x},{p.y}) rot={p.rotation} -> {ginfo}")
        for s in outs:
            print(f"       -> {s}")
    print("  toggle-blocks (barriers):")
    for i, b in enumerate(blocks):
        print(f"    BLK[{i}] @({b.x},{b.y}) rot={b.rotation} vis={b.is_visible} "
              f"slide_dir={b.hluvhlvimq()} special={b.dpdubazedr}")

    # --- engine-true passability BFS from player spawn -----------------------
    def passable(x, y):
        return ctrl.rhvduhvfwn(player, x, y)

    def bfs(start):
        seen = {start}
        q = deque([start])
        while q:
            cx, cy = q.popleft()
            for dx, dy in ((JV, 0), (-JV, 0), (0, JV), (0, -JV)):
                n = (cx + dx, cy + dy)
                if n in seen or not (0 <= n[0] < 64 and 0 <= n[1] < 64):
                    continue
                if passable(*n):
                    seen.add(n)
                    q.append(n)
        return seen

    spawn = (player.x, player.y)
    reach = bfs(spawn)
    print(f"\n=== ENGINE-TRUE reachability from spawn {spawn}: {len(reach)} cells ===")
    def in_reach(o):
        return any(abs(o.x - rx) < JV and abs(o.y - ry) < JV for rx, ry in reach)
    for i, p in enumerate(plates):
        print(f"  PLATE[{i}] @({p.x},{p.y}) reachable={in_reach(p)}")
    print(f"  GOAL @({goal.x},{goal.y}) reachable_cell?={in_reach(goal)}  "
          f"goal+1 @({goal.x+1},{goal.y+1}) reachable?={((goal.x+1,goal.y+1) in reach) or in_reach(goal)}")
    # dump reachable cells compactly (cell coords / JV) as (row=y/JV, col=x/JV)
    def cell(o):
        return (o.y // JV, o.x // JV)
    rc = sorted(((ry // JV, rx // JV) for rx, ry in reach))
    print(f"  reachable cells (row,col @/{JV}): {rc}")
    print(f"  plate cells: {[cell(p) for p in plates]}  block cells: {[cell(b) for b in blocks]}  goal cell: {cell(goal)}")

    # --- press simulation: seat an occupant on a plate, slide its block -------
    def press(plate):
        """Emulate a ghost standing on `plate`: press it and drain the block
        animation so the barrier reaches its open position, then leave it held."""
        ghost = player  # reuse player object as the seated occupant
        ghost.set_position(plate.x, plate.y)
        ctrl.ayhgaxoxce(ghost, True)
        for _ in range(30):
            if not ctrl.hjvvibklzv:
                break
            for i in range(len(ctrl.hjvvibklzv) - 1, -1, -1):
                if not ctrl.hjvvibklzv[i].rdhwzvqqij():
                    del ctrl.hjvvibklzv[i]

    def report(tag):
        r = bfs(spawn)
        rcs = sorted(((y // JV, x // JV) for x, y in r))
        pa = any(abs(plates[0].x - x) < JV and abs(plates[0].y - y) < JV for x, y in r)
        pb = any(abs(plates[1].x - x) < JV and abs(plates[1].y - y) < JV for x, y in r)
        gl = cell(goal) in rcs or (goal.x, goal.y) in r
        print(f"  [{tag}] reach={len(r)}  plateA(6,2)={pa}  plateB(4,6)={pb}  goal={gl}")
        print(f"        blocks now at: {[ (b.y//JV, b.x//JV) for b in blocks ]} vis={[b.is_visible for b in blocks]}")
        print(f"        reachable cells: {rcs}")
        return r

    # --- frame-observability of a press (answers "why sweep saw nothing") ----
    def render():
        arr = game.camera.render(game.current_level.get_sprites())
        return [[int(v) for v in row] for row in arr]

    def frame_diff(before, after):
        changed = []
        for r in range(len(before)):
            for c in range(len(before[0])):
                if before[r][c] != after[r][c]:
                    changed.append((r, c, before[r][c], after[r][c]))
        return changed

    print("\n=== FRAME-OBSERVABILITY of pressing plate B ===")
    # move player off the plate region first so its blob doesn't confound
    player.set_position(spawn[0], spawn[1])
    f_before = render()
    press(plates[1])
    # keep player parked on plate B (occupant) and render
    f_after = render()
    diff = frame_diff(f_before, f_after)
    # summarise: colour transitions and their cell locations (exclude player blob move)
    from collections import Counter
    trans = Counter((b, a) for _, _, b, a in diff)
    print(f"  total changed pixels: {len(diff)}")
    print(f"  colour transitions (before->after): {dict(trans)}")
    # group changed pixels into cells
    cells_changed = sorted({(r // JV, c // JV) for r, c, _, _ in diff})
    print(f"  changed cells (row,col): {cells_changed}")
    # reset engine state for the reachability sim (re-reach L1 fresh)
    print("\n=== PRESS SIMULATION (nested-circuit validation) ===")
    player.set_position(spawn[0], spawn[1])
    # spawn is at plateB(4,6)? player spawn=(49,25)=cell(4,8); plateB@(37,25)=cell(4,6)
    press(plates[1])   # seat ghost on plate B (reachable)
    report("after press B(4,6)")
    # now try plate A
    pa_now = any(abs(plates[0].x - x) < JV and abs(plates[0].y - y) < JV for x, y in bfs(spawn))
    if pa_now:
        press(plates[0])
        report("after press A(6,2) too")
    else:
        print("  plate A(6,2) still NOT reachable after opening B — deeper nesting or wrong hypothesis")


if __name__ == "__main__":
    main()
