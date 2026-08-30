# Releasing gephi-ai

Three tracks version independently: the **MCP server** (PyPI `gephi-ai`), the
**Gephi Java plugin** (`.nbm`), and the **assistant workflow packages** (Claude
and Codex marketplaces, sharing one plugin version). A release bumps whichever
changed and publishes to every channel that serves it.

`scripts/check-drift.sh` is the guard — it catches the steps below that were
skipped. This file is the how; run the script to find out what still needs doing.

## Order matters

PyPI first, then the release. `scripts/build-mcpb.sh` installs
`gephi-ai==<version>` **from PyPI**, so the bundle cannot be built until the
server is published. Publishing the server last means building the bundle from
the previous version without noticing.

## Steps

1. **Bump the versions.**

   ```bash
   scripts/bump-version.sh [--server X] [--java Y] [--plugin Z]
   ```

   Omit any track that did not change. This rewrites the synchronized server,
   Java, Claude, and Codex surfaces and verifies they agree. It does not touch the CHANGELOG or build
   anything.

2. **Write the CHANGELOG entry** by hand, newest section at the top. Head it with
   the tracks that moved, e.g. `## Java plugin 1.2.17 / workflow packages 1.9.32`.

3. **Build and test the Java plugin** (skip if the plugin did not change):

   ```bash
   mvn -f gephi-ai-plugin/pom.xml clean package
   ```

   `package` auto-deploys the jar into
   `~/Library/Application Support/gephi/0.11/modules/`, so **restart Gephi** to
   load it. Verify the fix against a running Gephi before shipping — the unit
   tests do not exercise the live MCP path.

4. **Do not commit the built `.nbm`.** It attaches to the GitHub release in step 9,
   which is the single download path. A copy at the repo root went two releases stale
   once, and a binary committed here stays in git history for good.

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
   Both plugin `.mcp.json` files resolve from PyPI, so an unpublished pin is dead
   on install for anyone who reinstalls.

7. **Build the Claude Desktop bundle** (skip if the server did not change):

   `scripts/build-mcpb.sh` installs `gephi-ai==<version>` from PyPI through pip, so pip
   has to be able to resolve that version before this step can run. Checking with
   `curl -s https://pypi.org/simple/gephi-ai/ | grep gephi_ai-<version>-py3` is
   necessary but not sufficient: that check can pass while pip still cannot install the
   version, because pip and curl can land on different PyPI CDN edges and the one pip
   hits can lag behind. Poll with pip itself and wait for it to succeed before building:

   ```bash
   pip download --no-cache-dir gephi-ai==<version>
   ```

   ```bash
   scripts/build-mcpb.sh          # version comes from mcpb/manifest.json
   ```

   `.mcpb` files are gitignored — they ship as release assets only.

8. **Commit and push.** A push that changes `.github/workflows/ci.yml` requires the
   `workflow` scope. Git routes GitHub credentials through the `gh` CLI by default, and
   that token carries only `gist, read:org, repo`, so a push touching a workflow file is
   rejected. This shows up most often on a force-push, where a rewritten history carries
   the workflow file through along with everything else. A second macOS keychain item
   holds the fix: `GitHub - https://api.github.com` under account `MattArtzAnthro`,
   scoped `repo, user, workflow`. Use that token instead of the `gh` default for any push
   touching a workflow file, and supply it through a credential helper that reads the
   keychain at push time. Never put the token in a URL, a file, or `git config`, where it
   stays findable after the fact.

   ```bash
   git -c credential.helper= \
       -c credential.helper='!f() { echo "username=MattArtzAnthro"; echo "password=$(security find-generic-password -s "GitHub - https://api.github.com" -a MattArtzAnthro -w)"; }; f' \
       push origin main
   ```

   The empty `-c credential.helper=` is not decoration and the push fails without it.
   Passing a helper with `-c` ADDS to the chain rather than replacing it, so the inherited
   `osxkeychain` entry is consulted first, hands over the cached token that lacks the scope,
   and the push is rejected a second time with the same message. Resetting the list to empty
   first is what makes the new helper the only one asked.

9. **Cut the GitHub release.** Tag is `v<server-version>`, and both artifacts
   attach:

   ```bash
   gh release create v<server-version> \
     gephi-ai-<server-version>.mcpb \
     gephi-ai-<java-version>.nbm \
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

   If the Codex marketplace is installed locally, refresh it and reinstall the
   matching workflow package as well:

   ```bash
   codex plugin marketplace upgrade gephi-ai
   codex plugin remove gephi-network-analysis@gephi-ai
   codex plugin add gephi-network-analysis@gephi-ai
   ```

   Start a new task after reinstalling so Codex discovers the refreshed skills
   and MCP registration together.

11. **Verify:**

    ```bash
    scripts/check-drift.sh
    ```

    Silence, or all `OK`, means every channel agrees. Anything else names the
    channel that is behind and the command that fixes it.

12. **Exercise the plugins in a real host** (only when the plugin or the server changed).

    The test suites check the package: manifests agree, versions are pinned, the
    documented tools match the registered ones. They cannot check that a host actually
    loads the thing, and that is a distinct failure. A Codex task has been observed
    receiving the UI resource while none of the tools appeared, with a restart fixing
    it, which no packaged test can see.

    In a fresh task in each host, confirm:

    - The MCP server initialises through the packaged `.mcp.json`.
    - `tools/list` returns the documented number of tools, not a subset.
    - `resources/list` includes `ui://gephi/graph-view`.
    - `gephi_health_check` reaches Gephi Desktop and reports the expected plugin version.
    - After fully quitting and reopening the host, a NEW task still sees both the tools
      and the resource. First-run and second-run behaviour differ, so checking only one
      proves only half.

    Run it from the desktop application rather than an interactive shell. The shell
    inherits a PATH the app does not, so a `uvx` entry point can work in one and fail in
    the other, and the app is where users hit it.
