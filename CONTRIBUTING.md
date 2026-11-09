# Contributing

Bug reports and pull requests are welcome. Report a security problem privately, as
[SECURITY.md](SECURITY.md) describes, not in an issue.

## Reporting a bug

Open an issue with the **Bug report** form. Its most useful field is the output of
`gephi_health_check`, which gives the plugin and server versions.

## Pull requests

Keep a pull request to one change, and say in its description what it changes and why. A `fix`
commit carries a test that fails without it.

Set up and build as the README's [Development](README.md#development) section describes. Before
you open the pull request, run what CI runs:

- in `gephi-ai-plugin/`: `mvn test`, which runs Gephi core's checkstyle, `SourceRulesTest` and
  the coverage floor (`mvn package` goes further and copies the plugin into your own Gephi);
- in `mcp-server/`: `ruff check .`, `mypy ./*.py gephi_mcp_viewer`,
  `bandit -q -c pyproject.toml -r .` and `python -m pytest -q --cov`;
- at the top level: `shellcheck install.sh scripts/*.sh plugins/claude-code/scripts/*.sh` and
  `bash plugins/claude-code/scripts/test-check-gephi.sh`.

`scripts/check.sh` runs the offline part of this in one command.

Changes to the plugin also get the live smoke test in a separate Gephi, so that your own Gephi
and its settings are left alone; the docstring of `mcp-server/tests/live_smoke_test.py` gives the
command. Changes to `install.sh` or `install.ps1` are tested by `scripts/test-installer.sh`,
`scripts/install.Tests.ps1` and the Installers workflow.

By contributing you agree that your contribution is licensed under the repository's
[license](LICENSE).
