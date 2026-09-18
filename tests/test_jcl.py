"""Session-control regressions. No real agent process is signalled or typed into."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("jcl", str(ROOT / "nv-tools/jcl"))
spec = importlib.util.spec_from_loader(loader.name, loader)
jcl = importlib.util.module_from_spec(spec)
loader.exec_module(jcl)
SID = "01234567-89ab-cdef-0123-456789abcdef"


def record(agent="codex", sid=SID, pane="%99", **overrides):
    rec = dict(agent=agent, session_id=sid, pid=12345, proc_start="123",
               cwd="/tmp", name="example", kind="interactive", status="idle",
               alive=True, stopped=False, pane_id=pane, target="test:1.0",
               tmux_session="test", window_index="1", pane_index="0",
               window_name="agent", started_at=100, model="gpt-test", effort="high")
    rec.update(overrides)
    return rec


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def invoke(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = jcl.main(argv)
        return rc, out.getvalue()

    def test_empty_json_is_valid(self):
        with patch.object(jcl, "collect", return_value=[]) as collect:
            rc, out = self.invoke(["list", "--agent", "codex", "--json"])
        self.assertEqual((rc, json.loads(out)), (0, []))
        collect.assert_called_once_with(include_stale=False, agent="codex")

    def test_codex_only_does_not_start_claude(self):
        with patch.object(jcl, "sessions_from_cli") as claude, \
             patch.object(jcl, "pane_lookup", return_value={}), \
             patch.object(jcl, "codex_sessions", return_value=[]):
            self.assertEqual(jcl.collect(agent="codex"), [])
        claude.assert_not_called()

    def test_current_agent_exclusion_both_codex_variables(self):
        for variable in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
            with self.subTest(variable=variable), patch.dict(os.environ, {variable: SID}), \
                 patch.object(jcl, "collect", return_value=[record()]):
                self.assertEqual(jcl.typeable_panes(), [])

    def test_suspended_and_noninteractive_panes_excluded(self):
        records = [record(stopped=True), record(kind="exec"), record(target="")]
        with patch.object(jcl, "collect", return_value=records):
            self.assertEqual(jcl.typeable_panes(), [])

    def test_lock_descriptor_and_custom_state_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "state_5.sqlite"
            with sqlite3.connect(database) as db:
                db.execute("CREATE TABLE threads (id TEXT, cwd TEXT, name TEXT, model TEXT, reasoning_effort TEXT, source TEXT, created_at INTEGER)")
                db.execute("INSERT INTO threads VALUES (?,?,?,?,?,?,?)",
                           (SID, "/work tree", "a named task", "gpt-local", "xhigh", "cli", 123))
            descriptors = [str(database), f"{tmp}/custom-home/thread-writer-locks/{SID}.lock"]
            with patch.object(jcl, "proc_start_marker", return_value="55"):
                records = jcl.codex_records(42, "/old", descriptors, ["/bin/codex"])
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["name"], "a named task")
            self.assertEqual(records[0]["cwd"], "/work tree")
            self.assertEqual(records[0]["model"], "gpt-local")
            self.assertEqual(records[0]["agent_home"], f"{tmp}/custom-home")
            self.assertEqual(records[0]["startedAt"], 123000)
            self.assertEqual(jcl.codex_records(42, "/old", [str(database)], ["codex"]), [])

    def test_legacy_rollout_deduplicates_lock(self):
        paths = [f"/custom/sessions/2026/09/16/rollout-2026-09-16T12-30-00-{SID}.jsonl",
                 f"/custom/thread-writer-locks/{SID}.lock"]
        with patch.object(jcl, "proc_start_marker", return_value="55"):
            records = jcl.codex_records(42, "/work", paths, ["codex", "resume", SID])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sessionId"], SID)
        self.assertEqual(records[0]["agent_home"], "/custom")

    def test_exec_helper_and_subagents_are_not_interactive(self):
        paths = [f"/custom/thread-writer-locks/{SID}.lock"]
        for argv in (["codex", "exec"], ["codex", "-c", "a=1", "exec"],
                     ["codex-code-mode-host"], ["bash", "-c", "codex"]):
            self.assertEqual(jcl.codex_records(42, "/work", paths, argv), [])
        with patch.object(jcl, "codex_thread_metadata", return_value={"source": "exec"}):
            self.assertEqual(jcl.codex_records(42, "/work", paths, ["codex"]), [])
        with patch.object(jcl, "codex_thread_metadata", return_value={"source": "cli", "agent_path": "/root/child"}):
            self.assertEqual(jcl.codex_records(42, "/work", paths, ["codex"]), [])

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "state_5.sqlite"
            self.assertEqual(jcl.codex_thread_metadata(SID, [str(missing)]), {})
            self.assertFalse(missing.exists())

    def test_lsof_reads_lock_and_rollout(self):
        output = f"p42\nfcwd\nn/work\nf7\nn/custom/thread-writer-locks/{SID}.lock\n"
        with patch.object(jcl.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)), \
             patch.object(jcl, "ps_info", return_value={"command": "codex resume " + SID}), \
             patch.object(jcl, "proc_start_marker", return_value="55"):
            records = jcl.codex_sessions_lsof()
        self.assertEqual(records[0]["cwd"], "/work")
        self.assertEqual(records[0]["sessionId"], SID)

    def test_save_preserves_live_model_and_restore_command(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(jcl, "collect", return_value=[record()]), \
             patch.object(jcl, "pane_tail", return_value="  gpt-live xhigh · /tmp · title"):
            path = Path(tmp) / "sessions.json"
            rc, _ = self.invoke(["save", "--agent", "codex", "-o", str(path)])
            saved = json.loads(path.read_text())["sessions"][0]
        self.assertEqual(rc, 0)
        self.assertEqual(saved["model"], "gpt-live")
        command = shlex.split(jcl.resume_record(saved))
        self.assertEqual(command[:3], ["codex", "resume", SID])
        self.assertIn('model_reasoning_effort="xhigh"', command)

    def test_restore_old_claude_and_new_codex_snapshots(self):
        claude = record("claude", sid="old-claude", pane="%98")
        del claude["agent"]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(jcl, "collect", return_value=[]), \
             patch.object(jcl, "tmux", return_value="") as tmux:
            path = Path(tmp) / "sessions.json"
            path.write_text(json.dumps({"sessions": [claude, record()]}))
            rc, out = self.invoke(["restore", "-f", str(path), "--dry-run"])
            self.assertEqual(rc, 0)
            self.assertIn("claude --resume old-claude", out)
            self.assertIn("codex resume " + SID, out)
            rc, out = self.invoke(["restore", "-f", str(path), "--agent", "codex", "--dry-run"])
            self.assertNotIn("claude --resume", out)
        self.assertTrue(all(c.args[0] == "list-sessions" for c in tmux.call_args_list))

    def test_refresh_skips_self_and_uses_stable_pane(self):
        with patch.dict(os.environ, {"CODEX_THREAD_ID": SID}), \
             patch.object(jcl, "collect", return_value=[record()]), \
             patch.object(jcl, "tmux") as tmux, patch.object(jcl.os, "kill") as kill:
            rc, out = self.invoke(["refresh", "all", "--agent", "codex"])
        self.assertEqual(rc, 1)
        tmux.assert_not_called()
        kill.assert_not_called()
        self.assertIn("Skipping the session", out)

    def test_refresh_resumes_after_graceful_exit(self):
        with patch.object(jcl, "collect", return_value=[record()]), \
             patch.object(jcl, "pane_tail", return_value="gpt-live high · /tmp"), \
             patch.object(jcl, "is_live_agent", return_value=True), \
             patch.object(jcl, "wait_for_exit", return_value=True), \
             patch.object(jcl.time, "sleep"), patch.object(jcl, "tmux") as tmux, \
             patch.object(jcl.os, "kill") as kill:
            rc, _ = self.invoke(["refresh", "test:1.0"])
        self.assertEqual(rc, 0)
        kill.assert_not_called()
        self.assertEqual(tmux.call_args_list[0].args, ("send-keys", "-t", "%99", "C-d"))
        resume = tmux.call_args_list[1].args
        self.assertEqual(resume[:4], ("send-keys", "-t", "%99", "-l"))
        self.assertIn("codex resume " + SID, resume[4])
        self.assertIn("--model gpt-live", resume[4])

    def test_refresh_no_resume_if_process_survives(self):
        with patch.object(jcl, "collect", return_value=[record()]), \
             patch.object(jcl, "pane_tail", return_value=""), \
             patch.object(jcl, "is_live_agent", return_value=True), \
             patch.object(jcl, "wait_for_exit", return_value=False), \
             patch.object(jcl.time, "sleep"), patch.object(jcl, "tmux") as tmux, \
             patch.object(jcl.os, "kill") as kill:
            rc, _ = self.invoke(["refresh", "all", "--agent", "codex"])
        self.assertEqual(rc, 1)
        self.assertEqual(kill.call_count, 2)
        self.assertFalse(any("-l" in c.args for c in tmux.call_args_list))

    def test_refresh_dry_run_never_sends_keys_or_signals(self):
        with patch.object(jcl, "collect", return_value=[record(), record("claude", "other")]), \
             patch.object(jcl, "pane_tail", return_value=""), \
             patch.object(jcl, "tmux") as tmux, patch.object(jcl.os, "kill") as kill:
            rc, out = self.invoke(["refresh", "all", "--agent", "codex", "-n"])
        self.assertEqual(rc, 0)
        self.assertIn("codex resume", out)
        self.assertNotIn("claude --resume", out)
        tmux.assert_not_called()
        kill.assert_not_called()

    def set_commands(self, argv, panes=None, footer="gpt-current high · /tmp"):
        with patch.object(jcl, "typeable_panes", return_value=panes or [record()]), \
             patch.object(jcl, "pane_tail", return_value=footer), \
             patch.object(jcl, "broadcast_to_agents", return_value=[]) as broadcast:
            rc, out = self.invoke(argv)
        return rc, out, [c.args[0] for c in broadcast.call_args_list]

    def test_codex_model_and_effort_respects_requested_level(self):
        rc, _, commands = self.set_commands(["set", "--agent", "codex", "--model", "gpt-next", "--effort", "low"])
        self.assertEqual((rc, commands), (0, ["/model gpt-next low"]))

    def test_codex_effort_only_preserves_live_model(self):
        rc, _, commands = self.set_commands(["set-effort", "xhigh", "--agent", "codex"])
        self.assertEqual((rc, commands), (0, ["/model gpt-current xhigh"]))

    def test_codex_model_only_preserves_effort(self):
        rc, _, commands = self.set_commands(["set-model", "gpt-next", "--agent", "codex"])
        self.assertEqual((rc, commands), (0, ["/model gpt-next high"]))

    def test_mixed_agent_model_routing(self):
        rc, _, commands = self.set_commands(
            ["set", "--model", "opus", "--model", "gpt-next", "--effort", "high"],
            [record(), record("claude", "other")])
        self.assertEqual(rc, 0)
        self.assertCountEqual(commands, ["/model opus", "/effort high", "/model gpt-next high"])

    def test_effort_only_fails_without_live_model(self):
        rc, out, commands = self.set_commands(["set-effort", "high", "--agent", "codex"], footer="busy")
        self.assertEqual((rc, commands), (1, []))
        self.assertIn("cannot read the current Codex model", out)

    def test_custom_codex_model_explicit_agent(self):
        rc, _, commands = self.set_commands(["set-model", "company-model", "--agent", "codex"])
        self.assertEqual((rc, commands), (0, ["/model company-model high"]))

    def broadcast_result(self, after):
        with patch.object(jcl, "pane_tail", side_effect=["gpt-old high · /tmp", after]), \
             patch.object(jcl, "is_live_agent", return_value=True), \
             patch.object(jcl, "tmux") as tmux, patch.object(jcl.time, "sleep"):
            results = jcl.broadcast_to_agents(
                "/model gpt-next high", [record()], confirm=("gpt-next",), timeout=0,
                expected_model="gpt-next", expected_effort="high")
        return results[0], tmux.call_args_list

    def test_prompt_echo_is_not_success(self):
        result, _ = self.broadcast_result("› /model gpt-next high\n gpt-old high · /tmp")
        self.assertEqual(result["status"], "unconfirmed")

    def test_refused_model_is_failure(self):
        result, _ = self.broadcast_result("Unknown model `gpt-next`\n gpt-old high · /tmp")
        self.assertEqual(result["status"], "refused")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(jcl.report_broadcast([result], "\0", 0, "/model"), 1)

    def test_footer_confirms_and_codex_uses_composer_keys(self):
        result, calls = self.broadcast_result(" gpt-next high · /tmp")
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(calls[0].args, ("send-keys", "-t", "%99", "C-e", "C-u"))

    def test_multiline_model_rejected_before_typing(self):
        with patch.object(jcl, "collect") as collect, self.assertRaises(SystemExit):
            self.invoke(["set", "--model", "gpt-next\nDo something"])
        collect.assert_not_called()

    def test_patch_resurrect_codex_and_claude(self):
        c = record("claude", sid="claude-id", window_index="2")
        with tempfile.TemporaryDirectory() as tmp, patch.object(jcl, "collect", return_value=[record(), c]), \
             patch.object(jcl, "pane_tail", return_value=""):
            layout = Path(tmp) / "layout.txt"
            layout.write_text("pane\ttest\t1\tagent\t1\t0\t:/tmp\t:/old\t1\tcodex\t:codex\n"
                              "pane\ttest\t2\tagent\t1\t0\t:/tmp\t:/old\t1\tclaude\t:claude\n")
            rc, _ = self.invoke(["patch-resurrect", str(layout)])
            self.assertEqual(rc, 0)
            first = layout.read_text()
            self.assertIn(":codex resume " + SID, first)
            self.assertIn(":claude --resume claude-id", first)
            self.invoke(["patch-resurrect", str(layout)])
            self.assertEqual(first, layout.read_text())

    @unittest.skipUnless(jcl.HAS_PROC, "Linux descriptor integration")
    def test_real_process_lock_discovery_and_exit(self):
        # A passive child with codex argv[0], not a model session. The descriptor
        # is real, so this tests /proc mapping rather than fabricating its result.
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "thread-writer-locks" / (SID + ".lock")
            lock.parent.mkdir()
            lock.touch()
            child = subprocess.Popen(
                ["codex", "-c", "import sys; f=open(sys.argv[1]); print('ready',flush=True); sys.stdin.read()", str(lock)],
                executable=sys.executable, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                rows = [r for r in jcl.codex_sessions_proc() if r["pid"] == child.pid]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["sessionId"], SID)
                child.communicate(timeout=5)
                self.assertFalse(any(r["pid"] == child.pid for r in jcl.codex_sessions_proc()))
            finally:
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=5)


class CompletionTests(unittest.TestCase):
    def test_agent_completion_for_set(self):
        command = "source completion/jcl_completion.bash\nCOMP_WORDS=(jcl set --agent co)\nCOMP_CWORD=3\n_jcl_complete\nprintf '%s\\n' \"${COMPREPLY[@]}\""
        proc = subprocess.run(["bash", "-c", command], cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(proc.stdout.strip(), "codex")

    def test_agent_option_offered_on_each_session_command(self):
        for cmd in ("list", "save", "restore", "set", "set-model", "set-effort"):
            script = f"source completion/jcl_completion.bash\nCOMP_WORDS=(jcl {cmd} --a)\nCOMP_CWORD=2\n_jcl_complete\nprintf '%s\\n' \"${{COMPREPLY[@]}}\""
            proc = subprocess.run(["bash", "-c", script], cwd=ROOT, text=True, capture_output=True, check=True)
            self.assertIn("--agent", proc.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
