import argparse
import json
import logging
import os
import sys
import shutil
from pathlib import Path
from dataclasses import asdict

from plumbum import local
from plumbum.cmd import git

from .common import nvchecker, nvcmp
from .github import GitHub, Repository


class PkgSettingsException(Exception):
    pass


class PkgOutdatedException(Exception):
    pass


def inspect_package(args, gh: GitHub, repo: Repository):
    if not repo.is_active() or repo.name in gh.internal_repositories:
        return

    logging.info(f"Check {repo.name} repository config...")

    git_dir = os.path.join(args.cache_dir, repo.name)

    if os.path.exists(git_dir):
        logging.debug("Update cached repository")
        with local.cwd(local.cwd / git_dir):
            git["fetch", "-q", "origin"]()
            git["reset", "-q", "--hard", f"origin/{repo.default_branch}"]()
            git["clean", "-q", "-xd", "--force"]()
    else:
        logging.debug("Clone repository")
        git[
            "clone",
            "--depth",
            "1",
            "--branch",
            repo.default_branch,
            repo.clone_url,
            git_dir,
        ]()

    if args.check_repository_settings:
        if repo.default_branch != "main":
            raise PkgSettingsException(
                f"Default branch must me 'main' not {repo.default_branch}"
            )
        if repo.is_template:
            raise PkgSettingsException("Repository should not be a template")

        if not repo.has_issues:
            raise PkgSettingsException("Issues must be enabled")
        if repo.has_wiki:
            raise PkgSettingsException("Wiki must be disabled")
        if repo.has_pages:
            raise PkgSettingsException("Pages must be disabled")
        if repo.has_projects:
            raise PkgSettingsException("Projects must be disabled")
        if repo.has_discussions:
            raise PkgSettingsException("Discussions must be disabled")

    if args.check_updates:
        with local.cwd(local.cwd / git_dir):
            nvchecker["-c", ".nvchecker.toml"]()

            if nvcmp["-c", ".nvchecker.toml"]() != "":
                raise PkgOutdatedException(f"'{repo.name}' has new version")


def run(args, github: GitHub):
    if args.clear_cache:
        shutil.rmtree(args.cache_dir, ignore_errors=True)

    repos_file = os.path.join(args.cache_dir, "repos.jsonl")

    if os.path.exists(args.cache_dir):
        logging.info(f"Use cached repos list from {args.cache_dir}")
    else:
        Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
        with open(repos_file, "w", encoding="utf-8") as fd:
            repos = github.fetch_repos()
            json.dump([asdict(it) for it in repos], fd)

    with open(repos_file, "r", encoding="utf-8") as fd:
        repos = json.load(fd)
        for repo in repos:
            try:
                inspect_package(args, github, Repository(**repo))
            except (PkgSettingsException, PkgOutdatedException) as err:
                logging.error(err)
                sys.exit(1)


def cli(subparsers):
    parser = subparsers.add_parser(
        "scan",
        help="Scan all packages and looks for potential errors",
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
    parser.add_argument("--cache-dir", help="Cache directory", default=".zd_cache")
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
