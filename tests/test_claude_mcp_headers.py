"""Credential reuse and URL binding for Codex's Claude MCP header helper."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "assets/codex/bin/claude-mcp-headers"
FUTURE_MS = 4_102_444_800_000
MAAS = "https://maas.prd.astra.nvidia.com/maas"
ORION_URL = "https://mcp.yai.nvidia.com/orion/mcp"


def oauth(name, token, expires=FUTURE_MS, url=None):
    return {
        "serverName": name,
        "serverUrl": url or f"{MAAS}/{name.removeprefix('nvidia-')}/mcp",
        "accessToken": token,
        "expiresAt": expires,
    }


class HeaderHelperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.claude_file = self.root / ".claude.json"
        self.credentials_file = self.root / ".credentials.json"
        self.env = {
            **os.environ,
            "CLAUDE_CONFIG_DIR": str(self.root),
            "CLAUDE_USER_CONFIG": str(self.claude_file),
        }

    def configure(self, servers, credentials=None):
        self.claude_file.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
        if credentials is not None:
            self.credentials_file.write_text(
                json.dumps({"mcpOAuth": credentials}), encoding="utf-8"
            )

    def call(self, *args):
        return subprocess.run(
            [str(HELPER), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_oauth_token_comes_from_claude_and_freshest_duplicate_wins(self):
        url = f"{MAAS}/confluence/mcp"
        self.configure(
            {"nvidia-confluence": {"type": "http", "url": url}},
            {
                "old": oauth("nvidia-confluence", "old", FUTURE_MS),
                "new": oauth("nvidia-confluence", "new", FUTURE_MS + 1),
            },
        )
        result = self.call("nvidia-confluence", url)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"Authorization": "Bearer new"})

    def test_static_claude_header_supports_orion_without_copying_it(self):
        self.configure(
            {
                "Orion-MCP": {
                    "type": "http",
                    "url": ORION_URL,
                    "headers": {"Authorization": "Bearer orion-test-secret"},
                }
            }
        )
        result = self.call("Orion-MCP", ORION_URL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout), {"Authorization": "Bearer orion-test-secret"}
        )
        stale = self.call("Orion-MCP", "https://wrong.example.com/orion/mcp")
        self.assertNotEqual(stale.returncode, 0)
        self.assertNotIn("orion-test-secret", stale.stdout + stale.stderr)

    def test_nvidia_name_cannot_send_oauth_to_a_different_origin(self):
        url = "https://wrong.example.com/maas/glean/mcp"
        self.configure(
            {"nvidia-glean": {"type": "http", "url": url}},
            {"entry": oauth("nvidia-glean", "secret", url=url)},
        )
        result = self.call("nvidia-glean", url)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("secret", result.stdout + result.stderr)

    def test_removed_or_changed_server_cannot_reuse_a_stale_codex_entry(self):
        url = f"{MAAS}/gerrit/mcp"
        self.configure(
            {"nvidia-gerrit": {"type": "http", "url": url}},
            {"entry": oauth("nvidia-gerrit", "secret")},
        )
        result = self.call("nvidia-gerrit", f"{MAAS}/redmine/mcp")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("secret", result.stdout + result.stderr)

    def test_active_list_and_anonymous_server(self):
        self.configure(
            {
                "Orion-MCP": {"type": "http", "url": ORION_URL},
                "nvidia-confluence": {"type": "http", "url": f"{MAAS}/confluence/mcp"},
                "disabled": {"type": "http", "url": "https://example.com/mcp", "disabled": True},
            }
        )
        listed = self.call("--list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(listed.stdout.splitlines(), ["Orion-MCP", "nvidia-confluence"])
        anonymous = self.call("Orion-MCP", ORION_URL)
        self.assertEqual(anonymous.returncode, 0, anonymous.stderr)
        self.assertEqual(json.loads(anonymous.stdout), {})

    def test_expiring_oauth_refreshes_in_background_without_blocking_helper(self):
        url = f"{MAAS}/gerrit/mcp"
        self.configure(
            {"nvidia-gerrit": {"type": "http", "url": url}},
            {"entry": oauth("nvidia-gerrit", "old-token", expires=1)},
        )
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os\n"
            "from pathlib import Path\n"
            "p = Path(os.environ['CLAUDE_CONFIG_DIR']) / '.credentials.json'\n"
            "d = json.loads(p.read_text())\n"
            "d['mcpOAuth']['entry']['accessToken'] = 'fresh-token'\n"
            f"d['mcpOAuth']['entry']['expiresAt'] = {FUTURE_MS}\n"
            "p.write_text(json.dumps(d))\n",
            encoding="utf-8",
        )
        claude.chmod(0o755)
        self.env["PATH"] = str(bin_dir) + os.pathsep + self.env.get("PATH", "")
        first = self.call("nvidia-gerrit", url)
        self.assertEqual(first.returncode, 0, first.stderr)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                token = json.loads(self.credentials_file.read_text())["mcpOAuth"]["entry"]["accessToken"]
            except (json.JSONDecodeError, FileNotFoundError):
                token = None
            if token == "fresh-token":
                break
            time.sleep(0.05)
        self.assertEqual(token, "fresh-token")
        second = self.call("nvidia-gerrit", url)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout), {"Authorization": "Bearer fresh-token"})


if __name__ == "__main__":
    unittest.main()
