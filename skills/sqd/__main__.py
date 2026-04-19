"""SQD CLI entry point: python -m sqd dispatch ..."""

import argparse
import asyncio
import sys
from pathlib import Path

from skills.sqd.layers.dispatcher import dispatch_parallel, MODELS


def main() -> int:
    parser = argparse.ArgumentParser(prog="sqd", description="SDLC Quality Dispatcher")
    sub = parser.add_subparsers(dest="command")

    dispatch = sub.add_parser("dispatch", help="Dispatch parallel adversarial review")
    dispatch.add_argument("--target", required=True, help="Artifact path or description")
    dispatch.add_argument(
        "--models",
        nargs="+",
        default=["deepseek", "gemini", "claude"],
        choices=list(MODELS),
        help="LLM providers to dispatch",
    )
    dispatch.add_argument(
        "--output",
        default="findings",
        help="Output directory for findings",
    )

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0

    output_dir = Path(args.output)
    return asyncio.run(
        dispatch_parallel(args.target, args.models, output_dir)
    )


if __name__ == "__main__":
    sys.exit(main())
