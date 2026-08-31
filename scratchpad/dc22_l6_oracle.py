"""dc22 level 6 ORACLE — execute the solution read out of the game's own source.

Purpose: prove (or refute) that dc22's last level is winnable, by driving the REAL
game module through the chain the source describes:
  pressure plates gate the crane buttons -> piyqze keys unlock the cycle+grab buttons ->
  the 'c' button teleports the mover between paired tewfut tiles -> the crane carries the
  20x20 brixto platform from (0,24) to the top rail, bridging the top gap -> walk to goal.

Rule 7f: level changes are reported with DIRECTION and the resulting number.
"""
import sys, json, importlib.util, collections

SRC = "environment_files/dc22/fdcac232/dc22.py"
STEP = 2


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def can_stand(g, x, y):
    return g.sxnzvaqltp(x, y, g.qnnpcoyzd) is not None


def blocked(g, x, y):
    mv = g.qnnpcoyzd
    ox, oy = mv.x, mv.y
    mv.set_position(x, y)
    hit = None
    for o in g.current_level.get_sprites():
        if g.collides_with(mv, o):
            hit = o.name
            break
    mv.set_position(ox, oy)
    return hit


DIRS = {1: (0, -STEP), 2: (0, STEP), 3: (-STEP, 0), 4: (STEP, 0)}


def path_to(g, tx, ty):
    """BFS over mover positions with the CURRENT board; returns list of action ids or None."""
    start = (g.qnnpcoyzd.x, g.qnnpcoyzd.y)
    if start == (tx, ty):
        return []
    prev = {start: None}
    q = collections.deque([start])
    while q:
        cur = q.popleft()
        for aid, (dx, dy) in DIRS.items():
            nx, ny = cur[0] + dx, cur[1] + dy
            if (nx, ny) in prev:
                continue
            if not (0 <= nx < 64 and 0 <= ny < 64):
                continue
            mv = g.qnnpcoyzd
            ox, oy = mv.x, mv.y
            mv.set_position(cur[0], cur[1])
            bad = blocked(g, nx, ny)
            mv.set_position(ox, oy)
            if bad:
                continue
            if not can_stand(g, nx, ny):
                continue
            prev[(nx, ny)] = (cur, aid)
            if (nx, ny) == (tx, ty):
                out = []
                node = (nx, ny)
                while prev[node] is not None:
                    p, a = prev[node]
                    out.append(a)
                    node = p
                return out[::-1]
            q.append((nx, ny))
    return None


class Runner:
    def __init__(self, g, mod):
        from arcengine.base_game import ActionInput
        self.AI = ActionInput
        self.g = g
        self.mod = mod
        self.n = 0
        self.start_score = g._score
        self.log = []

    def act(self, aid, x=None, y=None, why=""):
        a = self.AI(id=aid, data=({"x": x, "y": y} if aid == 6 else {}))
        self.g.perform_action(a)
        self.n += 1
        lvl = self.g._score
        if lvl > self.start_score:
            print(json.dumps({"result": "CLEARED", "direction": "UP",
                              "level_from": self.start_score, "level_to": lvl,
                              "actions": self.n, "state": self.g._state.name,
                              "last": why}), flush=True)
            sys.exit(0)
        if lvl < self.start_score:
            print(json.dumps({"result": "FELL_BACK", "direction": "DOWN",
                              "level_to": lvl, "actions": self.n, "last": why}), flush=True)
            sys.exit(0)
        if self.g._state.name == "GAME_OVER":
            print(json.dumps({"result": "GAME_OVER", "actions": self.n, "last": why}), flush=True)
            sys.exit(0)
        return self.g

    def walk(self, tx, ty, why=""):
        p = path_to(self.g, tx, ty)
        if p is None:
            print(f"  [walk] NO PATH from {(self.g.qnnpcoyzd.x, self.g.qnnpcoyzd.y)} to {(tx,ty)}  ({why})", flush=True)
            return False
        for aid in p:
            self.act(aid, why=f"walk {why}")
        print(f"  [walk] {why}: reached {(self.g.qnnpcoyzd.x, self.g.qnnpcoyzd.y)} in {len(p)} actions (total {self.n})", flush=True)
        return True

    def click_sprite(self, name, why=""):
        """Click the first non-transparent pixel of a named sprite (must be live)."""
        from arcengine.sprites import InteractionMode
        for s in self.g.current_level.get_sprites():
            if s.name != name:
                continue
            if s.interaction in (InteractionMode.REMOVED, InteractionMode.INVISIBLE):
                continue
            px = s.render()
            for yy in range(px.shape[0]):
                for xx in range(px.shape[1]):
                    if px[yy, xx] >= 0:
                        self.act(6, s.x + xx, s.y + yy, why=f"click {name} {why}")
                        print(f"  [click] {name} at ({s.x+xx},{s.y+yy}) {why} (total {self.n})", flush=True)
                        return True
        print(f"  [click] {name} NOT LIVE ({why})", flush=True)
        return False


def state(g, tag=""):
    from arcengine.sprites import InteractionMode
    live = [s.name for s in g.current_level.get_sprites_by_tag("sys_click")
            if s.interaction not in (InteractionMode.REMOVED, InteractionMode.INVISIBLE)]
    tew = [(s.name, s.x, s.y) for s in g.current_level.get_sprites_by_tag("tewfut")
           if s.interaction != InteractionMode.REMOVED]
    br = [(s.name, s.x, s.y, s.interaction.name) for s in g.current_level.get_sprites()
          if s.name.startswith("brixto-orckhi")]
    print(f"[{tag}] mover={(g.qnnpcoyzd.x,g.qnnpcoyzd.y)} goal={(g.hfuqkxulm.x,g.hfuqkxulm.y)} "
          f"crane=({g.sjixewahg},{g.uxtzlxsiq}) att={g.svxnnbpjl} live={live}", flush=True)
    print(f"      tewfut={tew}", flush=True)
    print(f"      brixto={br}", flush=True)


def main():
    m = load()
    g = m.Dc22()
    g.set_level(5)
    r = Runner(g, m)
    state(g, "start")

    # 1. reach the 'd' key at (6,18) -- unlocks the colour-cycle button
    r.walk(6, 18, "to d-key (6,18)")
    state(g, "after d-key")

    # 2. back to the cycle tile at (18,48)
    r.walk(18, 48, "to cycle tile (18,48)")
    state(g, "on cycle tile")

    # 3. teleport with the 'c' button
    r.click_sprite("buezna-matkhq", "teleport c")
    state(g, "after c click")

    print(json.dumps({"result": "SCRIPT_END", "actions": r.n,
                      "mover": [g.qnnpcoyzd.x, g.qnnpcoyzd.y], "level": g._score}), flush=True)


if __name__ == "__main__":
    main()
