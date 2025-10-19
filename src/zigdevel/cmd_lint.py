import logging
import argparse

from plumbum import local
from plumbum.cmd import find
from plumbum.commands.processes import CommandNotFound

from .github import GitHub
from .common import cmd, console


def cmd_find(name, strict=False):
    try:
        return local.get(name)
    except CommandNotFound:
        if strict:
            logging.error(f"Command not found: {name}")
            exit(1)
        else:
            logging.warning(f"Command not found: {name}")
    return None


def lint_sh(args):
    shellcheck = cmd_find("shellcheck", args.strict)
    if shellcheck is not None:
        cmd(
            find[".", "-name", "*.sh", "-exec", shellcheck, "--color=always", "{}", "+"]
        )


def lint_py(args):
    ruff = cmd_find("ruff", args.strict)
    if ruff is not None:
        cmd(ruff["check"])
        cmd(ruff["format", "--check"])


def lint_md(args):
    npx = cmd_find("npx", args.strict)
    if npx is None:
        return

    # TODO: maybe it's worth looking for a locally installed version?
    cmd(npx["-y", "markdownlint-cli2@0.18.1", "*.md"])


def lint_zig(args):
    zig = cmd_find("zig", args.strict)
    if zig is not None:
        cmd(zig["fmt", "--ast-check", "--check", "."])
        logging.info("All checks passed!")


def lint_licenses(args):
    reuse = cmd_find("reuse", args.strict)
    if reuse is not None:
        cmd(reuse["lint"])


def run(args, github: GitHub):
    if args.check_sh:
        console.print("[bold]Run shell linter...[/bold]")
        lint_sh(args)

    if args.check_py:
        console.print("[bold]Run python linter...[/bold]")
        lint_py(args)

    if args.check_md:
        console.print("[bold]Run markdown linter...[/bold]")
        lint_md(args)

    if args.check_zig:
        console.print("[bold]Run zig linter...[/bold]")
        lint_zig(args)

    if args.check_licenses:
        console.print("[bold]Run licenses linter...[/bold]")
        lint_licenses(args)


def cli(subparsers):
    parser = subparsers.add_parser(
        "lint",
        help="Runs a common set of linters and formatters on files in the current directory",
    )
    parser.add_argument(
        "--strict",
        help="Error if external utility is unavailable",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-sh",
        help="Toggle shell linter",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-py",
        help="Toggle python linter",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-md",
        help="Toggle markdown linter",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-zig",
        help="Toggle zig linter",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-licenses",
        help="Toggle licenses linter",
        default=True,
        action=argparse.BooleanOptionalAction,
    )

    parser.set_defaults(func=run)
