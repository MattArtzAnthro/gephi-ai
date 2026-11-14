# Releasing gephi-ai

Three tracks version independently: the **MCP server** (PyPI `gephi-ai`), the
**Gephi Java plugin** (`.nbm`), and the **assistant workflow packages** (Claude
and Codex marketplaces, sharing one plugin version). A release bumps whichever
changed and publishes to every channel that serves it.

`scripts/check-drift.sh` is the guard — it catches the steps below that were
skipped. This file is the how; run the script to find out what still needs doing.

## Order matters

PyPI first, then the release. The bundle does not carry the server:
`mcpb/pyproject.toml` pins `gephi-ai==<version>`, and Claude Desktop installs
that version from PyPI itself when someone installs the bundle. Publishing the
server last means releasing a bundle that points at a version PyPI does not
have yet, so it fails to install until PyPI catches up.

## The server and the Gephi plugin update at different times

The server reaches people almost at once: `uvx` and the workflow packages pull the new version.
The Gephi plugin reaches them only when they install a new `.nbm` or accept the update in
Gephi's plugin center. Every release therefore runs for a while beside the previous version of
the other half, and has to work with it. Three rules keep that true.

1. **The plugin's HTTP API only grows.** A plugin release may add endpoints and reply fields. It
   never removes or renames one that a released server reads, and it keeps its module code name,
   because Gephi treats a plugin with a new code name as a different plugin.
   `mcp-server/tests/test_plugin_endpoints.py` fails when the server calls a path the plugin's
   router no longer answers.
2. **The server never needs the newest plugin.** Server code that uses something a plugin
   release adds either behaves as before when the plugin lacks it, or refuses that one option
   with `_needs_plugin((major, minor, patch), "<feature>")`, which names the plugin version to
   update to. No tool may fail outright because the plugin is one release old.
3. **Raising `gephi.version` is a release of its own.** Gephi refuses a plugin built for a newer
   Gephi, so everyone on the older Gephi stays on the previous plugin until they update Gephi.
   `bump-version.sh` writes the new minimum to `nbm_needs_gephi` in `latest.json`, and the
   health check then tells those people to update Gephi first.

### The three pairs

Run these on a second Gephi (its own settings folder and port), never on a Gephi in use. To give
that Gephi exactly one plugin build, unzip the `.nbm` and copy its `netbeans/` contents into an
empty settings folder:

```bash
unzip -q gephi-ai-<java-version>.nbm -d /tmp/nbm
mkdir -p /tmp/gephi-test && cp -R /tmp/nbm/netbeans/. /tmp/gephi-test/
/Applications/Gephi.app/Contents/Resources/gephi/bin/gephi --userdir /tmp/gephi-test \
    --cachedir /tmp/gephi-test-cache -J-Dgephi.mcp.port=8091
curl -s http://127.0.0.1:8091/health     # confirms which plugin build answered
```

| Pair | What it shows | How to run it |
|---|---|---|
| New plugin, this server | The release as a whole | The live smoke test and the live workflow test (step 3 below) |
| New plugin, previous server release | Someone who updated the plugin in Gephi while their package still pins the older server | That release's own smoke test, from a worktree of its tag (below) |
| Previous plugin release, this server | Most users on the day of a server release | Download the previous `.nbm` with `gh release download`, install it as above, and run the live workflow test |

The previous server's smoke test, against the Gephi that holds the new plugin:

```bash
git worktree add --detach /tmp/prev-server v<previous-server-version>
cd /tmp/prev-server/mcp-server && GEPHI_API_URL=http://127.0.0.1:8091 PYTHONPATH=. \
    uv run --with mcp --with httpx --with pydantic python tests/live_smoke_test.py
git worktree remove /tmp/prev-server
```

Every line must PASS in all three. A server-only release needs the third pair alone, and the
live workflow test in step 3 is that pair when the second Gephi holds the released plugin.

