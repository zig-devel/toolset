from dataclasses import dataclass

import requests


@dataclass
class Repository:
    name: str

    private: bool
    archived: bool
    is_template: bool

    clone_url: str
    default_branch: str

    has_issues: bool
    has_wiki: bool
    has_pages: bool
    has_projects: bool
    has_discussions: bool

    created_at: str
    updated_at: str
    open_issues_count: int

    def is_active(self):
        return not self.private and not self.archived


class GitHub:
    org = "zig-devel"
    token = None

    github_repository = ".github"
    toolset_repository = "toolset"
    internal_repositories = {github_repository, toolset_repository}

    def __init__(self, *, org, token):
        if org is not None:
            self.org = org
        if org is not None:
            self.token = token

    def is_repo_package(self, repo: Repository) -> bool:
        return repo.is_active() and repo.name not in self.internal_repositories

    def get_package_url(self, name: str) -> str:
        return f"https://github.com/{self.org}/{name}"

    def get_package_remote(self, name: str) -> str:
        return f"git@github.com:{self.org}/{name}.git"

    def get_package_ci_url(self, name: str) -> str:
        url = self.get_package_url(name)
        return f"{url}/actions/workflows/library.yml"

    def get_package_archive(self, name: str, version: str) -> str:
        url = self.get_package_url(name)
        return f"zig fetch --save {url}/archive/refs/tags/{version}.tar.gz"

    def get_ci_file(self) -> (str, str):
        filename = ".github/workflows/library.yml"
        content = f"""
        name: Build and test library

        on:
          push:
            branches: [main]
            tags: [ '*.*.*-*' ]
          pull_request:
            branches: [main]
            types: [opened, synchronize]
          workflow_dispatch:

        jobs:
          build:
            name: Build and test library
            uses: {self.org}/{self.toolset_repository}/.github/workflows/_library.yml@latest
            permissions:
              contents: write
        """
        return filename, content

    def fetch_repos(self) -> list[Repository]:
        repositories = []

        url = f"https://api.github.com/orgs/{self.org}/repos"
        hdrs = {} if self.token is None else {"Authorization": f"Bearer {self.token}"}

        page = 1
        while True:
            params = {"per_page": 100, "page": page}

            resp = requests.get(url, params=params, headers=hdrs, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if len(data) <= 0:
                break

            repositories += [
                Repository(
                    name=it["name"],
                    private=it["private"],
                    archived=it["archived"],
                    is_template=it["is_template"],
                    clone_url=it["clone_url"],
                    default_branch=it["default_branch"],
                    has_issues=it["has_issues"],
                    has_wiki=it["has_wiki"],
                    has_pages=it["has_pages"],
                    has_projects=it["has_projects"],
                    has_discussions=it["has_discussions"],
                    created_at=it["created_at"],
                    updated_at=it["updated_at"],
                    open_issues_count=it["open_issues_count"],
                )
                for it in data
            ]
            page += 1

        return repositories
