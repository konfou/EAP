"""Run metrics job or backfill."""

import argparse
from datetime import date

from jobs.metrics.job import backfill, run


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute daily metrics")
    parser.add_argument("--start", type=str, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="Backfill end date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.start and args.end:
        backfill(date.fromisoformat(args.start), date.fromisoformat(args.end))
    elif args.start or args.end:
        raise ValueError("Provide both --start and --end for backfill")
    else:
        run()


if __name__ == "__main__":
    main()
