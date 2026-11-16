# SPDX-License-Identifier: Apache-2.0
"""Manual collection and static report commands."""
import argparse
import fcntl
from datetime import UTC, datetime
from pathlib import Path

from .collect import run
from .config import load
from .github import GitHub
from .metrics import build_report
from .render import publish
from .store import Store
from .timeutil import completed_month, month_ends, norm_ts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independent Apache Logging community activity reports")
    parser.add_argument("--config", type=Path, default=Path("config/logging.yaml"))
    parser.add_argument("--data", type=Path, default=Path("data/local"))
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="Read public sources and checkpoint internal snapshots")
    collect.add_argument("--as-of")
    collect.add_argument("--sample", type=int, metavar="ITEMS", help="Bounded sample per GitHub channel, labelled partial")
    collect.add_argument("--months", type=int, help="Explicit initial history window, up to configured history")
    collect.add_argument("--full", action="store_true", help="Reconcile complete sources, including deletions")
    collect.add_argument("--no-git", action="store_true")
    collect.add_argument("--no-mail", action="store_true")
    collect.add_argument("--projects", nargs="+")
    collect.add_argument("--request-budget", type=int, default=10000)
    render = sub.add_parser("render", help="Build a static report from local snapshots")
    render.add_argument("--as-of")
    render.add_argument("--output", type=Path, default=Path("site/logging"))
    render.add_argument("--allow-partial", action="store_true", help="Explicitly render incomplete data with coverage warnings")
    args = parser.parse_args(argv)
    config = load(args.config)
    store = Store(args.data)
    at = norm_ts(args.as_of or datetime.now(UTC).isoformat())
    if args.command == "collect":
        lock = (store.root / "collect.lock").open("w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("A collector already owns this data directory. Wait for it to finish.")
        if args.sample is not None and args.sample < 1:
            parser.error("--sample must be positive")
        if args.months is not None and not 1 <= args.months <= config["history_months"]:
            parser.error("--months must be between 1 and the configured history length")
        if args.projects and set(args.projects) - {p["id"] for p in config["projects"]}:
            parser.error("--projects contains an unknown project ID")
        if args.months:
            config["history_months"] = args.months
        start = completed_month(month_ends(at, config["history_months"])[0])[0]
        run(GitHub(args.request_budget), store, config, at, start, args.sample, args.full,
            not args.no_git, not args.no_mail, args.projects)
        failed = [source for source, info in store.state.items() if info["status"] in ("failed", "unavailable")]
        print(f"Checkpointed {len(store.state)} sources. {len(failed)} failed or unavailable.")
        return 1 if failed else 0
    report = build_report(store, config, at)
    if not args.allow_partial and any(s.get("status") not in ("complete", "disabled") for s in report["sources"].values()):
        parser.error("Incomplete sources remain. Inspect coverage or explicitly use --allow-partial for a local review.")
    if not report["sources"]:
        parser.error("No collected sources exist. Run collect first.")
    publish(report, args.output)
    print(args.output / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
