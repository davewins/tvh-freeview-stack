import argparse
import logging
import sys

from . import __version__, config, runner
from .state import State
from .tvheadend import Tvheadend
import os


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tvhpipeline", description="Recording pipeline for Tvheadend + Jellyfin")
    p.add_argument("command", choices=["run", "once", "status", "cleanup-dry-run", "version"], help="run = loop forever; once = one pass; status = what has been done")
    p.add_argument("--config", help="path to config.toml")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    if a.command == "version":
        print(__version__)
        return 0
    cfg = config.load(a.config)
    if a.command == "run":
        runner.loop(cfg)
        return 0
    os.makedirs(cfg.state_dir, exist_ok=True)
    state = State(os.path.join(cfg.state_dir, "state.db"))
    if a.command == "status":
        try:
            print("NOW:", open(os.path.join(cfg.state_dir, "activity")).read())
        except OSError:
            print("NOW: idle")
        for step, status, n in state.summary():
            print("%-14s %-11s %d" % (step, status, n))
        for rec, step, detail, attempts in state.failures():
            print("FAILED %s %s (attempt %d): %s" % (rec[:8], step, attempts, detail))
        return 0
    if a.command == "cleanup-dry-run":
        from .steps import cleanup
        print(cleanup.run(cfg, dry_run=True))
        return 0
    print(runner.cycle(cfg, state, Tvheadend(cfg.tvh_url, cfg.tvh_user, cfg.tvh_pass)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
