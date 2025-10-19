import json
import logging
import os
from pathlib import Path

from plumbum.cmd import cat, sed, git

from .common import cmd, console
from .common import reuse, nvchecker
from .common import GITHUB_ORG, GITHUB_REPO_TOOLSET, INTERNAL_LICENSE


def _WriteFile(filename: str, payload: str):
    """
    Writes a file discarding whitespace (a consequence of code formatting).
    Recursively creates the directory if it doesn't exist.
    """

    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    payload = payload.lstrip("\n").rstrip()
    whitespaces = min(
        [
            len(line) - len(line.lstrip(" "))
            for line in payload.splitlines()
            if line.strip() != ""
        ]
    )

    with open(filename, "w") as fd:
        for line in payload.splitlines(keepends=True):
            if line.strip() != "":
                fd.write(line[whitespaces:])
            else:
                fd.write(line)
        fd.write("\n")


def _SetupGitConfigs(name: str):
    logging.info("Generate .gitattributes")
    _WriteFile(
        ".gitattributes",
        """
            *.zig text eol=lf
            *.zon text eol=lf
        """,
    )

    logging.info("Generate .gitignore")
    _WriteFile(
        ".gitignore",
        """
        /.zig-cache
        /zig-out
        """,
    )

    logging.info("Set git origin")
    cmd(git["remote", "add", "origin", f"git@github.com:{GITHUB_ORG}/{name}.git"])


def _SetupGithubActions():
    logging.info("Generate library build workflow")
    _WriteFile(
        ".github/workflows/library.yml",
        f"""
        name: Build and test library

        on:
          push:
            branches: [main]
          pull_request:
            branches: [main]
            types: [opened, synchronize]
          workflow_dispatch:

        jobs:
          build:
            name: Build and test library
            uses: {GITHUB_ORG}/{GITHUB_REPO_TOOLSET}/.github/workflows/_library.yml@latest
            permissions:
                contents: write
        """,
    )


def _SetupAutoUpdate(git: str):
    logging.info("Generate nvchecker config")
    _WriteFile(
        ".nvchecker.toml",
        f"""
        [__config__]
        oldver = ".github/oldver.json"
        newver = ".github/newver.json"

        [upstream]
        source = "git"
        git = "{git}"
        prefix = "v"
        """,
    )

    logging.info("Fetch latest version")

    cmd(nvchecker["-c", ".nvchecker.toml", "-l", "error"])
    os.rename(".github/newver.json", ".github/oldver.json")

    git = git.removesuffix(".git").removesuffix("/")

    with open(".github/oldver.json") as f:
        manifest = json.load(f)
        upstream = manifest["data"]["upstream"]

        logging.info(f"Latest version detected: {upstream}")
        return upstream["version"], upstream["revision"]


def _SetupLicenses(project_licenses: list[str]):
    project_licenses = [spdx for spdx in project_licenses if spdx != INTERNAL_LICENSE]
    project_licenses = [INTERNAL_LICENSE] + project_licenses

    logging.info(f"Detected licenses: {project_licenses}")

    logging.info("Generate reuse config")
    _WriteFile(
        "REUSE.toml",
        f"""
        version = 1

        [[annotations]]
        path = [
            "README.md",
            "REUSE.toml",
            "tests.zig",
            "build.zig",
            "build.zig.zon",
            ".nvchecker.toml",
            ".gitignore",
            ".gitattributes",
            ".github/**/*.yml",
            ".github/oldver.json",
            ".github/newver.json",
        ]
        SPDX-FileCopyrightText = "Zig Devel contributors"
        SPDX-License-Identifier = "{" OR ".join(project_licenses)}"
        """,
    )

    logging.info("Download licenses files...")
    cmd(reuse["download", "--all"])

    return project_licenses