Delete a test build of the `.nbm` from `gephi-ai-plugin/target/` afterwards. It carries the
same file name as the released one and different bytes, and step 9 must attach the file whose
checksum is in `latest.json`.

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
   load it. Add `-Dmaven.antrun.skip=true` to build without deploying.

   The auto-deploy copies the module jar only. When a release changes the bundled
   libraries (`modules/ext/org.gephi.plugins.gephi-ai/`), install the whole `.nbm`
   instead: with Gephi closed, unzip it and copy its `netbeans/` contents into
   `~/Library/Application Support/gephi/0.11/`, then delete any library folder under
   `modules/ext/org.gephi.plugins.gephi-ai/` that the new `.nbm` no longer carries.

   Then run the live smoke test, which drives every tool against a running Gephi
   at 1000 nodes; the unit tests do not exercise the live MCP path:

   ```bash
   cd mcp-server && PYTHONPATH=. .venv/bin/python tests/live_smoke_test.py
   ```

   Every line must PASS. Run it twice: against your own Gephi, and against a Gephi
   started with an empty settings folder, which has Gephi's default settings as a
   new user's does. The test's docstring gives the command for a second Gephi on
   its own port, which leaves an open Gephi untouched. On macOS it also fails when
   a Gephi dialog is left open, and on any interface-thread warning or error the
   run adds to Gephi's own log.

   Then run the live workflow test against the same second Gephi. It checks what holds across
   calls, which neither the unit suite (it replaces the HTTP client) nor the smoke test (one call
   per tool) can see: a partition surviving profile, stability and whatif, the receipt naming the
   layout and the partition's resolution, the edge-weight caveat after a profile and a layout,
   claims verifying against live values, and undo restoring a filter. It runs on generated
   networks of several kinds, and on your own when `GEPHI_TEST_NETWORKS` names a folder of them
   (one sub-folder each with `nodes.csv` and `edges.csv`; keep such data out of this repository):

   ```bash
   cd mcp-server && GEPHI_API_URL=http://127.0.0.1:8091 PYTHONPATH=. \
       uv run --with networkx python tests/live_workflow_test.py
   ```

   It refuses to run without `GEPHI_API_URL`, because it opens a new project for every network.
   Run it for every server release, not only plugin releases: every defect it covers was in the
   server.

   When the Claude Code plugin changed (hooks, agents, commands), also run the live
   plugin checks. They start real Claude sessions and confirm that Claude Code applies
   the plugin's health-check hook, the agents' tool lists and the commands'
   pre-approved tools, which the file checks alone cannot show. Gephi need not be
   running:

   ```bash
   cd mcp-server && GEPHI_LIVE_PLUGIN=1 PYTHONPATH=. .venv/bin/python -m pytest -v tests/test_plugin_live.py
   ```

   **Record the .nbm's checksum.** Once the `.nbm` is built, run
   `scripts/bump-version.sh --nbm-file gephi-ai-<java-version>.nbm`. It writes `nbm_sha256` into
   `latest.json`, and refuses a file named for another plugin version. Attach this same file to
   the release in step 9: a rebuild is not byte-identical, so its digest would not match. The
   installers use the digest when GitHub's API is unavailable, and refuse to install the plugin
   when they have none. A Java bump removes the old digest, so every release that changes the
   plugin needs this run. Once the release is published, the Installers workflow and
   `scripts/check-drift.sh` (step 11) compare it with the digest GitHub recorded for the attached
   `.nbm`.

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

6. **Publish the server to PyPI** (skip if the server did not change). Both plugin
   `.mcp.json` files pin the server version and resolve it from PyPI, so an unpublished pin
   fails on install for anyone who reinstalls.

7. **Build the Claude Desktop bundle** (skip if the server did not change):

   `scripts/build-mcpb.sh` checks that `mcpb/pyproject.toml` pins `gephi-ai==<version>`,
   locks the bundle's dependencies into `mcpb/uv.lock` with `uv lock`, and packs `mcpb/`
   with the lock inside. The lock step needs uv on PATH and needs `gephi-ai==<version>` to
   resolve from PyPI, so the build fails until it does. Claude Desktop
   is what installs `gephi-ai==<version>` from PyPI, and it does that on the
   user's machine when they install the bundle. So pip has to be able to resolve
   that version before the bundle is safe to release, or installs fail for
   anyone who grabs it early. Checking with
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

   uv can lag behind pip: for 1.21.0, pip resolved the new version while the lock still
   failed. Rerun with `UV_NO_CACHE=1 scripts/build-mcpb.sh` until it succeeds.

   The CI job "Build the bundle for real and check what it ships" fails on the release
   pull request for the same reason until the version is on PyPI. Rerun it once the build
   succeeds (`gh run rerun <run-id> --failed`) and merge only when every check passes.

   `.mcpb` files are gitignored — they ship as release assets only.

8. **Commit and push.** A push that changes a file under `.github/workflows/` needs a token
   with the `workflow` scope, and the `gh` CLI's default token may not carry it (check with
   `gh auth status`). Supply a token that has the scope through a credential helper that reads
   it from the system keychain at push time. Never put a token in a URL, a file, or
   `git config`, where it stays findable after the fact.

   ```bash
   git -c credential.helper= \
       -c credential.helper='!f() { echo "username=<user>"; echo "password=$(<command that prints the token>)"; }; f' \
       push origin main
   ```

   The empty `-c credential.helper=` is required. Passing a helper with `-c` adds to the chain
   and does not replace it, so the inherited helper is asked first, hands over the token
   that lacks the scope, and the push is rejected again with the same message.

9. **Cut the GitHub release.** Tag is `v<server-version>`, and both artifacts
   attach:

   ```bash
   gh release create v<server-version> \
     dist/gephi-ai-<server-version>.mcpb \
     gephi-ai-<java-version>.nbm \
     --title "v<server-version> — <short theme>" \
     --notes-file <notes>
   ```

   This step is easy to skip and expensive to skip: `latest.json` drives
   `gephi_health_check`'s update prompt, so the moment it is pushed, users are
   told to update. Without the release they are pointed at a Releases page that
   does not have the file.

   The one-command installers (`install.sh`, `install.ps1`) read this release
   too: they take the asset whose name ends in `.nbm` and verify it against the
   SHA-256 digest GitHub records for it, and when GitHub's API is rate-limited
   they fall back to `latest.json`, build the URL as
   `gephi-ai-<java-version>.nbm`, and verify against its `nbm_sha256`. Keep that asset name. They skip the `.nbm`
   entirely when the person's Gephi already bundles the plugin. Claude Desktop
   gets a `claude_desktop_config.json` entry pinned to the release, not the
   `.mcpb`. Nothing in the installers needs a version bump.

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

   Cowork keeps its own plugin store, which the commands above do not touch.
   `scripts/check-drift.sh --fix-clones` updates its marketplace clone. Its install record
   (`cowork_plugins/installed_plugins.json` under the Cowork session folder the drift
   script names) then needs pointing at the new version by hand. Back the file up,
   copy `marketplaces/gephi-ai/plugins/claude-code` to
   `cache/gephi-ai/gephi-network-analysis/<version>`, and update the entry's
   `installPath`, `version`, `gitCommitSha` and `lastUpdated`.

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
