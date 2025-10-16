# Zig-Devel infrastructure

This repository contains common infrastructure for all libraries,
such as CI, automatic releases, new version monitoring, etc.

If you want to add a new tool, use a package manager that can lock the version.
For internal scripts, prefer bash for simple ones and python for larger ones.

To use project locally install dependencies:

```bash
npm ci --no-fund --ignore-scripts
uv sync --locked --all-extras
```
