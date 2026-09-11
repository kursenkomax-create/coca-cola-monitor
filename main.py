from __future__ import annotations

from coca_monitor.config import load_config
from coca_monitor.monitor import Monitor


def main() -> None:
    """Run exactly one monitoring cycle.

    Railway Cron starts this process on schedule, so the program must finish
    after one cycle instead of sleeping in an internal loop.
    """
    cfg = load_config()
    monitor = Monitor(cfg)
    print("Coca-Cola Monitor: one-shot cycle started")
    try:
        monitor.run_once()
    finally:
        monitor.close()
    print("Coca-Cola Monitor: cycle finished")


if __name__ == "__main__":
    main()
