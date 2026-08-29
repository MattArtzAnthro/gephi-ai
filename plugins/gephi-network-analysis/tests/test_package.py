import json
import re
import unittest
from pathlib import Path

import yaml


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"

COMMAND_TO_SKILL = {
    "analyze-network": "analyze-network",
    "centrality": "centrality-analysis",
    "community-detection": "community-detection",
    "counterfactual": "counterfactual-analysis",
    "explore": "explore-network",
    "export-map": "export-map",
    "import-and-explore": "import-and-explore",
    "teach": "teach-with-gephi",
    "text-network": "build-text-network",
    "verify-claim": "verify-claim",
    "visualize": "visualize-network",
}

AGENT_TO_SKILL = {
    "network-analyst": "analyze-network",
    "claim-verifier": "verify-claim",
    "layout-iterator": "visualize-network",
    "text-network-builder": "build-text-network",
}

ALLOWED_SKILL_KEYS = {"name", "description", "license", "metadata", "allowed-tools"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_skill(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} has no YAML frontmatter")
    _, frontmatter, _ = text.split("---", 2)
    return yaml.safe_load(frontmatter), text


class CodexPluginPackageTests(unittest.TestCase):
    def test_manifest_and_folder_names_match(self):
        manifest = load_json(MANIFEST)
        self.assertEqual(manifest["name"], PLUGIN_ROOT.name)
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        self.assertFalse("[TODO:" in MANIFEST.read_text(encoding="utf-8"))

    def test_repo_marketplace_points_to_the_package(self):
        marketplace = load_json(MARKETPLACE)
        self.assertEqual(marketplace["name"], "gephi-ai")
        entry = next(
            item for item in marketplace["plugins"]
            if item["name"] == "gephi-network-analysis"
        )
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Developer Tools")
        source = REPO_ROOT / entry["source"]["path"].removeprefix("./")
        self.assertEqual(source.resolve(), PLUGIN_ROOT.resolve())

    def test_plugin_versions_are_synchronized(self):
        codex = load_json(MANIFEST)["version"]
        claude = load_json(REPO_ROOT / "plugins/claude-code/.claude-plugin/plugin.json")["version"]
        latest = load_json(REPO_ROOT / "latest.json")["plugin"]
        self.assertEqual(codex, claude)
        self.assertEqual(codex, latest)

    def test_mcp_pins_are_synchronized(self):
        codex = load_json(PLUGIN_ROOT / ".mcp.json")["mcpServers"]["gephi-mcp"]["args"]
        claude = load_json(REPO_ROOT / "plugins/claude-code/.mcp.json")["mcpServers"]["gephi-mcp"]["args"]
        self.assertEqual(codex, claude)
        pinned = codex[1].split("==", 1)[1]
        pyproject = (REPO_ROOT / "mcp-server/pyproject.toml").read_text(encoding="utf-8")
        server = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
        self.assertEqual(pinned, server)

    def test_every_claude_command_has_a_codex_skill(self):
        claude_commands = {
            path.stem for path in (REPO_ROOT / "plugins/claude-code/commands").glob("*.md")
        }
        self.assertEqual(claude_commands, set(COMMAND_TO_SKILL))
        for skill in COMMAND_TO_SKILL.values():
            self.assertTrue((PLUGIN_ROOT / "skills" / skill / "SKILL.md").is_file())

    def test_every_claude_agent_procedure_is_folded_into_a_skill(self):
        claude_agents = {
            path.stem for path in (REPO_ROOT / "plugins/claude-code/agents").glob("*.md")
        }
        self.assertEqual(claude_agents, set(AGENT_TO_SKILL))
        for skill in AGENT_TO_SKILL.values():
            text = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("Dispatch the", text)
            self.assertNotIn("$ARGUMENTS", text)

    def test_skill_frontmatter_and_health_gate(self):
        for skill_dir in sorted((PLUGIN_ROOT / "skills").iterdir()):
            if not skill_dir.is_dir():
                continue
            frontmatter, text = load_skill(skill_dir / "SKILL.md")
            self.assertEqual(frontmatter["name"], skill_dir.name)
            self.assertTrue(frontmatter["description"].strip())
            self.assertFalse(set(frontmatter) - ALLOWED_SKILL_KEYS)
            self.assertIn("gephi_health_check", text)
            self.assertNotIn("[TODO:", text)

    # Files whose Codex copy is allowed to differ from the Claude original, each with the
    # reason. Anything not listed here must be byte-identical. A new reference file is
    # therefore a deliberate decision rather than something that slips through: the test
    # fails until it is classified.
    MAY_DIFFER = {
        "tool-reference.md": "drops host names specific to one vendor",
        "reading-network-maps.md": "names Codex skills rather than Claude slash commands",
    }

    def _reference_pairs(self):
        source_dir = REPO_ROOT / "plugins/claude-code/skills/gephi/references"
        bundled_dir = PLUGIN_ROOT / "skills/gephi/references"
        return source_dir, bundled_dir

    def test_reference_library_matches_the_portable_source(self):
        source_dir, bundled_dir = self._reference_pairs()
        source = {p.name for p in source_dir.glob("*.md")}
        bundled = {p.name for p in bundled_dir.glob("*.md")}
        self.assertEqual(source, bundled, "the two reference libraries hold different files")

    def test_unmodified_references_are_byte_identical(self):
        """Filename parity is inventory, not content. Everything not explicitly allowed to
        differ has to be identical, or an edit to one copy silently leaves the other stale."""
        source_dir, bundled_dir = self._reference_pairs()
        for path in sorted(source_dir.glob("*.md")):
            if path.name in self.MAY_DIFFER:
                continue
            with self.subTest(reference=path.name):
                self.assertEqual(
                    path.read_bytes(),
                    (bundled_dir / path.name).read_bytes(),
                    f"{path.name} differs between the two plugins. Either sync it, or add it "
                    f"to MAY_DIFFER with the reason it is allowed to differ.",
                )

    def test_references_allowed_to_differ_still_document_the_same_tools(self):
        """The differences are vendor wording. If they ever become a missing tool, this
        catches it: a tool added to one copy and not the other changes the documented set."""
        source_dir, bundled_dir = self._reference_pairs()
        for name in self.MAY_DIFFER:
            with self.subTest(reference=name):
                a = set(re.findall(r"\bgephi_[a-z0-9_]+", (source_dir / name).read_text(encoding="utf-8")))
                b = set(re.findall(r"\bgephi_[a-z0-9_]+", (bundled_dir / name).read_text(encoding="utf-8")))
                self.assertEqual(a, b, f"{name} documents different tools in the two plugins: {sorted(a ^ b)}")

    def test_both_skill_files_document_the_same_tools(self):
        a = set(re.findall(r"\bgephi_[a-z0-9_]+", (REPO_ROOT / "plugins/claude-code/skills/gephi/SKILL.md").read_text(encoding="utf-8")))
        b = set(re.findall(r"\bgephi_[a-z0-9_]+", (PLUGIN_ROOT / "skills/gephi/SKILL.md").read_text(encoding="utf-8")))
        self.assertEqual(a, b, f"the two SKILL.md files reference different tools: {sorted(a ^ b)}")

    def test_tool_reference_documents_every_registered_tool(self):
        """Ties the documentation to the server rather than to a number written in prose.
        Adding a tool without documenting it fails here instead of shipping undocumented."""
        server = (REPO_ROOT / "mcp-server/gephi_mcp.py").read_text(encoding="utf-8")
        registered = set(re.findall(r'@_tool\(name="(gephi_[a-z0-9_]+)"', server))
        self.assertTrue(registered, "found no @_tool registrations to compare against")
        documented = set(re.findall(r"\bgephi_[a-z0-9_]+", (PLUGIN_ROOT / "skills/gephi/references/tool-reference.md").read_text(encoding="utf-8")))
        missing = registered - documented
        self.assertFalse(missing, f"registered but undocumented in the Codex tool reference: {sorted(missing)}")

    def test_no_skill_names_a_tool_that_does_not_exist(self):
        """The other direction, which matters more: a skill telling the assistant to call a
        tool that was never registered sends it after something that cannot answer. Checking
        only that every tool is documented leaves this whole class invisible."""
        server = (REPO_ROOT / "mcp-server/gephi_mcp.py").read_text(encoding="utf-8")
        registered = set(re.findall(r'@_tool\(name="(gephi_[a-z0-9_]+)"', server))
        self.assertTrue(registered, "found no @_tool registrations to compare against")
        for path in sorted((PLUGIN_ROOT / "skills").rglob("*.md")):
            named = set(re.findall(r"\bgephi_[a-z0-9_]+", path.read_text(encoding="utf-8")))
            unknown = named - registered
            with self.subTest(skill=str(path.relative_to(PLUGIN_ROOT))):
                self.assertFalse(unknown, f"names tools that do not exist: {sorted(unknown)}")


if __name__ == "__main__":
    unittest.main()
