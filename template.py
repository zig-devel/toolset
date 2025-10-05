#!/usr/bin/env python3
"""
Creates a new project from a template.
Uses several global dependencies (including zig, reuse, and nvchecker).
"""

import os, sys, json, argparse, logging, subprocess
from pathlib import Path

GITHUB_ORG = "zig-devel"
INTERNAL_LICENSE = "0BSD"


def _WriteFile(filename: str, payload: str):
  """
  Writes a file discarding whitespace (a consequence of code formatting).
  Recursively creates the directory if it doesn't exist.
  """

  Path(filename).parent.mkdir(parents=True, exist_ok=True)

  payload = payload.lstrip('\n').rstrip()
  whitespaces = min([len(line) - len(line.lstrip(' ')) for line in payload.splitlines() if line.strip() != ""])

  with open(filename, "w") as fd:
    for line in payload.splitlines(keepends=True):
      if line.strip() != "":
        fd.write(line[whitespaces:]);
      else:
        fd.write(line);
    fd.write('\n')


def _SetupGitConfigs():
  _WriteFile(".gitattributes", f"""
    *.zig text eol=lf
    *.zon text eol=lf
  """)
  _WriteFile(".gitignore", f"""
    /.zig-cache
    /zig-out
  """)


def _SetupGithubActions():
  _WriteFile(".github/workflows/library.yml", f"""
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
        uses: {GITHUB_ORG}/.infra/.github/workflows/library.yml@main
  """)

  _WriteFile(".github/workflows/release.yml", f"""
    name: Prepare GH release

    on:
      push:
        tags: [ '*.*.*-*' ]

    jobs:
      release:
        name: Prepare GitHub release
        uses: {GITHUB_ORG}/.infra/.github/workflows/release.yml@main
        permissions:
          contents: write
  """)


def _SetupAutoUpdate(git: str):
  _WriteFile(".nvchecker.toml", f"""
    [__config__]
    oldver = ".github/oldver.json"
    newver = ".github/newver.json"

    [upstream]
    source = "git"
    git = "{git}"
    prefix = "v"
  """)

  os.system("nvchecker -c .nvchecker.toml")
  os.rename(".github/newver.json", ".github/oldver.json")

  git = git.removesuffix(".git").removesuffix("/")

  with open('.github/oldver.json') as f:
    manifest = json.load(f)
    upstream = manifest["data"]["upstream"]

    return upstream["version"], upstream["revision"]


def _SetupLicenses(project_licenses: list[str]):
  ptoject_licenses = [spdx for spdx in project_licenses if spdx != INTERNAL_LICENSE]
  project_licenses = [INTERNAL_LICENSE] + project_licenses

  _WriteFile("REUSE.toml", f"""
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
  """)

  os.system("reuse download --all")

  return project_licenses


def _SetupZigPackage(name: str, version: str, git: str, revision: str):
  os.system("zig init --minimal")

  _WriteFile("build.zig", f"""
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

        _ = mod;      // stub
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
  """)

  fingerprint = subprocess.check_output(['bash', '-c', "cat build.zig.zon | sed -n 's/\\s*\\.fingerprint = \\(.*\\),/\\1/p'"], text=True)

  _WriteFile("build.zig.zon", f"""
    .{{
        .name = .{name},
        .version = "{version}",
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
  """)

  archive_link = f"{git}/archive/{revision}.tar.gz"
  os.system(f"zig fetch --save={name} {archive_link}")

  _WriteFile("tests.zig", f"""
    const std = @import("std");

    const {name} = @cImport({{
        @cInclude("stdio.h");
    }});

    // Just a smoke test to make sure the library is linked correctly.
    test {{
    }}
  """)


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

  _WriteFile("README.md", f"""
    # [{name}]({url})@v{version} [![Build and test library]({ci_url }/badge.svg)]({ci_url})

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
  """)


def main(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument("--name", help="Library name", required=True)
  parser.add_argument("--description", help="Library description", required=True)
  parser.add_argument("--url", help="Project url", required=True)
  parser.add_argument("--git", help="Project gitrepo", required=True)
  parser.add_argument("--license", help="Library license SPDX identifier", nargs='+')
  parser.add_argument("--verbose", help="Verbose logging", action="store_true")

  args = parser.parse_args(argv)

  if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

  logging.debug(args.license)

  logging.info("Init repository")
  os.system(f'git init {args.name}')
  os.chdir(args.name)

  logging.info("Add Git configs")
  _SetupGitConfigs()

  logging.info("Add GitHubActions configs")
  _SetupGithubActions()

  logging.info("Add autoupdate configs")
  version, revision = _SetupAutoUpdate(args.git)

  logging.info("Add licenses")
  licenses = _SetupLicenses(args.license)

  logging.info("Setup zig package")
  _SetupZigPackage(args.name, version, args.git, revision)

  logging.info("Add readme")
  _SetupDocs(args.name, args.description, args.url, version, licenses)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
