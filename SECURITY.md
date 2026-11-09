# Security policy

## Reporting a vulnerability

Report it privately through GitHub: open the repository's **Security** tab and choose **Report a
vulnerability**. Please do not open a public issue, pull request, or discussion for a security
problem; that discloses it before a fix is available.

Include what you found, the versions involved (the MCP server, the Gephi AI plugin, Gephi Desktop,
and the installer if relevant), and the steps to reproduce it.

## Supported versions

Fixes go into the latest release of each part: the `gephi-ai` MCP server on PyPI, the Gephi AI
plugin (`.nbm`), and the installers (`install.sh`, `install.ps1`). Update to the latest release
before reporting.

## Scope

- The Gephi AI plugin's HTTP API, which listens on `127.0.0.1` only and refuses requests that carry
  a browser origin or a host name other than the loopback address.
- The MCP server, which runs on the same machine as Gephi and talks to that API.
- The installers, which download the plugin and check it against its published SHA-256 checksum,
  and write the MCP server's entry into the settings of the AI clients they find.

Gephi Desktop itself is maintained by the Gephi project: report its vulnerabilities to
[gephi/gephi](https://github.com/gephi/gephi).