def _SetupZigPackage(name: str, version: str, git: str, revision: str):
    from plumbum.cmd import zig  # zig is not installed by default

    logging.info("Init zig package")
    cmd(zig["init", "--minimal"])

    fingerprint = (
        cat["build.zig.zon"] | sed["-n", "s/\\s*\\.fingerprint = \\(.*\\),/\\1/p"]
    )().strip()
    logging.info(f"Detect project fingerprint: {fingerprint}")

    logging.info("Generate build.zig boilerplate")
    _WriteFile(
        "build.zig",
        f"""
        const std = @import("std");

        pub fn build(b: *std.Build) void {{
            const target = b.standardTargetOptions(.{{}});
            const optimize = b.standardOptimizeOption(.{{}});

            const upstream = b.dependency("{name}", .{{}});

            const mod = b.createModule(.{{
                .link_libc = true,
                .target = target,
                .optimize = optimize,
            }});

            _ = mod; // stub
            _ = upstream; // stub

            // Smoke unit test
            const test_mod = b.addModule("test", .{{
                .root_source_file = b.path("tests.zig"),
                .target = target,
                .optimize = optimize,
            }});
            // TODO: mod.linkLibrary(lib);

            const run_mod_tests = b.addRunArtifact(b.addTest(.{{ .root_module = test_mod }}));

            const test_step = b.step("test", "Run tests");
            test_step.dependOn(&run_mod_tests.step);
        }}
        """,
    )

    logging.info("Generate build.zig.zon boilerplate")
    _WriteFile(
        "build.zig.zon",
        f"""
        .{{
            .name = .{name},
            .version = "{version}-0",
            .fingerprint = {fingerprint}, // Changing this has security and trust implications.
            .minimum_zig_version = "0.15.1",
            .dependencies = .{{}},
            .paths = .{{
                "LICENSES/",
                "REUSE.toml",
                "README.md",
                "tests.zig",
                "build.zig",
                "build.zig.zon",
            }},
        }}
        """,
    )

    logging.info("Generate tests.zig boilerplate")
    _WriteFile(
        "tests.zig",
        f"""
        const std = @import("std");

        const {name} = @cImport({{
            @cInclude("stdio.h");
        }});

        // Just a smoke test to make sure the library is linked correctly.
        test {{}}
        """,
    )

    git = git.removesuffix(".git").removesuffix("/")
    archive_link = f"{git}/archive/{revision}.tar.gz"

    logging.info(f"Download upstream sources from {archive_link}")
    cmd(zig["fetch", f"--save={name}", archive_link])


def _Licenselink(spdx: str):
    return f"[{spdx}](./LICENSES/{spdx}.txt)"


def _SetupDocs(name: str, desc: str, url: str, version: str, licenses: list[str]):
    gh_url = f"https://github.com/{GITHUB_ORG}/{name}"
    ci_url = f"{gh_url}/actions/workflows/library.yml"

    spdx_list = " OR ".join([_Licenselink(spdx) for spdx in licenses])

    prefix = ""
    if len(spdx_list) > 2:
        prefix = "multi-"
    elif len(spdx_list) > 1:
        prefix = "double-"

    _WriteFile(
        "README.md",
        f"""
        # [{name}]({url})@v{version} [![Build and test library]({ci_url}/badge.svg)]({ci_url})

        {desc}

        ## Usage

        Install library:

        ```sh
        zig fetch --save {gh_url}/archive/refs/tags/{version}-0.tar.gz
        ```

        Statically link with `mod` module:

        ```zig
        const {name} = b.dependency(\"{name}\", .{{
            .target = target,
            .optimize = optimize,
        }});

        mod.linkLibrary({name}.artifact(\"{name}\"));
        ```

        ## License

        All code in this repo is {prefix}licensed under {spdx_list}.
        """,
    )


def run(args):
    console.print("[bold]Init git repository...[/bold]")
    cmd(git["init", args.name])
    os.chdir(args.name)

    console.print("[bold]Setup git configs...[/bold]")
    _SetupGitConfigs(args.name)

    console.print("[bold]Setup GitHub Actions...[/bold]")
    _SetupGithubActions()

    console.print("[bold]Configure nvchecker...[/bold]")
    version, revision = _SetupAutoUpdate(args.git)

    console.print("[bold]Configure licenses...[/bold]")
    licenses = _SetupLicenses(args.license)

    console.print("[bold]Init zig package...[/bold]")
    _SetupZigPackage(args.name, version, args.git, revision)

    console.print("[bold]Generate readme...[/bold]")
    _SetupDocs(args.name, args.description, args.url, version, licenses)

    logging.info("Commit template")
    cmd(git["add", "."])
    cmd(git["commit", "-am", "ZD: init library repository from template"])


def cli(subparsers):
    parser = subparsers.add_parser(
        "init",
        help="Initializes a new library from a template",
    )
    parser.add_argument("--name", help="Library name", required=True)
    parser.add_argument("--description", help="Library description", required=True)
    parser.add_argument("--url", help="Project url", required=True)
    parser.add_argument("--git", help="Project gitrepo", required=True)
    parser.add_argument("--license", help="Library license SPDX identifier", nargs="+")

    parser.set_defaults(func=run)
