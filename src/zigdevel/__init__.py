#!/usr/bin/env python3

import sys
import argparse
import logging

from rich.logging import RichHandler

from .github import GitHub

from . import cmd_lint
from . import cmd_scan
from . import cmd_libinit
from . import cmd_libcheck


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description="""
        Overseer is an automation tool within zig-devel.
        It should remain autonomous so that the infrastructure
        doesn't depend on the CI provider and everything can be done locally.
        """
    )
    parser.add_argument("--verbose", help="Verbose logging", action="store_true")
    parser.add_argument("--github-org", help="Github organization", required=False)
    parser.add_argument("--github-token", help="Github API token", required=False)

    subparsers = parser.add_subparsers(required=True, title="Commands")
    cmd_lint.cli(subparsers)
    cmd_scan.cli(subparsers)
    cmd_libinit.cli(subparsers)
    cmd_libcheck.cli(subparsers)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()],
    )
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    github = GitHub(org=args.github_org, token=args.github_token)
    args.func(args, github)
