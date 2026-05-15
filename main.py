"""Behavioural Business Signals — main entrypoint.

Usage:
    python main.py score --financial
    python main.py score --behavioural
    python main.py score --all
    python main.py ui
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _print_score_table(df, score_col: str) -> None:
    """Print a summary table of scores to the terminal.

    Args:
        df: Scored DataFrame containing ticker, company_name, and score_col.
        score_col: Name of the score column to display.
    """
    try:
        from tabulate import tabulate
    except ImportError:
        logger.warning("tabulate not installed — skipping summary table")
        print(df[["ticker", "company_name", score_col]].to_string(index=False))
        return

    display_cols = ["ticker", "company_name", score_col]
    available = [c for c in display_cols if c in df.columns]
    print(
        tabulate(
            df[available].sort_values(score_col, ascending=False),
            headers="keys",
            tablefmt="rounded_outline",
            showindex=False,
            floatfmt=".2f",
        )
    )


def cmd_score(args: argparse.Namespace) -> None:
    """Run one or both scorers based on CLI flags.

    Args:
        args: Parsed argparse namespace with boolean flags financial, behavioural, all.
    """
    run_financial = args.financial or args.all
    run_behavioural = args.behavioural or args.all

    if not run_financial and not run_behavioural:
        logger.error("Specify at least one of --financial, --behavioural, or --all")
        sys.exit(1)

    if run_financial:
        logger.info("Running financial collector")
        from collectors import financial_collector
        raw_df = financial_collector.fetch_all_companies()
        financial_collector.save_financial_data(raw_df)

        logger.info("Running financial scorer")
        from processors import financial_scorer
        df = financial_scorer.run()
        if not df.empty:
            print("\nFinancial Scores:")
            _print_score_table(df, "financial_score")

    if run_behavioural:
        logger.info("Running behavioural scorer")
        from processors import behavioural_scorer
        df = behavioural_scorer.run()
        if not df.empty:
            print("\nBehavioural Scores:")
            _print_score_table(df, "behavioural_score")


def cmd_collect(args: argparse.Namespace) -> None:
    """Run one or more data collectors based on CLI flags.

    Args:
        args: Parsed argparse namespace with boolean flags trends, reddit, all.
    """
    run_trends = args.trends or args.all
    run_reddit = args.reddit or args.all

    if not run_trends and not run_reddit:
        logger.error("Specify at least one of --trends, --reddit, or --all")
        sys.exit(1)

    if run_trends:
        logger.info("Running Google Trends collector")
        from collectors import trends_collector
        df = trends_collector.run()
        if not df.empty:
            print(f"\nGoogle Trends collected for {len(df)} companies.")

    if run_reddit:
        logger.info("Running Reddit sentiment collector")
        from collectors import reddit_collector
        df = reddit_collector.run()
        if not df.empty:
            print(f"\nReddit sentiment collected for {len(df)} companies.")


def cmd_ui(args: argparse.Namespace) -> None:
    """Launch the Flask web UI.

    Args:
        args: Parsed argparse namespace (unused but included for consistency).
    """
    import config
    logger.info("Starting Flask UI at http://%s:%d", config.UI_HOST, config.UI_PORT)
    from ui.app import create_app
    flask_app = create_app()
    flask_app.run(host=config.UI_HOST, port=config.UI_PORT, debug=config.UI_DEBUG)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Behavioural Business Signals — dual-score analytics for beauty & fashion companies",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score", help="Run the scoring pipeline")
    score_parser.add_argument("--financial", action="store_true", help="Run financial scorer")
    score_parser.add_argument("--behavioural", action="store_true", help="Run behavioural scorer")
    score_parser.add_argument("--all", action="store_true", help="Run both scorers")

    collect_parser = subparsers.add_parser("collect", help="Run data collectors")
    collect_parser.add_argument("--trends", action="store_true", help="Run Google Trends collector")
    collect_parser.add_argument("--reddit", action="store_true", help="Run Reddit sentiment collector")
    collect_parser.add_argument("--all", action="store_true", help="Run all collectors")

    subparsers.add_parser("ui", help="Launch the Flask web UI")

    return parser


def main() -> None:
    """Parse arguments and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "score":
        cmd_score(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "ui":
        cmd_ui(args)


if __name__ == "__main__":
    main()
