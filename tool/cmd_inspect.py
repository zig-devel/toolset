import argparse
import json
import logging
import os
import sys
import shutil
from pathlib import Path

from plumbum import local
from plumbum.cmd import curl, jq, git, nvchecker, nvcmp
from rich.console import Console

console = Console()

GITHUB_ORG = "zig-devel"

_CWD = os.path.dirname(os.path.abspath(__file__))


class PkgSettingsException(Exception):
    pass


class PkgOutdatedException(Exception):
    pass


def fetch_repositories(args, fd):
    page = 1
    while True:
        api_url = f"https://api.github.com/orgs/{args.github_org}/repos?per_page=100&page={page}"
        api_bearer = (
            f"Authorization: Bearer {args.github_token}"
            if args.github_token != ""
            else ""
        )

        response = (
            curl["-s", "--fail-with-body", "-H", api_bearer, api_url]
            | jq["-r", "-c", ".[]"]
        )().strip()
        if response == "":
            break

        fd.write(response)
        fd.write("\n")

        page += 1


def inspect_package(args, line):
    if not line:
        return

    lib = json.loads(line)

    if lib["name"].startswith(".") or lib["private"] or lib["archived"]:
        return

    logging.info(f"Check {lib['name']} repository config...")

    git_dir = os.path.join(args.cache_dir, lib["name"])

    if os.path.exists(git_dir):
        logging.debug("Update cached repository")
        with local.cwd(local.cwd / git_dir):
            git["fetch", "-q", "origin"]()
            git["reset", "-q", "--hard", f"origin/{lib['default_branch']}"]()
            git["clean", "-q", "-xd", "--force"]()
    else:
        logging.debug("Clone repository")
        git[
            "clone",
            "--depth",
            "1",
            "--branch",
            lib["default_branch"],
            lib["clone_url"],
            git_dir,
        ]()

    if args.check_repository_settings:
        if lib["default_branch"] != "main":
            raise PkgSettingsException(
                f"Default branch must me 'main' not {lib['default_branch']}"
            )
        if lib["is_template"]:
            raise PkgSettingsException("Repository should not be a template")

        if not lib["has_issues"]:
            raise PkgSettingsException("Issues must be enabled")
        if lib["has_wiki"]:
            raise PkgSettingsException("Wiki must be disabled")
        if lib["has_pages"]:
            raise PkgSettingsException("Pages must be disabled")
        if lib["has_projects"]:
            raise PkgSettingsException("Projects must be disabled")
        if lib["has_discussions"]:
            raise PkgSettingsException("Discussions must be disabled")

    if args.check_updates:
        with local.cwd(local.cwd / git_dir):
            nvchecker["-c", ".nvchecker.toml"]()

            if nvcmp["-c", ".nvchecker.toml"]() != "":
                raise PkgOutdatedException(f"'{lib['name']}' has new version")


def run(args):
    if args.clear_cache:
        shutil.rmtree(args.cache_dir, ignore_errors=True)

    repos_file = os.path.join(args.cache_dir, "repos.jsonl")

    if os.path.exists(args.cache_dir):
        logging.info(f"Use cached repos list from {args.cache_dir}")
    else:
        Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
        with open(repos_file, "w", encoding="utf-8") as fd:
            fetch_repositories(args, fd)

    with open(repos_file, "r", encoding="utf-8") as fd:
        for line in fd:
            try:
                inspect_package(args, line.strip())
            except (PkgSettingsException, PkgOutdatedException) as err:
                logging.error(err)
                sys.exit(1)


def cli(subparsers):
    parser = subparsers.add_parser(
        "inspect",
        help="Checks each packet and looks for potential errors",
        description="""
        This script crawls all repositories and performs general checks
        such as repository formatting and searching for new versions.

        This is done centrally, rather than separately in each repository,
        to reduce the amount of bolt-on code. GH doesn't support centralized rules,
        so you'll need to copy the rules to each repository.

        Actual checks:
        - repository settings
        - new version from upstream
        """,
    )
    parser.add_argument("--github-org", help="Github organization", default=GITHUB_ORG)
    parser.add_argument("--github-token", help="Github API token", required=False)
    parser.add_argument(
        "--cache-dir", help="Cache directory", default=".overseer_cache"
    )
    parser.add_argument(
        "--clear-cache",
        help="Clear repos cache",
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-updates",
        help="Check packages updates",
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--check-repository-settings",
        help="Check packages repo settings",
        default=True,
        action=argparse.BooleanOptionalAction,
    )

    parser.set_defaults(func=run)
