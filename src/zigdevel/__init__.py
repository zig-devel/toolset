#!/usr/bin/env python3

import sys
import argparse
import logging

from rich.logging import RichHandler

from . import cmd_init
from . import cmd_inspect


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description="""
    Overseer is an automation tool within zig-devel.
    It should remain autonomous so that the infrastructure
    doesn't depend on the CI provider and everything can be done locally.
    """
    )
    parser.add_argument("--verbose", help="Verbose logging", action="store_true")

    subparsers = parser.add_subparsers(required=True, title="Overseer commands")
    cmd_init.cli(subparsers)
    cmd_inspect.cli(subparsers)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()],
    )
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    args.func(args)
