import os
import sys
import logging

from plumbum import local
from rich.console import Console

TOOLSET_LICENSE = "AGPL-3.0-only"
PACKAGE_LICENSE = "0BSD"


console = Console()

# This is a workaround for installing package via uv.
# pip installs dependencies same with root package,
# any tools from dependencies are available in the PATH.
#
# uv, on the other hand, installs the package in isolation
# and adds the package to the PATH via a symlink.
# Dependency utilities can be found in the same folder as the current package.
#
# Note that when you run via `uvx` it will be a real file,
# but if you install it via `uv tool install` it can be a symlink
# that must to be resolved.
_ROOT = os.path.dirname(os.path.realpath(sys.argv[0]))

reuse = local.get("reuse", os.path.join(_ROOT, "reuse"))
nvcmp = local.get("nvcmp", os.path.join(_ROOT, "nvcmp"))
nvchecker = local.get("nvchecker", os.path.join(_ROOT, "nvchecker"))


def cmd(command, *, withstderr=False, todebug=False):
    (returncode, stdout, stderr) = command.run(retcode=None)

    stdout = stdout.strip()
    stderr = stderr.strip()

    log = logging.debug if todebug else logging.info
    stream = stderr if withstderr else stdout

    if stream != "":
        log(stream)

    if returncode != 0:
        logging.error(f"'{command}' failed with exit code {returncode}")
        if stderr != "":
            logging.error(stderr)
        exit(1)
