from __future__ import annotations

import sys, time


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "help"
    if cmd == "help":
        print("usage: python3 -m gardener [run|migrate|status]")
        return 0
    if cmd == "run":
        from pathlib import Path
        from .config import config_for
        from .runner import run_once
        summary = run_once(config_for(Path.home()), now=time.time())
        print(f"garden: {summary}")
        return 0
    if cmd == "migrate":
        from .config import config_for
        from .migrate import migrate as _migrate
        from pathlib import Path
        import datetime
        # date passed explicitly to keep the function pure/testable
        out = _migrate(config_for(Path.home()),
                       now_date=datetime.date.today().isoformat())
        print(f"migrate: {out}")
        return 0
    if cmd == "status":
        from .config import config_for
        from .status import collect
        from pathlib import Path
        import time, json
        print(json.dumps(collect(config_for(Path.home()), now=time.time()), indent=2))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
