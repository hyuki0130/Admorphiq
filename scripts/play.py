"""Interactive ARC-AGI-3 game player — play games in the terminal."""

import sys

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

# ARC color palette → ANSI 256-color codes
# 0=black, 1=blue, 2=red, 3=green, 4=yellow, 5=gray, 6=magenta, 7=orange, 8=cyan, 9=brown
# 10-15: lighter variants
_COLOR_MAP = {
    0: 0,      # black
    1: 21,     # blue
    2: 196,    # red
    3: 46,     # green
    4: 226,    # yellow
    5: 245,    # gray
    6: 201,    # magenta
    7: 208,    # orange
    8: 51,     # cyan
    9: 130,    # brown
    10: 33,    # light blue
    11: 203,   # light red
    12: 119,   # light green
    13: 229,   # light yellow
    14: 213,   # light magenta
    15: 231,   # white
}


def colored_block(val: int) -> str:
    """Render a single cell as a colored block."""
    c = _COLOR_MAP.get(int(val), 0)
    return f"\033[48;5;{c}m  \033[0m"


def render_frame(frame: np.ndarray, scale: int = 2) -> str:
    """Render a (64,64) frame to terminal string, downsampled by scale."""
    h, w = frame.shape
    lines = []
    for y in range(0, h, scale):
        row = ""
        for x in range(0, w, scale):
            # Take the most common non-zero value in the block, or 0
            block = frame[y:y + scale, x:x + scale]
            vals = block.flatten()
            nonzero = vals[vals != 0]
            if len(nonzero) > 0:
                val = int(np.bincount(nonzero.astype(np.int32)).argmax())
            else:
                val = 0
            row += colored_block(val)
        lines.append(row)
    return "\n".join(lines)


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def select_game(arcade: Arcade) -> str | None:
    """Show game list and let user pick one."""
    envs = arcade.get_environments()
    if not envs:
        print("No environments available.")
        return None

    print(f"\n  Available games ({len(envs)}):\n")
    for i, e in enumerate(envs):
        actions = e.baseline_actions or []
        total = sum(actions) if actions else "?"
        print(f"  [{i:2d}] {e.game_id:<20} {e.title or '':<6} levels={len(actions)}  baseline_actions={total}")

    print(f"\n  Enter number (0-{len(envs)-1}) or game_id, q to quit:")
    choice = input("  > ").strip()
    if choice.lower() == "q":
        return None
    try:
        idx = int(choice)
        if 0 <= idx < len(envs):
            return envs[idx].game_id
    except ValueError:
        # Try as game_id
        for e in envs:
            if e.game_id.startswith(choice):
                return e.game_id
    print(f"  Invalid choice: {choice}")
    return None


def show_status(obs, action_count: int, game_id: str) -> None:
    """Print game status info."""
    available = [GameAction.from_id(a).name for a in obs.available_actions]
    print(f"  Game: {game_id}  |  State: {obs.state.name}  |  "
          f"Level: {obs.levels_completed}/{obs.win_levels}  |  Actions: {action_count}")
    print(f"  Available: {', '.join(available)}")


def show_help() -> None:
    print("  Controls: 1-5=ACTION1-5  6=ACTION6(+coords)  7=ACTION7  r=RESET  q=quit  h=help")


def play_game(arcade: Arcade, game_id: str) -> None:
    """Main game loop."""
    env = arcade.make(game_id)
    if env is None:
        print(f"  Failed to create environment for {game_id}")
        return

    obs = env.observation_space
    if obs is None:
        print("  No observation after make()")
        return

    action_count = 0
    clear_screen()
    print(f"\n  === {game_id} ===\n")
    show_help()

    while True:
        # Render frame (first layer)
        print()
        if obs.frame:
            frame = obs.frame[0] if hasattr(obs.frame[0], 'shape') else np.array(obs.frame[0])
            print(render_frame(frame.astype(np.int32), scale=2))

            # Show additional layers indicator
            if len(obs.frame) > 1:
                print(f"  ({len(obs.frame)} layers, showing layer 0)")

        print()
        show_status(obs, action_count, game_id)
        show_help()

        # Check terminal state
        if obs.state.name == "WIN":
            print("\n  *** YOU WIN! ***")
            input("  Press Enter to continue...")
            break
        if obs.state.name == "GAME_OVER":
            print("\n  *** GAME OVER ***")
            choice = input("  Press r to reset, q to quit: ").strip().lower()
            if choice == "r":
                obs = env.step(GameAction.RESET)
                action_count += 1
                clear_screen()
                continue
            break

        # Get input
        cmd = input("\n  Action> ").strip().lower()

        if cmd == "q":
            break
        elif cmd == "h":
            show_help()
            continue
        elif cmd == "r":
            obs = env.step(GameAction.RESET)
            action_count += 1
        elif cmd in ("1", "2", "3", "4", "5", "7"):
            action_id = int(cmd)
            if action_id not in obs.available_actions:
                print(f"  ACTION{cmd} not available!")
                continue
            action = GameAction.from_id(action_id)
            obs = env.step(action)
            action_count += 1
        elif cmd == "6":
            if 6 not in obs.available_actions:
                print("  ACTION6 not available!")
                continue
            try:
                x_str = input("    x (0-63): ").strip()
                y_str = input("    y (0-63): ").strip()
                x, y = int(x_str), int(y_str)
                if not (0 <= x <= 63 and 0 <= y <= 63):
                    print("  Coordinates out of range!")
                    continue
                action = GameAction.ACTION6
                action.set_data({"x": x, "y": y})
                obs = env.step(action, data={"x": x, "y": y})
                action_count += 1
            except (ValueError, EOFError):
                print("  Invalid coordinates!")
                continue
        else:
            print(f"  Unknown command: {cmd}")
            continue

        if obs is None:
            print("  Error: no response from environment")
            break

        clear_screen()
        print(f"\n  === {game_id} ===\n")


def main() -> None:
    print("\n  === ARC-AGI-3 Interactive Player ===\n")

    arcade = Arcade(operation_mode=OperationMode.NORMAL)

    while True:
        game_id = select_game(arcade)
        if game_id is None:
            break
        play_game(arcade, game_id)
        print()

    print("  Bye!")


if __name__ == "__main__":
    main()
