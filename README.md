# Zig Devel infrastructure

This repository contains common infrastructure for all libraries,
such as CI, automatic releases, new version monitoring, etc.

Instead of multiple scripts, the entire infrastructure is collected
in a single utility, `zd`. Try to avoid bash scripts and prefer
to write a new command in `zd`.

The tool serves several purposes:

- explicitly check any implied rules;
- run the same commands locally and on CI;
- don't clutter libs repos with infrastructure;
- avoid vendor lock-in with a single CI provider.

## Usage

**Use standalone:**

```bash
pip install git+https://github.com/zig-devel/toolset#latest

# use CLI interface
zd --help
```

**Use locally:**

Install dependencies:

- [uv](https://github.com/astral-sh/uv) build system for python;
- (optional) Node.js to use some linters;
- (optional) [ShellCheck](https://www.shellcheck.net/) for validate shell scripts.

```bash
# install dependencies
uv sync --locked --all-extras

# activate environment
. .venv/bin/activate

# use CLI interface
zd --help
```

## License

Zig Devel's toolset is Licensed under [GNU Affero General Public License v3.0](./LICENSES/AGPL-3.0-only.txt).

Note that the packages are licensed differently under the 0BSD
OR the original project license. This differentiation is intended
to give you as much freedom as possible in using packages,
but save the toolset free.
