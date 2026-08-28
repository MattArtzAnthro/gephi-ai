# Releasing gephi-ai

Three tracks version independently: the **MCP server** (PyPI `gephi-mcp`), the
**Gephi Java plugin** (`.nbm`), and the **Claude Code plugin** (marketplace).
A release bumps whichever changed and publishes to every channel that serves it.

`scripts/check-drift.sh` is the guard — it catches the steps below that were
skipped. This file is the how; run the script to find out what still needs doing.

## Order matters

PyPI first, then the release. `scripts/build-mcpb.sh` installs
`gephi-mcp==<version>` **from PyPI**, so the bundle cannot be built until the
server is published. Publishing the server last means building the bundle from
the previous version without noticing.

## Steps

1. **Bump the versions.**

   ```bash
   scripts/bump-version.sh [--server X] [--java Y] [--plugin Z]
   ```

   Omit any track that did not change. This rewrites ~13 version strings across
   11 files and verifies they agree. It does not touch the CHANGELOG or build
   anything.

2. **Write the CHANGELOG entry** by hand, newest section at the top. Head it with
   the tracks that moved, e.g. `## Java plugin 1.2.17 / claude-plugin 1.9.32`.

3. **Build and test the Java plugin** (skip if the plugin did not change):

   ```bash
   mvn -f gephi-mcp-plugin/pom.xml clean package
   ```

   `package` auto-deploys the jar into
   `~/Library/Application Support/gephi/0.11/modules/`, so **restart Gephi** to
   load it. Verify the fix against a running Gephi before shipping — the unit
   tests do not exercise the live MCP path.

4. **Refresh the repo-root `.nbm`.** README offers the repo root as a download
   fallback, so it must match the build:

   ```bash
   cp gephi-mcp-plugin/target/gephi-mcp-<java-version>.nbm .
   git rm gephi-mcp-<old-version>.nbm
   ```

5. **Verify the artifact before publishing it.**

   ```bash
   scripts/verify-artifact.sh
   ```

   The test suite reads the working tree; a release reads the built wheel. Anything living in the
   gap between them — packaging rules, excluded files, data files a local run has rewritten — is
   invisible to a green suite. This builds the wheel, inspects it, installs it into a throwaway
   venv, and exercises it, then checks the documented tool count against the count the artifact
   actually registers. It exits non-zero and names the problem rather than letting a bad build
   reach PyPI, where a version cannot be unpublished.

   It exists because 1.15.0 and 1.16.0 shipped one machine's probe verdicts to every user:
   `caveats.json` is rewritten by a local probe run and the wheel was built afterwards. Every test
   passed throughout.

6. **Publish the server to PyPI** (skip if the server did not change). The pin in
   `claude-plugin/.mcp.json` resolves from PyPI, so an unpublished pin is dead on
   install for anyone who reinstalls.

7. **Build the Claude Desktop bundle** (skip if the server did not change):

   ```bash
   scripts/build-mcpb.sh          # version comes from mcpb/manifest.json
   ```

   `.mcpb` files are gitignored — they ship as release assets only.

8. **Commit and push.**

9. **Cut the GitHub release.** Tag is `v<server-version>`, and both artifacts
   attach:

   ```bash
   gh release create v<server-version> \
     gephi-ai-<server-version>.mcpb \
     gephi-mcp-<java-version>.nbm \
     --title "v<server-version> — <short theme>" \
     --notes-file <notes>
   ```

   This step is easy to skip and expensive to skip: `latest.json` drives
   `gephi_health_check`'s update prompt, so the moment it is pushed, users are
   told to update. Without the release they are pointed at a Releases page that
   does not have the file.

10. **Update the local install** so your own machine is not running the old build:

   ```bash
   claude plugin marketplace update gephi-ai
   claude plugin update gephi-network-analysis@gephi-ai
   ```

   Both commands are required — updating the marketplace clone alone leaves the
   installed plugin pinned to the old version.

11. **Verify:**

    ```bash
    scripts/check-drift.sh
    ```

    Silence, or all `OK`, means every channel agrees. Anything else names the
    channel that is behind and the command that fixes it.
