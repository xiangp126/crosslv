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
from types import SimpleNamespace
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
        # Reading tmux is fine (restore looks for the pane to reuse); changing it is not
        self.assertTrue(all(c.args[0] in ("list-sessions", "list-panes") for c in tmux.call_args_list))

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

    def set_commands(self, argv, panes=None, footer="gpt-current high · /tmp", turn="idle", comes_back=True):
        """What set typed: claude's slash commands, then the resume command each
        restarted codex pane was given (its leading `cd` dropped). `footer` is
        one footer for every pane, or a dict by pane id."""
        typed = []

        def relaunch(rec, command, timeout, e):
            typed.append(command.split(" && ", 1)[1])
            return True

        tail = ({"side_effect": lambda pane, *a, **k: footer[pane]} if isinstance(footer, dict)
                else {"return_value": footer})
        with patch.object(jcl, "typeable_panes", return_value=panes or [record()]), \
             patch.object(jcl, "pane_tail", **tail), \
             patch.object(jcl, "CODEX_DIR", Path("/nonexistent")), \
             patch.object(jcl, "codex_turn", return_value=(turn, None)), \
             patch.object(jcl, "relaunch", side_effect=relaunch), \
             patch.object(jcl, "await_codex_settings",
                          side_effect=lambda recs, *a, **k: {r["session_id"] for r in recs} if comes_back else set()), \
             patch.object(jcl, "broadcast_to_agents", return_value=[]) as broadcast:
            rc, out = self.invoke(argv)
        return rc, out, [c.args[0] for c in broadcast.call_args_list] + typed

    @staticmethod
    def resumed(model, effort, sid=SID):
        return f"codex resume {sid} --model {model} -c 'model_reasoning_effort=\"{effort}\"'"

    def test_codex_model_and_effort_respects_requested_level(self):
        rc, _, commands = self.set_commands(["set", "--agent", "codex", "--model", "gpt-next", "--effort", "low"])
        self.assertEqual((rc, commands), (0, [self.resumed("gpt-next", "low")]))

    def test_codex_effort_only_preserves_live_model(self):
        rc, _, commands = self.set_commands(["set", "--effort", "xhigh", "--agent", "codex"])
        self.assertEqual((rc, commands), (0, [self.resumed("gpt-current", "xhigh")]))

    def test_codex_model_only_preserves_effort(self):
        rc, _, commands = self.set_commands(["set", "--model", "gpt-next", "--agent", "codex"])
        self.assertEqual((rc, commands), (0, [self.resumed("gpt-next", "high")]))

    def test_mixed_agent_model_routing(self):
        rc, _, commands = self.set_commands(
            ["set", "--model", "opus", "--model", "gpt-next", "--effort", "high"],
            [record(), record("claude", "other")])
        self.assertEqual(rc, 0)
        self.assertCountEqual(commands, ["/model opus", "/effort high", self.resumed("gpt-next", "high")])

    def test_effort_follows_the_named_model(self):
        recs = [record(), record("claude", "other")]
        rc, _, commands = self.set_commands(["set", "--model", "opus", "--effort", "max"], recs)
        self.assertEqual((rc, commands), (0, ["/model opus", "/effort max"]))  # codex untouched
        rc, _, commands = self.set_commands(["set", "--effort", "max"], recs)
        self.assertCountEqual(commands, ["/effort max", self.resumed("gpt-current", "max")])  # sweep

    def test_codex_panes_are_restarted_per_setting_and_only_when_needed(self):
        panes = [record(sid="a", pane="%1", target="t:1.1"),
                 record(sid="b", pane="%2", target="t:1.2"),
                 record(sid="c", pane="%3", target="t:1.3")]
        footers = {"%1": "gpt-6-sol max · /w", "%2": "gpt-6-sol high · /w", "%3": "gpt-6-astra low · /w"}
        rc, out, commands = self.set_commands(["set", "--effort", "max", "--agent", "codex"], panes, footers)
        self.assertEqual(rc, 0)
        # Nothing is typed into a codex session any more; a already runs on the pair
        self.assertEqual(commands, [self.resumed("gpt-6-sol", "max", "b"),
                                    self.resumed("gpt-6-astra", "max", "c")])
        self.assertIn("Restarting 1 of 2 codex pane(s) on gpt-6-sol max", out)
        self.assertIn("Restarting 1 codex pane(s) on gpt-6-astra max", out)
        self.assertRegex(out, r"t:1\.1\s+unchanged")
        self.assertRegex(out, r"t:1\.2\s+confirmed")

    def test_codex_heading_says_when_nothing_needs_a_restart(self):
        rc, out, commands = self.set_commands(["set", "--effort", "max", "--agent", "codex"],
                                              [record(), record(sid="b", pane="%2", target="t:1.2")],
                                              footer="gpt-current max · /w")
        self.assertEqual((rc, commands), (0, []))
        self.assertIn("No restart needed for 2 codex pane(s) on gpt-current max", out)

    def test_codex_pane_mid_turn_or_not_back_counts_as_not_done(self):
        rc, out, commands = self.set_commands(["set", "--effort", "max", "--agent", "codex"], turn="busy")
        self.assertEqual((rc, commands), (1, []))
        self.assertIn("busy", out)
        rc, out, _ = self.set_commands(["set", "--effort", "max", "--agent", "codex"], comes_back=False)
        self.assertEqual(rc, 1)
        self.assertIn("unconfirmed", out)

    def test_codex_display_names_become_model_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "models_cache.json").write_text(json.dumps(
                {"models": [{"slug": "gpt-6-sol", "display_name": "GPT-6-Sol"}]}))
            with patch.object(jcl, "CODEX_DIR", Path(tmp)):
                self.assertEqual(jcl.codex_pane_settings("› Ask\n  GPT-6-Sol max · /w"), ("gpt-6-sol", "max"))
                self.assertEqual(jcl.codex_model_slug("company-model"), "company-model")
                # A snapshot saved before the mapping still resumes on the id
                self.assertIn("--model gpt-6-sol ",
                              jcl.resume_record(record(model="GPT-6-Sol", effort="max")))

    def test_claude_reply_comes_from_the_transcript_and_shows_as_it_lands(self):
        reply = json.dumps({"type": "user", "message": {"role": "user", "content":
                            "<local-command-stdout>Set effort level to max (this session only):"
                            " Deep</local-command-stdout>"}}) + "\n"
        # The screen is full of the same reply from earlier runs: counting it
        # can never tell a new one apart
        screen = "❯ /effort max\n  ⎿  Set effort level to max (this session only)\n" * 6
        with tempfile.TemporaryDirectory() as tmp:
            for sid in ("silent", "quick"):
                Path(tmp, sid + ".jsonl").write_text(reply)
            recs = [record("claude", "silent", pane="%1", target="t:1.1"),
                    record("claude", "quick", pane="%2", target="t:1.2")]

            def tmux(*argv):
                if argv[-1] == "Enter" and argv[2] == "%2":
                    with Path(tmp, "quick.jsonl").open("a") as fh:
                        fh.write(reply)
                return ""

            with patch.object(jcl, "typeable_panes", return_value=recs), \
                 patch.object(jcl, "claude_transcript",
                              side_effect=lambda rec: Path(tmp, rec["session_id"] + ".jsonl")), \
                 patch.object(jcl, "is_live_agent", return_value=True), \
                 patch.object(jcl, "pane_tail", return_value=screen), \
                 patch.object(jcl, "tmux", side_effect=tmux), \
                 patch.object(jcl.time, "sleep"):
                rc, out = self.invoke(["set", "--effort", "max", "--agent", "claude", "--timeout", "0.2"])
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"t:1\.2\s+confirmed\s+example\s+Set effort level to max \(this session only\)")
        # The pane that answered is shown before the one still being waited on
        self.assertLess(out.index("t:1.2"), out.index("t:1.1"))
        self.assertRegex(out, r"t:1\.1\s+unconfirmed")

    def test_set_takes_named_panes_like_refresh(self):
        recs = [record("claude", "c1", pane="%1", target="t:1.1"),
                record("claude", "c2", pane="%2", target="t:1.2"),
                record(sid="cx", pane="%3", target="t:1.3")]

        def sent(*argv):
            with patch.object(jcl, "collect", return_value=[dict(r) for r in recs]), \
                 patch.object(jcl, "typeable_panes") as every_pane, \
                 patch.object(jcl, "broadcast_to_agents", return_value=[]) as broadcast:
                rc, out = self.invoke(["set", *argv])
            every_pane.assert_not_called()  # named panes only, not a sweep of all
            return rc, out, [(c.args[0], [r["session_id"] for r in c.kwargs["records"]])
                             for c in broadcast.call_args_list]

        # A named claude pane is set even under --agent codex: naming wins
        self.assertEqual(sent("t:1.2", "--effort", "max", "--agent", "codex")[::2],
                         (0, [("/effort max", ["c2"])]))
        self.assertEqual(sent("t:1.1,t:1.2", "--effort", "high")[2], [("/effort high", ["c1", "c2"])])
        self.assertEqual(sent("--effort", "high", "t:1.1", "t:1.2")[2], [("/effort high", ["c1", "c2"])])
        self.assertEqual(sent("claude", "--effort", "high")[2], [("/effort high", ["c1", "c2"])])
        rc, out, calls = sent("t:9.9", "--effort", "max")
        self.assertEqual((rc, calls), (1, []))
        self.assertIn("No live session at 't:9.9'", out)

    def test_effort_only_fails_without_live_model(self):
        rc, out, commands = self.set_commands(["set", "--effort", "high", "--agent", "codex"], footer="busy")
        self.assertEqual((rc, commands), (1, []))
        self.assertIn("cannot read the current Codex model", out)

    def test_custom_codex_model_explicit_agent(self):
        rc, _, commands = self.set_commands(["set", "--model", "company-model", "--agent", "codex"])
        self.assertEqual((rc, commands), (0, [self.resumed("company-model", "high")]))

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


    def test_codex_desktop_threads_are_marked(self):
        paths = [f"/custom/thread-writer-locks/{SID}.lock"]
        with patch.object(jcl, "codex_thread_metadata", return_value={"source": "vscode"}):
            self.assertEqual(jcl.codex_records(42, "/w", paths, ["codex", "resume", SID])[0]["origin"], "desktop")
        server = ["codex", "-c", "a=1", "app-server", "--listen", "unix://"]
        with patch.object(jcl, "codex_thread_metadata", return_value={"source": "cli"}):
            self.assertEqual(jcl.codex_records(42, "/w", paths, ["codex"])[0]["origin"], "terminal")
            # The shared daemon hosts CLI threads too; the thread's source decides
            self.assertEqual(jcl.codex_records(42, "/w", paths, server)[0]["origin"], "terminal")
        with patch.object(jcl, "codex_thread_metadata", return_value={"source": "vscode"}):
            self.assertEqual(jcl.codex_records(42, "/w", paths, server)[0]["origin"], "desktop")
        # The daemon stamps `vscode` on threads a terminal asked it for; the
        # originator still names the client, from the state row or the rollout
        tui = {"source": "vscode", "originator": "codex-tui"}
        with patch.object(jcl, "codex_thread_metadata", return_value=tui):
            self.assertEqual(jcl.codex_records(42, "/w", paths, ["codex"])[0]["origin"], "terminal")
            self.assertEqual(jcl.codex_records(42, "/w", paths, server)[0]["origin"], "terminal")
        with patch.object(jcl, "codex_thread_metadata", return_value={"source": "vscode"}), \
             patch.object(jcl, "codex_rollout_meta", return_value=tui):
            self.assertEqual(jcl.codex_records(42, "/w", paths, ["codex"])[0]["origin"], "terminal")
        app = {"source": "vscode", "originator": "Codex Desktop"}
        with patch.object(jcl, "codex_thread_metadata", return_value=app):
            self.assertEqual(jcl.codex_records(42, "/w", paths, ["codex"])[0]["origin"], "desktop")
        # Never had a message (no state row, no rollout): nothing to resume
        with patch.object(jcl, "codex_thread_metadata", return_value={}), \
             patch.object(jcl, "codex_rollout_meta", return_value={}):
            self.assertEqual(jcl.codex_records(42, "/w", paths, server)[0]["origin"], "desktop")
            self.assertEqual(jcl.codex_records(42, "/w", paths, ["codex"])[0]["origin"], "terminal")

    def test_restore_reuses_the_idle_original_pane(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(jcl, "collect", return_value=[]), \
             patch.object(jcl, "free_panes", return_value={"%99": "test:1.0"}), \
             patch.object(jcl, "tmux", return_value="test") as tmux:
            path = Path(tmp) / "sessions.json"
            path.write_text(json.dumps({"sessions": [record(cwd=tmp)]}))
            rc, out = self.invoke(["restore", "-f", str(path)])
        self.assertEqual(rc, 0)
        self.assertIn("Restored in place", out)
        verbs = [c.args[0] for c in tmux.call_args_list]
        self.assertNotIn("new-window", verbs)
        self.assertNotIn("new-session", verbs)
        self.assertTrue(any(c.args[:3] == ("send-keys", "-t", "%99") for c in tmux.call_args_list))

    def test_restore_skips_desktop_sessions(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(jcl, "collect", return_value=[]), \
             patch.object(jcl, "free_panes", return_value={"%99": "test:1.0"}), \
             patch.object(jcl, "tmux", return_value="test") as tmux:
            path = Path(tmp) / "sessions.json"
            path.write_text(json.dumps({"sessions": [record(cwd=tmp, origin="desktop")]}))
            rc, out = self.invoke(["restore", "-f", str(path)])
        self.assertIn("Skipped, desktop session", out)
        self.assertFalse(any(c.args[0] in ("send-keys", "new-window") for c in tmux.call_args_list))

    def test_exit_session_quits_without_relaunching(self):
        with patch.object(jcl, "collect", return_value=[record()]), \
             patch.object(jcl, "is_live_agent", return_value=True), \
             patch.object(jcl, "pane_tail", return_value=""), \
             patch.object(jcl, "quit_agent", return_value=True) as quit_agent, \
             patch.object(jcl, "tmux") as tmux:
            rc, out = self.invoke(["exit-session", "test:1.0"])
        self.assertEqual(rc, 0)
        quit_agent.assert_called_once()
        tmux.assert_not_called()  # nothing typed back into the pane
        self.assertIn("Exited", out)
        self.assertIn("codex resume " + SID, out)

    def test_exit_session_needs_a_selector_and_spares_self_and_desktop(self):
        rc, _ = self.invoke(["exit-session"])
        self.assertEqual(rc, 1)
        recs = [record(), record(sid="desk", pane="%98", target="test:1.1", origin="desktop")]
        with patch.dict(os.environ, {"CODEX_THREAD_ID": SID}), \
             patch.object(jcl, "collect", return_value=recs), \
             patch.object(jcl, "quit_agent") as quit_agent:
            rc, out = self.invoke(["exit-session", "all", "--agent", "codex"])
        self.assertEqual(rc, 1)
        quit_agent.assert_not_called()
        self.assertIn("Skipping the session", out)
        self.assertIn("Skipping desktop session", out)

    def test_claude_sessions_come_from_files_before_the_cli(self):
        rec = {"pid": 7, "sessionId": "abc", "cwd": "/w", "name": "n", "kind": "interactive"}
        with patch.object(jcl, "sessions_from_files", return_value=[rec]), \
             patch.object(jcl, "sessions_from_cli") as cli, \
             patch.object(jcl, "codex_sessions", return_value=[]), \
             patch.object(jcl, "pane_lookup", return_value={}), \
             patch.object(jcl, "is_live_agent", return_value=True), \
             patch.object(jcl, "proc_environ", return_value={}), \
             patch.object(jcl, "proc_state", return_value="S"):
            self.assertEqual([r["session_id"] for r in jcl.collect()], ["abc"])
            cli.assert_not_called()  # starting the client is what made jcl slow
        # Files that yield no usable record (format changed, or none there):
        # the supported CLI answers instead
        with patch.object(jcl, "sessions_from_files", return_value=[{"unexpected": 1}]), \
             patch.object(jcl, "sessions_from_cli", return_value=[rec]) as cli, \
             patch.object(jcl, "codex_sessions", return_value=[]), \
             patch.object(jcl, "pane_lookup", return_value={}), \
             patch.object(jcl, "is_live_agent", return_value=True), \
             patch.object(jcl, "proc_environ", return_value={}), \
             patch.object(jcl, "proc_state", return_value="S"):
            self.assertEqual([r["session_id"] for r in jcl.collect()], ["abc"])
            cli.assert_called_once()

    def test_agent_keywords_select_sessions(self):
        recs = [record(), record("claude", "c1", pane="%1", target="t:1.1"),
                record("claude", "c2", pane="%2", target="t:1.2")]
        def picked(*sessions, agent="claude"):
            args = SimpleNamespace(sessions=list(sessions), agent=agent)
            with patch.object(jcl, "collect", return_value=[dict(r) for r in recs]):
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    got = jcl.pick_live_sessions(args, jcl.palette(), jcl.palette(), "x", "y")
            return sorted(r["session_id"] for r in got or [])
        self.assertEqual(picked("codex"), [SID])
        self.assertEqual(picked("claude"), ["c1", "c2"])
        self.assertEqual(picked("codex", "t:1.1"), [SID, "c1"])   # keyword plus a pane
        self.assertEqual(picked("all"), ["c1", "c2"])              # --agent defaults to claude
        self.assertEqual(picked("all", agent="all"), [SID, "c1", "c2"])

    def test_jsonl_tail_reads_newest_first_across_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            # Entry 3 is far longer than a chunk: it has to be stitched across reads
            entries = [{"n": i, "pad": "x" * (5000 if i == 3 else 300)} for i in range(8)]
            path.write_text("".join(json.dumps(e) + "\n" for e in entries))
            got = [e["n"] for e in jcl.jsonl_tail(path, (b'"n"',), chunk=256)]
            self.assertEqual(got, list(range(7, -1, -1)))
            # The read limit stops it short of the oldest entries
            short = [e["n"] for e in jcl.jsonl_tail(path, (b'"n"',), limit=1024, chunk=256)]
            self.assertEqual(short, [7, 6, 5])

    def test_codex_turn_reads_the_newest_turn_event(self):
        def event(kind, stamp):
            return json.dumps({"timestamp": stamp, "type": "event_msg", "payload": {"type": kind}}) + "\n"
        def at(stamp):
            return jcl.datetime.fromisoformat(stamp + "+00:00").timestamp()
        rec = record()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            with patch.object(jcl, "codex_rollout_path", return_value=path), \
                 patch.object(jcl, "proc_started_at", return_value=at("2026-10-01T00:00:00")):
                path.write_text(event("task_started", "2026-10-01T01:00:00Z")
                                + event("task_complete", "2026-10-01T01:05:00.123Z"))
                self.assertEqual(jcl.codex_turn(rec), ("idle", at("2026-10-01T01:05:00.123")))
                with path.open("a") as fh:
                    fh.write(event("task_started", "2026-10-01T02:00:00Z"))
                self.assertEqual(jcl.codex_turn(rec)[0], "busy")
                with path.open("a") as fh:  # interrupted with Esc
                    fh.write(event("turn_aborted", "2026-10-01T02:01:00Z"))
                self.assertEqual(jcl.codex_turn(rec)[0], "idle")
                # Started before this process was: killed mid-turn, resumed since
                path.write_text(event("task_started", "2026-09-30T23:00:00Z"))
                self.assertEqual(jcl.codex_turn(rec)[0], "idle")
        with patch.object(jcl, "codex_rollout_path", return_value=None):
            self.assertEqual(jcl.codex_turn(rec), ("idle", None))  # never had a message

    def test_claude_settings_follow_the_latest_reply_or_switch(self):
        def reply(model, effort=None, **extra):
            return json.dumps({"type": "assistant", "message": {"model": model},
                               "effort": effort, **extra}) + "\n"
        def stdout(text):
            return json.dumps({"type": "user", "message": {"role": "user",
                               "content": f"<local-command-stdout>{text}</local-command-stdout>"}}) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "projects" / "-w-my-repo"
            project.mkdir(parents=True)
            transcript = project / "abc.jsonl"
            transcript.write_text(
                reply("claude-opus-5", "xhigh") + reply("claude-opus-5-5", "max")
                + reply("claude-haiku-4-5", "low", isSidechain=True)  # a sub-agent's reply
                + reply("<synthetic>")
                + json.dumps({"type": "ai-title"}) + "\n")
            rec = record("claude", "abc", cwd="/w/my_repo", model="", effort="")

            def settings(**changes):
                return jcl.claude_settings(dict(rec, **changes))

            def append(*lines):
                with transcript.open("a") as fh:
                    fh.write("".join(lines))

            with patch.object(jcl, "CLAUDE_DIR", Path(tmp)):
                self.assertEqual(settings(), ("claude-opus-5-5", "max"))
                # Resumed from another directory: found by its id all the same
                self.assertEqual(settings(cwd="/else"), ("claude-opus-5-5", "max"))
                # Switched since the last reply: the switch is what it runs on,
                # and the effort still comes from the reply before it
                append(stdout("Set model to `Opus 5 (1M context)` and saved as your default"
                              " for new sessions\x1b[2m\x1b[22m\n\x1b[2m     Managed settings"
                              " pins \x1b[22m`Sonnet 5`\x1b[2m — that applies on restart"))
                self.assertEqual(settings(), ("claude-opus-5", "max"))
                append(stdout("Kept model as Fable 5.1"),
                       stdout("Set effort level to xhigh (saved as your default for new sessions): Deep"))
                self.assertEqual(settings(), ("claude-fable-5-1", "xhigh"))
                append(stdout("Set model to `Opus 5.5` and saved as your default for new sessions"
                              " with `medium` effort"))
                self.assertEqual(settings(), ("claude-opus-5-5", "medium"))
                append(stdout("Model 'nope' not found"))  # a refused model sets nothing
                self.assertEqual(settings(), ("claude-opus-5-5", "medium"))
                append(reply("claude-sonnet-5", "high"))
                self.assertEqual(settings(), ("claude-sonnet-5", "high"))

    def test_list_adds_columns_and_puts_paneless_sessions_below_a_rule(self):
        now = jcl.time.time()
        recs = [record("claude", "c1", status="waiting", status_at=(now - 7200) * 1000),
                record("claude", "c2", target="test:1.1", stopped=True, status="busy",
                       status_at=(now - 90) * 1000),
                record(target="", pane="", origin="desktop"),
                record(sid="cx", target="test:1.2", pane="%97")]
        with patch.object(jcl, "collect", return_value=recs), \
             patch.object(jcl, "claude_settings", return_value=("claude-opus-5-5", "max")), \
             patch.object(jcl, "codex_turn", return_value=("busy", now - 30)), \
             patch.object(jcl, "pane_tail", return_value="› Ask\n  GPT-6-Sol xhigh · /w\n"):
            rc, out = self.invoke(["list"])
        self.assertEqual(rc, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0].split(), ["TMUX", "WINDOW", "AGENT", "PID", "STATE", "ACTIVE",
                                            "MODEL", "EFFORT", "NAME", "CWD", "SESSION", "ID"])
        self.assertEqual(lines[2].split(), ["test:1.0", "agent", "claude", "12345", "waiting", "2h",
                                            "ago", "claude-opus-5-5", "max", "example", "/tmp", "c1"])
        self.assertEqual(lines[3].split()[4:9], ["stopped", "1m", "ago", "claude-opus-5-5", "max"])
        # A codex pane reads its footer; one without a pane, the thread's record
        self.assertEqual(lines[4].split()[:8], ["test:1.2", "agent", "codex", "12345",
                                                "busy", "now", "gpt-6-sol", "xhigh"])
        self.assertEqual(lines[5], lines[1])  # the rule between the two groups
        self.assertEqual(lines[6].split()[:8], ["-", "agent", "codex", "12345",
                                                "busy", "now", "gpt-test", "high"])
        self.assertEqual(lines[7], lines[1])
        self.assertIn("3 in tmux, 1 in desktop", lines[8])


class CompletionTests(unittest.TestCase):
    def test_agent_completion_for_set(self):
        command = "source completion/jcl_completion.bash\nCOMP_WORDS=(jcl set --agent co)\nCOMP_CWORD=3\n_jcl_complete\nprintf '%s\\n' \"${COMPREPLY[@]}\""
        proc = subprocess.run(["bash", "-c", command], cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(proc.stdout.strip(), "codex")

    def test_set_completes_panes_and_offers_model_effort_until_given(self):
        def complete(*words):
            line = " ".join(words)
            script = ("source completion/jcl_completion.bash\n"
                      "_jcl_live_ids() { printf '%s\\n' all claude 0:6.2; }\n"
                      f"COMP_WORDS=({' '.join(shlex.quote(w) for w in words)}); COMP_CWORD={len(words) - 1}\n"
                      f"COMP_LINE={shlex.quote(line)}; COMP_POINT=${{#COMP_LINE}}\n"
                      "_jcl_complete\nprintf '%s\\n' \"${COMPREPLY[@]}\"\n")
            proc = subprocess.run(["bash", "-c", script], cwd=ROOT, text=True, capture_output=True, check=True)
            return sorted(proc.stdout.split())
        self.assertEqual(complete("jcl", "set", ""), ["--effort", "--model", "0:6.2", "all", "claude"])
        self.assertEqual(complete("jcl", "set", "--effort", "max", ""), ["0:6.2", "all", "claude"])

    def test_agent_option_offered_on_each_session_command(self):
        for cmd in ("list", "save", "restore", "refresh", "exit-session", "set"):
            script = f"source completion/jcl_completion.bash\nCOMP_WORDS=(jcl {cmd} --a)\nCOMP_CWORD=2\n_jcl_complete\nprintf '%s\\n' \"${{COMPREPLY[@]}}\""
            proc = subprocess.run(["bash", "-c", script], cwd=ROOT, text=True, capture_output=True, check=True)
            self.assertIn("--agent", proc.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
