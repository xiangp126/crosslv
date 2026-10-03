"""codex completion: taken from codex itself, cached per binary, then filtered.

A stand-in codex answers `completion bash` with a clap-shaped script and
`--help` with a Commands section, and logs every run, so no real codex is needed.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPLETION = ROOT / "completion/codex_completion.bash"

FAKE_CODEX = textwrap.dedent('''\
    #!/bin/bash
    echo "$1" >> "$CODEX_FAKE_LOG"
    case "$1" in
    completion)
        cat <<'SCRIPT'
    _codex() {
        COMPREPLY=( $(compgen -W "[PROMPT] agents exec e delete tcp-tunnel -c -m --config --model" -- "$2") )
    }
    complete -F _codex -o bashdefault -o default codex
    SCRIPT
        ;;
    --help)
        printf 'Usage: codex\\n\\nCommands:\\n  agents  Agents\\n  exec    Run [aliases: e]\\n'
        printf '  delete  Delete\\n\\nOptions:\\n  -h, --help  Help\\n'
        ;;
    esac
    ''')


class CodexCompletionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "bin").mkdir()
        self.codex = root / "bin" / "codex"
        self.install(self.codex)
        (root / "home").mkdir()
        (root / "home" / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "gpt-6-sol", "visibility": "list"},
            {"slug": "gpt-reserve", "visibility": "hide"},
        ]}))
        self.log = root / "runs"
        self.env = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
                        XDG_CACHE_HOME=str(root / "cache"), CODEX_HOME=str(root / "home"),
                        CODEX_FAKE_LOG=str(self.log))

    @staticmethod
    def install(path):
        path.write_text(FAKE_CODEX)
        path.chmod(0o755)

    def complete(self, *words):
        script = (f"source {shlex.quote(str(COMPLETION))}\n"
                  f"COMP_WORDS=({' '.join(shlex.quote(w) for w in words)}); COMP_CWORD={len(words) - 1}\n"
                  '_codex_complete codex "${COMP_WORDS[-1]}" "${COMP_WORDS[-2]}"\n'
                  'printf "%s\\n" "${COMPREPLY[@]}"\n')
        proc = subprocess.run(["bash", "-c", script], env=self.env, text=True,
                              capture_output=True, check=True)
        return sorted(proc.stdout.split())

    def runs(self):
        return self.log.read_text().split() if self.log.exists() else []

    def test_first_word_is_what_codex_help_lists(self):
        self.assertEqual(self.complete("codex", "de"), ["delete"])
        # No [PROMPT] placeholder, no hidden command, no alias, no option
        self.assertEqual(self.complete("codex", ""), ["agents", "delete", "exec"])

    def test_dashes_pick_short_or_long_options_and_add_the_wrapper_flags(self):
        self.assertEqual(self.complete("codex", "-"), ["-c", "-m", "-y"])
        self.assertEqual(self.complete("codex", "--"), ["--auto-approve", "--config", "--model"])

    def test_models_come_from_codex_model_cache(self):
        self.assertEqual(self.complete("codex", "-m", "gpt"), ["gpt-6-sol"])

    def test_found_under_nvm_before_nvm_is_loaded(self):
        # A fresh interactive shell: the bashrc wrapper has not loaded nvm yet,
        # so codex is not on PATH
        nvm = Path(self.env["CODEX_HOME"]).parent / "nvm"
        node_bin = nvm / "versions" / "node" / "v24.12.0" / "bin"
        node_bin.mkdir(parents=True)
        self.install(node_bin / "codex")
        self.env.update(PATH="/usr/bin:/bin", NVM_DIR=str(nvm))
        self.assertEqual(self.complete("codex", "de"), ["delete"])

    def test_generated_once_per_installed_binary(self):
        self.complete("codex", "de")
        self.complete("codex", "ag")
        self.assertEqual(self.runs(), ["completion", "--help"])
        # An upgrade replaces the file: a new inode, so the script is made again
        fresh = self.codex.with_name("codex.new")
        self.install(fresh)
        fresh.replace(self.codex)
        self.complete("codex", "de")
        self.assertEqual(self.runs(), ["completion", "--help"] * 2)


if __name__ == "__main__":
    unittest.main()
