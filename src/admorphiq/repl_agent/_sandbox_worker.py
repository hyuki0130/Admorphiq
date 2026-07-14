"""Subprocess worker for the code-REPL sandbox (R55 module 4).

Reads a JSON job ``{code, payload, max_output}`` on stdin, binds the inspection
API onto a restricted namespace (stdlib-allowlist builtins reused from
``ewm.core``), executes the model code with stdout captured, and prints a JSON
result ``{stdout, error, actions}`` on the real stdout. Runs as a throwaway
process so the parent's hard timeout can kill a runaway loop.

Invoked as ``python -m admorphiq.repl_agent._sandbox_worker``; never imported.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import traceback
from typing import Any

from admorphiq.ewm.core import _safe_builtins
from admorphiq.repl_agent.sandbox import Inspector


def _run(job: dict[str, Any]) -> dict[str, Any]:
    inspector = Inspector(job["payload"])
    max_output = int(job.get("max_output", 4000))

    namespace: dict[str, Any] = {"__builtins__": _safe_builtins()}
    # Bind the inspection + action API as plain callables the model code uses.
    for name in ("objects", "crop", "ascii", "mask", "compare", "relations",
                 "shortest_path", "action_outcomes", "is_dead", "action"):
        namespace[name] = getattr(inspector, name)

    buf = io.StringIO()
    error = ""
    try:
        compiled = compile(job["code"], "<model>", "exec")
    except SyntaxError as exc:
        return {"stdout": "", "error": f"syntax error: {exc}", "actions": inspector.actions}

    with contextlib.redirect_stdout(buf):
        try:
            exec(compiled, namespace)  # noqa: S102 - sandboxed restricted namespace
        except BaseException as exc:  # noqa: BLE001 - surfaced to the parent
            error = f"{type(exc).__name__}: {exc}"
            tb = traceback.format_exc(limit=2)
            error = (error + "\n" + tb)[:max_output]

    return {
        "stdout": buf.getvalue()[:max_output],
        "error": error,
        "actions": inspector.actions,
    }


def main() -> None:
    try:
        job = json.loads(sys.stdin.read())
        result = _run(job)
    except Exception as exc:  # noqa: BLE001 - report malformed jobs cleanly
        result = {"stdout": "", "error": f"worker error: {exc}", "actions": []}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
