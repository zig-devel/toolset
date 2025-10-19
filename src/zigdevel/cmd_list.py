from rich.table import Table

from .common import console
from .github import GitHub


def run(args, github: GitHub):
    table = Table()

    table.add_column("Name")
    table.add_column("Url")
    table.add_column("Updated")
    table.add_column("Issues")

    repos = github.fetch_repos()
    for repo in repos:
        if github.is_repo_package(repo):
            table.add_row(
                repo.name,
                github.get_package_url(repo.name),
                repo.updated_at,
                str(repo.open_issues_count),
            )

    console.print(table)


def cli(subparsers):
    parser = subparsers.add_parser("list", help="Print packages list")
    parser.set_defaults(func=run)
