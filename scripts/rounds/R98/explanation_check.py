"""R98 explanation check — is a model's stated reason TRUE of the animation it saw?

Purpose
-------
The fill stage separates models on one slot, and the unscored follow-up now recovers why
each answers as it does. A stated reason is not evidence until it is checked: a model may
cite the animation and be wrong about it, which must not be read as either "it earned the
answer" or "it reasoned from a prior".

The frozen contract capture makes three claims checkable, and they are the three an
explanation is most likely to lean on:

* the flow ENTERED a hazard, or was destroyed by one — false: no flow cell ever occupies
  the hazard row, the spill stops one row short of it;
* a failure marking, reset or screen APPEARED — false: a failing spill carries no failure
  colour on any of its layers and this capture's last layer is one ordinary flow cell;
* the targets were NOT satisfied — false: both cups reach the satisfied appearance.

Expected feedback
-----------------
Per explanation, the claims it makes that the capture contradicts. Nothing flagged means
the reason is consistent with what was shown — which is not the same as the answer being
right, and the script says so rather than implying otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CONTRADICTED = (
    (r"enter\w*\s+the\s+(hazard|barrier)|(hazard|barrier)\s+was\s+entered|"
     r"(destroyed|consumed|absorbed)\s+by\s+the\s+(hazard|barrier)",
     "claims the flow entered or was destroyed by the barrier; no flow cell ever occupies "
     "the hazard row"),
    (r"failure\s+(screen|message|marking|indicator)|screen\s+appeared|"
     r"(flow|targets?)\s+(was|were)\s+reset|reset\s+of\s+the\s+(flow|targets?)",
     "claims a failure marking or reset appeared; the capture's last layer is one ordinary "
     "flow cell and a failing spill carries no failure colour"),
    (r"targets?\s+(were|was)\s+not\s+satisfied|not\s+all\s+targets?\s+(were|was)",
     "claims the targets were unsatisfied; both cups reach the satisfied appearance"),
)


# A COUNTERFACTUAL is not a claim. gemma4 says "if the animation HAD ended with a failure
# screen ... I WOULD have chosen terminate_fatal" — naming what was absent, which is the
# opposite of asserting it was there. The first version of this script flagged that as a
# contradiction on its very first run, which is what a checker does when it matches words
# instead of claims.
# NEGATION is not counterfactual framing. The first list held "no" and "not", which
# swallowed a genuine negative assertion — "the targets were not satisfied" is a claim about
# the animation and has to be checkable. Only the conditional markers belong here.
_HYPOTHETICAL = re.compile(r"\b(if|had|would|were\s+to|unless)\b", re.IGNORECASE)


def _asserted(sentence: str) -> bool:
    """Is this sentence stating what happened, rather than what did not or might have?"""
    return not _HYPOTHETICAL.search(sentence)


def check(text: str) -> list[str]:
    """Which checkable claims this explanation ASSERTS that the capture contradicts.

    Sentence by sentence, because an explanation routinely reports what it saw in one
    breath and what it did not in the next."""
    hits = []
    for sentence in re.split(r"(?<=[.;])\s+", text):
        if not _asserted(sentence):
            continue
        for pattern, why in CONTRADICTED:
            if re.search(pattern, sentence, re.IGNORECASE) and why not in hits:
                hits.append(why)
    return hits


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print("usage: explanation_check.py <r98_flow_fill_*.json> ...")
        return 1
    for path in paths:
        with open(path) as f:
            payload = json.load(f)
        seen: set = set()
        for run in payload.get("runs", []):
            text = run.get("explanation") or ""
            if not text or text in seen:
                continue
            seen.add(text)
            problems = check(text)
            print(f"\n== {path.stem}, run {run['run']} "
                  f"({run.get('slots', {}).get('hazard_response', '?')})")
            print(f"   {text.strip()[:600]}")
            if problems:
                for why in problems:
                    print(f"   ⛔ CONTRADICTED — {why}")
            else:
                print("   ✓ consistent with the capture — which says the REASON is not "
                      "false, not that the ANSWER is right")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
