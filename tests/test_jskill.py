"""Tests for the shared Claude/Codex skill manager."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("jskill", str(ROOT / "nv-tools/jskill"))
spec = importlib.util.spec_from_loader(loader.name, loader)
jskill = importlib.util.module_from_spec(spec)
loader.exec_module(jskill)


class JskillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "repo" / "assets" / "skills"
        self.claude = base / "claude"
        self.codex = base / "codex"
        self.home = base / "home"
        self.env = patch.dict(
            os.environ,
            {
                "CROSSLV_SKILLS_ROOT": str(self.root),
                "CLAUDE_CONFIG_DIR": str(self.claude),
                "CODEX_HOME": str(self.codex),
                "HOME": str(self.home),
            },
            clear=True,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            rc = jskill.main(argv)
        return rc, output.getvalue()

    def make_skill(self, name="example"):
        skill = self.root / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: {}\ndescription: A useful test skill.\n---\n\n# Test\n".format(name)
        )
        return skill

    def test_add_sync_and_check(self):
        rc, output = self.invoke(
            ["add", "new-skill", "--description", "Use when a shared test skill is needed."]
        )
        self.assertEqual(rc, 0, output)
        skill = self.root / "new-skill"
        self.assertTrue((skill / "SKILL.md").is_file())
        for legacy in jskill.legacy_skill_roots(self.root):
            self.assertFalse(legacy.exists())
        self.assertEqual(self.claude.joinpath("skills").resolve(), self.root.resolve())
        installed = self.home / ".agents" / "skills" / "new-skill"
        self.assertEqual(installed.resolve(), skill.resolve())
        rc, output = self.invoke(["check"])
        self.assertEqual(rc, 0, output)

    def test_sync_preserves_unrelated_codex_skill(self):
        self.make_skill()
        unrelated = self.home / ".agents" / "skills" / "other-source"
        unrelated.mkdir(parents=True)
        (unrelated / "SKILL.md").write_text("unmanaged")
        rc, output = self.invoke(["sync"])
        self.assertEqual(rc, 0, output)
        self.assertTrue(unrelated.is_dir())
        self.assertFalse(unrelated.is_symlink())

    def test_list_summarizes_claude_and_codex_layouts(self):
        self.make_skill()
        unrelated = self.home / ".agents" / "skills" / "other-source"
        unrelated.mkdir(parents=True)
        (unrelated / "SKILL.md").write_text("unmanaged")
        rc, output = self.invoke(["sync"])
        self.assertEqual(rc, 0, output)
        rc, output = self.invoke(["list"])
        self.assertEqual(rc, 0, output)
        self.assertIn("Claude tree: linked", output)
        self.assertIn("Codex directory: {}".format(unrelated.parent), output)
        self.assertIn("Codex shared: 1/1 linked", output)
        self.assertIn("Codex independent: 1 preserved (other-source)", output)

    def test_conflict_is_not_overwritten(self):
        self.make_skill()
        conflict = self.home / ".agents" / "skills" / "example"
        conflict.mkdir(parents=True)
        marker = conflict / "keep-me"
        marker.write_text("user data")
        rc, output = self.invoke(["sync"])
        self.assertEqual(rc, 1, output)
        self.assertEqual(marker.read_text(), "user data")
        self.assertFalse(conflict.is_symlink())

    def test_explicit_backup_conflicts_preserves_then_links(self):
        skill = self.make_skill()
        conflict = self.home / ".agents" / "skills" / "example"
        conflict.mkdir(parents=True)
        (conflict / "keep-me").write_text("user data")
        backup = Path(self.temp.name) / "backup"
        rc, output = self.invoke(
            ["sync", "--backup-conflicts", "--backup-dir", str(backup)]
        )
        self.assertEqual(rc, 0, output)
        self.assertEqual((backup / "example" / "keep-me").read_text(), "user data")
        self.assertEqual(conflict.resolve(), skill.resolve())

    def test_legacy_links_are_repaired(self):
        skill = self.make_skill()
        legacy_claude, legacy_codex = jskill.legacy_skill_roots(self.root)
        self.claude.mkdir(parents=True)
        self.claude.joinpath("skills").symlink_to(legacy_claude, target_is_directory=True)
        installed = self.home / ".agents" / "skills" / "example"
        installed.parent.mkdir(parents=True)
        installed.symlink_to(legacy_codex / "example", target_is_directory=True)
        rc, output = self.invoke(["sync"])
        self.assertEqual(rc, 0, output)
        self.assertEqual(os.readlink(str(self.claude / "skills")), str(self.root))
        self.assertEqual(os.readlink(str(installed)), str(skill))
        self.assertFalse(legacy_claude.exists())
        self.assertFalse(legacy_codex.exists())

    def test_check_rejects_product_specific_installation_paths(self):
        skill = self.make_skill()
        with (skill / "SKILL.md").open("a") as handle:
            handle.write("Run ~/.claude/skills/example/script.sh\n")
        rc, output = self.invoke(["check", "--source-only"])
        self.assertEqual(rc, 1)
        self.assertIn("use assets/skills", output)

    def test_check_rejects_angle_brackets_in_description(self):
        skill = self.make_skill()
        (skill / "SKILL.md").write_text(
            "---\nname: example\ndescription: Write FINDINGS_<ticket>.md.\n---\n"
        )
        rc, output = self.invoke(["check", "--source-only"])
        self.assertEqual(rc, 1)
        self.assertIn("description cannot contain angle brackets", output)

    def test_sync_stops_before_linking_an_invalid_source(self):
        skill = self.make_skill()
        (skill / "SKILL.md").write_text("no frontmatter\n")
        rc, output = self.invoke(["sync"])
        self.assertEqual(rc, 1)
        self.assertIn("canonical source is invalid", output)
        self.assertFalse(self.claude.joinpath("skills").exists())

    def test_add_rejects_invalid_metadata_before_creating(self):
        rc, output = self.invoke(["add", "bad--name", "--description", "useful"])
        self.assertEqual(rc, 1)
        self.assertIn("at most 64", output)
        self.assertFalse(self.root.exists())
        rc, output = self.invoke(["add", "valid-name", "--description", "   "])
        self.assertEqual(rc, 1)
        self.assertIn("1-1024", output)
        self.assertFalse(self.root.exists())
        rc, output = self.invoke(
            ["add", "valid-name", "--description", "Write FINDINGS_<ticket>.md."]
        )
        self.assertEqual(rc, 1)
        self.assertIn("cannot contain angle brackets", output)
        self.assertFalse(self.root.exists())

    def test_path_rejects_traversal(self):
        rc, output = self.invoke(["path", "../outside"])
        self.assertEqual(rc, 1)
        self.assertIn("invalid skill name", output)

    def test_host_adapters_are_a_pair(self):
        skill = self.make_skill()
        hosts = skill / "references" / "hosts"
        hosts.mkdir(parents=True)
        (hosts / "claude.md").write_text("# Claude\n")
        rc, output = self.invoke(["check", "--source-only"])
        self.assertEqual(rc, 1)
        self.assertIn("codex.md", output)

    def test_sync_removes_only_stale_managed_links(self):
        self.make_skill()
        installed = self.home / ".agents" / "skills"
        installed.mkdir(parents=True)
        stale = installed / "removed-skill"
        stale.symlink_to(self.root / "removed-skill", target_is_directory=True)
        unrelated = installed / "other-source"
        unrelated.symlink_to(Path(self.temp.name) / "external", target_is_directory=True)
        rc, output = self.invoke(["sync"])
        self.assertEqual(rc, 0, output)
        self.assertFalse(stale.is_symlink())
        self.assertTrue(unrelated.is_symlink())


if __name__ == "__main__":
    unittest.main()
