# Zig-Devel infrastructure

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

To use project locally install dependencies:

```bash
npm ci --no-fund --ignore-scripts
uv sync --locked --all-extras
```
