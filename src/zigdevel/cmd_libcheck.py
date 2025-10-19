import re
import json
import logging
import argparse

from plumbum import local
from plumbum.cmd import cat, git, sed, head, grep

from .github import GitHub
from .common import cmd, console


def check_versioning(reference: str) -> None:
    number_regex = "(0|[1-9][0-9]*)"  # valid: 0, 42; invalid: 00 or 08
    version_regex = f"^{number_regex}\.{number_regex}\.{number_regex}-{number_regex}$"

    # Consider the version in the manifesto to be correct because it must be
    package_ref = sed["-n", 's/\s*\.version\s*=\s*"\(.*\)",/\\1/p', "build.zig.zon"]()
    package_ref = package_ref.strip()

    upstream_version = re.sub(f"-{number_regex}$", "", package_ref).strip()

    logging.info(f"Detected package version {package_ref}")
    logging.info(f"Detected upstream version {upstream_version}")

    if re.search(version_regex, package_ref) is None:
        logging.error(f"Invalid version in build.zig.zon: version={package_ref}")
        exit(1)

    # Compare package_ref and reference version
    if reference and reference != package_ref:
        logging.error(
            f"Version from build.zig.zon and reference does not match: package_ref={package_ref}, reference={reference}."
        )
        exit(1)

    # Compare package_ref and version in git tag
    gittag_ref = (git["tag", "--sort=-authordate", "--merged=HEAD"] | head["-1"])()
    gittag_ref = gittag_ref.strip()

    if gittag_ref and gittag_ref != package_ref:
        logging.error(
            f"Version from build.zig.zon and git tag does not match: package_ref={package_ref}, gittag_ref={gittag_ref}."
        )
        exit(1)

    # Check version in nvchecker config
    with open(".github/oldver.json") as fd:
        data = json.load(fd)
        version = data["data"]["upstream"]["version"]

        if upstream_version != version:
            logging.error(
                f"Incorrect upstream version in nvchecker config, upstream_version={upstream_version}, nvchecker={version}."
            )
            exit(1)

    # Check version in readme header
    readme_version = (
        cat["README.md"] | head["-1"] | sed["-n", "s/^# .*@v\([0-9.]*\).*/\\1/p"]
    )().strip()

    if upstream_version != readme_version:
        logging.error(
            f"The readme header contains an incorrect upstream version: upstream_version={upstream_version}, readme_version={readme_version}."
        )
        exit(1)

    # Check version in install doc
    (returncode, _, _) = grep[
        "-q",
        f"^zig fetch --save .*/archive/refs/tags/{package_ref}.tar.gz$",
        "README.md",
    ].run(retcode=None)
    if returncode != 0:
        logging.error("Incorrect version in installation documentation.")
        exit(1)


def make_triplets(os: str, arches, modes=[]):
    triplets = []

    for arch in arches:
        base = f"{arch}-{os}"
        for mode in modes:
            triplets.append(f"{base}-{mode}")
        else:
            triplets.append(base)

    return triplets


def build(zig, triplet, optimize):
    logging.info(f"Build {triplet}\t{optimize}")
    args = [
        "--prefix",
        f"zig-out/{triplet}/{optimize}",
        f"-Dtarget={triplet}",
        f"-Doptimize={optimize}",
    ]
    cmd(zig["build", "--summary", "all", *args], withstderr=True, todebug=True)


def crosscompile(zig):
    # In theory, there could be issues with other modes, but that's unlikely.
    # On the other hand, it doubles the build time.
    # ["ReleaseFast", "ReleaseSmall"]
    modes = ["Debug", "ReleaseSafe"]

    triplets = [
        *make_triplets("macos", ["x86_64", "aarch64"]),
        *make_triplets("windows", ["x86_64", "aarch64"]),
        *make_triplets("linux", ["x86_64", "aarch64"], ["gnu", "musl"]),
        *make_triplets("netbsd", ["x86_64"]),
        *make_triplets("freebsd", ["x86_64"]),
    ]

    for triplet in triplets:
        for optimize in modes:
            build(zig, triplet, optimize)


def run(args, github: GitHub):
    zig = local.get("zig")
    if zig is None:
        logging.error("Zig not found")
        exit(1)

    console.print("[bold]Check versions consistency...[/bold]")
    check_versioning(args.reference)

    console.print("[bold]Build by matrix...[/bold]")
    crosscompile(zig)

    if args.run_tests:
        console.print("[bold]Unit tests...[/bold]")
        cmd(
            zig["build", "test", "--summary", "all", "-Doptimize=ReleaseSafe"],
            withstderr=True,
        )


def cli(subparsers):
    parser = subparsers.add_parser("libcheck", help="Build and tests one library")
    parser.add_argument("--reference", help="Reference version tag", required=False)
    parser.add_argument(
        "--run-tests",
        help="Run unit tests",
        default=True,
        action=argparse.BooleanOptionalAction,
    )

    parser.set_defaults(func=run)
