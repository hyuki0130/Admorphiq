#!/usr/bin/env python3
"""Prove pfan.sh runs the SNAPSHOT's src, not the box's shared copy.

⛔ It reports the FILE admorphiq was imported from, not a pass/fail. `ptest.sh` and `pfan.sh` were
both caught measuring `/home/ubuntu/admorphiq/src` while appearing to work, because the venv installs
admorphiq editable and the `.pth` wins over an unset PYTHONPATH (rule 7n). A green tick cannot tell
those apart; a path can.
"""
import json
import sys

import admorphiq


def main() -> None:
    print(json.dumps({"seed": sys.argv[1] if len(sys.argv) > 1 else None,
                      "admorphiq_from": admorphiq.__file__}))


if __name__ == "__main__":
    main()
