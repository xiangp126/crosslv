"""Dynamic discovery tests for the Codex MCP header helper."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "assets/codex/bin/claude-mcp-headers"
FUTURE_MS = 4_102_444_800_000


def credential(name, token, expires=FUTURE_MS, url=None):
    service = name.removeprefix("nvidia-")
    return {
        "serverName": name,
        "serverUrl": url or f"https://maas.prd.astra.nvidia.com/maas/{service}/mcp",
        "accessToken": token,
        "expiresAt": expires,
    }


class HeaderHelperTests(unittest.TestCase):
    def run_helper(self, entries, *args, claude_script=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".credentials.json").write_text(
                json.dumps({"mcpOAuth": entries}), encoding="utf-8"
            )
            env = {**os.environ, "CLAUDE_CONFIG_DIR": str(root)}
            if claude_script is not None:
                bin_dir = root / "bin"
                bin_dir.mkdir()
                claude = bin_dir / "claude"
                claude.write_text(claude_script, encoding="utf-8")
                claude.chmod(0o755)
                env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            return subprocess.run(
                [str(HELPER), *args], env=env, capture_output=True, text=True, timeout=10
            )

    def test_new_nvidia_service_is_discovered_without_an_allowlist_change(self):
        proc = self.run_helper(
            {"new|hash": credential("nvidia-new-service", "new-token")},
            "nvidia-new-service",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"Authorization": "Bearer new-token"})

    def test_freshest_usable_duplicate_wins(self):
        entries = {
            "old": credential("nvidia-glean", "old-token", FUTURE_MS),
            "new": credential("nvidia-glean", "new-token", FUTURE_MS + 1),
            "newest-empty": credential("nvidia-glean", "", FUTURE_MS + 2),
        }
        proc = self.run_helper(entries, "nvidia-glean")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["Authorization"], "Bearer new-token")

    def test_url_must_match_server_name_and_nvidia_maas_origin(self):
        for url in (
            "https://maas.prd.astra.nvidia.com/maas/redmine/mcp",
            "https://example.com/maas/glean/mcp",
            "http://maas.prd.astra.nvidia.com/maas/glean/mcp",
        ):
            with self.subTest(url=url):
                proc = self.run_helper(
                    {"bad": credential("nvidia-glean", "secret", url=url)},
                    "nvidia-glean",
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertNotIn("secret", proc.stdout + proc.stderr)

    def test_invalid_or_unknown_name_is_rejected_without_token_output(self):
        entries = {"known": credential("nvidia-glean", "secret")}
        for name in ("", "glean", "nvidia-Glean", "nvidia-../glean", "nvidia-unknown"):
            with self.subTest(name=name):
                proc = self.run_helper(entries, name)
                self.assertNotEqual(proc.returncode, 0)
                self.assertNotIn("secret", proc.stdout + proc.stderr)

    def test_invalid_expiry_is_rejected(self):
        entry = credential("nvidia-glean", "secret")
        entry["expiresAt"] = "tomorrow"
        proc = self.run_helper({"bad": entry}, "nvidia-glean")
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("secret", proc.stdout + proc.stderr)

    def test_list_reports_only_valid_authenticated_dynamic_entries(self):
        entries = {
            "good-b": credential("nvidia-zeta", "z"),
            "good-a": credential("nvidia-alpha", "a"),
            "duplicate": credential("nvidia-alpha", "a2"),
            "empty": credential("nvidia-empty", ""),
            "wrong-url": credential("nvidia-wrong", "secret", url="https://example.com/mcp"),
            "wrong-name": credential("other", "secret"),
        }
        proc = self.run_helper(entries, "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), ["nvidia-alpha", "nvidia-zeta"])
        self.assertNotIn("secret", proc.stdout + proc.stderr)

    def test_expired_token_is_synchronously_refreshed_before_return(self):
        refresher = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path

path = Path(os.environ["CLAUDE_CONFIG_DIR"]) / ".credentials.json"
data = json.loads(path.read_text())
for entry in data["mcpOAuth"].values():
    entry["accessToken"] = "fresh-" + entry["serverName"]
    entry["expiresAt"] = 4_102_444_800_000
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(data))
tmp.replace(path)
'''
        proc = self.run_helper(
            {"old": credential("nvidia-gerrit", "stale-secret", expires=1)},
            "nvidia-gerrit",
            claude_script=refresher,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout),
            {"Authorization": "Bearer fresh-nvidia-gerrit"},
        )
        self.assertNotIn("stale-secret", proc.stdout + proc.stderr)

    def test_refresh_failure_never_returns_stale_token(self):
        proc = self.run_helper(
            {"old": credential("nvidia-gerrit", "stale-secret", expires=1)},
            "nvidia-gerrit",
            claude_script="#!/bin/sh\nexit 9\n",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("silent refresh failed", proc.stderr)
        self.assertNotIn("stale-secret", proc.stdout + proc.stderr)

    def test_valid_token_does_not_invoke_claude(self):
        proc = self.run_helper(
            {"valid": credential("nvidia-gerrit", "valid-token")},
            "nvidia-gerrit",
            claude_script="#!/bin/sh\nexit 99\n",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"Authorization": "Bearer valid-token"})

    def test_concurrent_servers_share_one_synchronous_refresh(self):
        refresher = r'''#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path

count = Path(os.environ["REFRESH_COUNT"])
with count.open("a") as handle:
    handle.write("refresh\n")
time.sleep(0.25)
path = Path(os.environ["CLAUDE_CONFIG_DIR"]) / ".credentials.json"
data = json.loads(path.read_text())
for entry in data["mcpOAuth"].values():
    entry["accessToken"] = "fresh-" + entry["serverName"]
    entry["expiresAt"] = 4_102_444_800_000
tmp = path.with_suffix(".tmp")
tmp.write_text(json.dumps(data))
tmp.replace(path)
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = {
                "gerrit": credential("nvidia-gerrit", "stale-gerrit", expires=1),
                "glean": credential("nvidia-glean", "stale-glean", expires=1),
            }
            (root / ".credentials.json").write_text(
                json.dumps({"mcpOAuth": entries}), encoding="utf-8"
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            claude = bin_dir / "claude"
            claude.write_text(refresher, encoding="utf-8")
            claude.chmod(0o755)
            count = root / "refresh-count"
            env = {
                **os.environ,
                "CLAUDE_CONFIG_DIR": str(root),
                "REFRESH_COUNT": str(count),
                "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            }
            processes = [
                subprocess.Popen(
                    [str(HELPER), server],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for server in ("nvidia-gerrit", "nvidia-glean")
            ]
            results = [process.communicate(timeout=10) for process in processes]
            returncodes = [process.returncode for process in processes]
            count_lines = count.read_text().splitlines()
            headers = [json.loads(stdout)["Authorization"] for stdout, _ in results]

        self.assertEqual(returncodes, [0, 0], results)
        self.assertEqual(count_lines, ["refresh"])
        self.assertEqual(
            sorted(headers),
            ["Bearer fresh-nvidia-gerrit", "Bearer fresh-nvidia-glean"],
        )


if __name__ == "__main__":
    unittest.main()
