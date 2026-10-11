"""agent-bridge regressions. No real agent, daemon, or Codex queue is touched."""
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("agent_bridge", str(ROOT / "nv-tools/agent-bridge"))
spec = importlib.util.spec_from_loader(loader.name, loader)
ab = importlib.util.module_from_spec(spec)
loader.exec_module(ab)

# The tests must not write into the running daemon's log
ab.log = lambda msg: None

ME = "uds:/tmp/cc-socks/533796.sock"
ALPHA = "01a12630-3e0d-7640-82f0-608bfe192bd8"
BRAVO = "01a12630-48c1-7e22-8fb2-c611eb7c129d"
CLAUDE_ID = "6aa35b10-6771-425b-9ce0-81b8fbdbb3da"
FROM_ALPHA = {"agent": "codex", "id": ALPHA}
FROM_CLAUDE = {"agent": "claude", "id": CLAUDE_ID, "socket": "/tmp/cc-socks/533796.sock"}


def envelope(text, sender="claude-a", address=ME):
    return (f'<cross-session-message from="{address}" from-name="{sender}" '
            f'from-mode="prompting">\n{text}\n</cross-session-message>')


def codex(sid, name="", empty=False):
    return {"agent": "codex", "session_id": sid, "name": name, "alive": True, "kind": "interactive",
            "empty": empty, "target": "t:1.0", "cwd": "/w"}


def claude(name, inbox="/tmp/cc-socks/1.sock"):
    return {"agent": "claude", "session_id": f"c-{name}", "name": name, "alive": True,
            "kind": "interactive", "inbox": inbox, "target": "t:2.0", "cwd": "/w"}


class FakeProc:
    def __init__(self):
        self.stdin = io.StringIO()
        self.pid = 4242

    def poll(self):
        return None


class EnvelopeAndNames(unittest.TestCase):
    def test_each_envelope_in_a_prompt_is_a_message(self):
        # Messages that queued up while the stand-in was busy arrive together
        prompt = envelope("first") + "\n" + envelope("second &amp; last", sender="a &quot;b&quot;")
        found = ab.parse_envelopes(prompt)
        self.assertEqual([m["text"] for m in found], ["first", "second &amp; last"])
        self.assertEqual(found[1]["from_name"], 'a "b"')
        self.assertEqual(found[0]["from"], ME)
        self.assertEqual(ab.parse_envelopes("plain text, no envelope"), [])

    def test_names_are_titles_or_id_tails_and_never_clash(self):
        names = ab.unique_names([
            claude("Read PSF feature"),
            codex(ALPHA), codex(BRAVO),                       # untitled, same id head
            codex("01aaaaaa-0000-7000-8000-00000000aaaa", "Read PSF feature"),
            codex("01bbbbbb-0000-7000-8000-00000000bbbb", "Same title"),
            codex("01cccccc-0000-7000-8000-00000000cccc", "Same title"),
        ])
        self.assertEqual(names[ALPHA], "codex-192bd8")
        self.assertEqual(names[BRAVO], "codex-7c129d")
        self.assertEqual(names["01aaaaaa-0000-7000-8000-00000000aaaa"], "Read PSF feature (aaaa)")
        self.assertEqual(names["01bbbbbb-0000-7000-8000-00000000bbbb"], "Same title")
        self.assertEqual(names["01cccccc-0000-7000-8000-00000000cccc"], "Same title (cccc)")

    def test_a_codex_message_says_who_sent_it_and_how_to_answer(self):
        text = ab.codex_message("claude a", ME, "hello")
        first, body = text.split("\n", 1)
        self.assertTrue(first.startswith("Message from @claude a - another agent, not Peter."))
        self.assertIn(f"agent-bridge send --to {ME} ", first)
        self.assertIn("agent-bridge send --to 'Reply as ALPHA' ",
                      ab.codex_message("x", "Reply as ALPHA", "y"))
        self.assertEqual(body, "hello")


class OwnView(unittest.TestCase):
    def test_stand_ins_listed_by_jcl_are_dropped_and_inboxes_read(self):
        # Kept, a stand-in's name would count as taken and it would be renamed
        # away from itself on every scan
        recs = [claude("claude-a", inbox=None) | {"pid": 1}, claude("Reply as ALPHA", inbox=None) | {"pid": 2},
                codex(ALPHA, "Reply as ALPHA")]
        sessions = {1: '{"messagingSocketPath": "/tmp/cc-socks/1.sock"}'}

        def read(path):
            pid = int(Path(path).stem)
            if pid not in sessions:
                raise OSError("no file")
            return sessions[pid]

        with patch.object(ab, "is_stand_in", side_effect=lambda pid: pid == 2), \
             patch.object(Path, "read_text", lambda self: read(self)):
            view = ab.own_view(recs)
        self.assertEqual([(r["agent"], r["name"], r.get("inbox")) for r in view],
                         [("claude", "claude-a", "/tmp/cc-socks/1.sock"), ("codex", "Reply as ALPHA", None)])


class Hooks(unittest.TestCase):
    env = {"AGENT_BRIDGE_PROXY": ALPHA}

    def test_inbound_hands_over_and_always_blocks(self):
        with patch.object(ab, "request", return_value={"ok": True}) as req:
            out = ab.hook("inbound", {"prompt": envelope("hi codex")}, env=self.env)
        self.assertEqual(out["decision"], "block")
        sent = req.call_args.args[0]
        self.assertEqual((sent["op"], sent["thread"]), ("inbound", ALPHA))
        self.assertEqual(sent["messages"], [{"from": ME, "from_name": "claude-a", "text": "hi codex"}])
        # Unblocked, the prompt would reach the relay model: block even when the daemon is gone
        with patch.object(ab, "request", side_effect=OSError("gone")):
            out = ab.hook("inbound", {"prompt": envelope("hi")}, env=self.env)
        self.assertEqual(out["decision"], "block")
        self.assertIn("unreachable", out["reason"])

    def test_the_daemons_own_trigger_reaches_the_model(self):
        with patch.object(ab, "request") as req:
            self.assertIsNone(ab.hook("inbound", {"prompt": f"{ab.OUTBOUND_MARK} send now"}, env=self.env))
        req.assert_not_called()

    def test_an_unrecognised_prompt_is_still_handed_over_whole(self):
        with patch.object(ab, "request", return_value={"ok": True}) as req:
            ab.hook("inbound", {"prompt": "a future format"}, env=self.env)
        self.assertEqual(req.call_args.args[0]["messages"],
                         [{"from": "", "from_name": "", "text": "a future format"}])

    def test_pretool_puts_the_real_message_in_and_refuses_an_unasked_send(self):
        with patch.object(ab, "request", return_value={"outbound": {"to": ME, "message": "exact"}}):
            out = ab.hook("pretool", {"tool_input": {"to": "placeholder"}}, env=self.env)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "allow")
        self.assertEqual(out["updatedInput"], {"to": ME, "message": "exact"})
        with patch.object(ab, "request", return_value={"outbound": None}):
            out = ab.hook("pretool", {}, env=self.env)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")

    def test_posttool_reports_and_ends_the_turn(self):
        response = {"success": True, "message": "queued there"}
        with patch.object(ab, "request") as req:
            out = ab.hook("posttool", {"tool_response": response}, env=self.env)
        self.assertEqual(out["continue"], False)
        self.assertEqual(req.call_args.args[0], {"op": "result", "thread": ALPHA, "response": response})


class StandInSend(unittest.TestCase):
    def test_send_waits_for_the_hooks_and_returns_what_sendmessage_said(self):
        stand_in = ab.StandIn(ALPHA, "Reply as ALPHA")
        stand_in.proc = FakeProc()
        result = {}
        worker = threading.Thread(target=lambda: result.update(r=stand_in.send(ME, "exact text")))
        worker.start()
        for _ in range(100):
            if stand_in.pending:
                break
            time.sleep(0.01)
        self.assertIn(ab.OUTBOUND_MARK, stand_in.proc.stdin.getvalue())
        self.assertNotIn("exact text", stand_in.proc.stdin.getvalue())  # the model never sees it
        self.assertEqual(stand_in.claim(), {"to": ME, "message": "exact text"})
        self.assertIsNone(stand_in.claim())                             # handed out once only
        stand_in.settle({"success": False, "message": "Not sent: no such session"})
        worker.join(5)
        self.assertEqual(result["r"], (False, "Not sent: no such session"))
        self.assertEqual(stand_in.sent, 1)


class Routing(unittest.TestCase):
    def daemon(self):
        d = ab.Daemon()
        me = claude("claude-a", inbox="/tmp/cc-socks/533796.sock") | {"session_id": CLAUDE_ID}
        other = claude("claude-b", inbox="/tmp/cc-socks/42.sock") | {"session_id": "fcd17def-02fb-4afb-869d-cfb285482b52"}
        d.sessions = [codex(ALPHA, "Reply as ALPHA"), codex(BRAVO, "Reply as BRAVO"), me, other]
        stand_in = ab.StandIn(ALPHA, "Reply as ALPHA")
        stand_in.name, stand_in.proc = "Reply as ALPHA", FakeProc()
        d.stand_ins[ALPHA] = stand_in
        return d, stand_in

    def test_codex_to_codex_goes_straight_to_the_queue(self):
        d, _ = self.daemon()
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")) as deliver:
            resp = d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "hi"})
        self.assertTrue(resp["ok"])
        deliver.assert_called_once_with(BRAVO, ab.codex_message("Reply as ALPHA", "Reply as ALPHA", "hi"))

    def test_codex_to_claude_goes_through_its_stand_in(self):
        d, stand_in = self.daemon()
        with patch.object(stand_in, "send", return_value=(True, "queued there")) as send, \
             patch.object(ab, "deliver_to_codex") as deliver:
            resp = d.send({"from": FROM_ALPHA, "to": ME, "text": "pong"})
        self.assertTrue(resp["ok"])
        send.assert_called_once_with(ME, "pong")
        deliver.assert_not_called()

    def test_refusals(self):
        d, _ = self.daemon()
        with patch.object(d, "scan"):
            self.assertIn("no live codex session", d.send({"from": {"agent": "codex", "id": "gone"}, "to": "x", "text": "t"})["error"])
        self.assertIn("itself", d.send({"from": FROM_ALPHA, "to": "Reply as ALPHA", "text": "t"})["error"])
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")):
            for _ in range(ab.RATE_LIMIT[0]):
                self.assertTrue(d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["ok"])
            self.assertIn("too many", d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["error"])

    def test_an_undeliverable_message_is_reported_to_its_sender(self):
        d, stand_in = self.daemon()
        told = threading.Event()
        with patch.object(ab, "deliver_to_codex", return_value=(False, "no message yet")), \
             patch.object(stand_in, "send", side_effect=lambda to, text: told.set() or (True, "")) as send:
            d.inbound({"thread": ALPHA, "messages": [{"from": ME, "from_name": "claude-a", "text": "x"}]})
            worker = threading.Thread(target=d.delivery_worker, daemon=True)
            worker.start()
            self.assertTrue(told.wait(5))
            d.stop_event.set()
        to, text = send.call_args.args
        self.assertEqual(to, ME)
        self.assertIn("was not delivered: no message yet", text)

    def test_a_sender_hears_once_that_an_interrupted_session_holds_its_messages(self):
        d, stand_in = self.daemon()
        notices = []
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")), \
             patch.object(ab, "interrupted_at", side_effect=[100.0, 100.0, 200.0]), \
             patch.object(stand_in, "send", side_effect=lambda to, text: notices.append(text) or (True, "")):
            worker = threading.Thread(target=d.delivery_worker, daemon=True)
            worker.start()
            for n in range(3):  # two messages in one interruption, one in the next
                d.inbound({"thread": ALPHA, "messages": [{"from": ME, "from_name": "claude-a", "text": f"{n}"}]})
                deadline = time.monotonic() + 5
                while not d.deliveries.empty() and time.monotonic() < deadline:
                    time.sleep(0.05)
                time.sleep(0.2)
            d.stop_event.set()
        self.assertEqual(len(notices), 2, notices)
        self.assertIn("its last turn was interrupted", notices[0])

    def test_a_send_into_an_interrupted_session_says_it_is_held(self):
        d, _ = self.daemon()
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")), \
             patch.object(ab, "interrupted_at", return_value=100.0):
            self.assertTrue(d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["held"])
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")), \
             patch.object(ab, "interrupted_at", return_value=None):
            self.assertFalse(d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["held"])

    def test_peers_list_both_agents_with_who_can_receive(self):
        d, _ = self.daemon()
        d.sessions.append(codex("01dddddd-0000-7000-8000-00000000dddd", "Fresh", empty=True))
        rows = {p["name"]: p["reachable"] for p in d.peers()}
        self.assertEqual(rows, {"Reply as ALPHA": "yes", "Reply as BRAVO": "codex only",
                                "claude-a": "yes", "claude-b": "yes", "Fresh": "empty"})
        self.assertIn(CLAUDE_ID, [p["session_id"] for p in d.peers()])


class ById(unittest.TestCase):
    """A --to may be a session id, or its first 8 or more characters, as jcl shows it."""
    daemon = Routing.daemon

    def test_ids_and_their_starts_resolve_for_both_agents(self):
        d, _ = self.daemon()
        self.assertEqual(d.resolve(CLAUDE_ID), ("claude", "uds:/tmp/cc-socks/533796.sock"))
        self.assertEqual(d.resolve("6aa35b10"), ("claude", "uds:/tmp/cc-socks/533796.sock"))
        self.assertEqual(d.resolve(BRAVO), ("codex", BRAVO))
        self.assertEqual(d.resolve("01a12630-48c1"), ("codex", BRAVO))
        self.assertEqual(d.resolve("claude-b"), ("claude", "claude-b"))     # a name: SendMessage's to find
        self.assertEqual(d.resolve("uds:/tmp/cc-socks/9.sock"), ("claude", "uds:/tmp/cc-socks/9.sock"))
        # Codex ids are UUIDv7: sessions started in the same minute share their head
        with self.assertRaisesRegex(LookupError, "starts 2 session ids"):
            d.resolve("01a12630")

    def test_claude_to_codex_by_id_goes_straight_to_the_queue_with_its_own_inbox_to_reply_to(self):
        d, _ = self.daemon()
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")) as deliver:
            resp = d.send({"from": FROM_CLAUDE, "to": "01a12630-48c1", "text": "hi"})
        self.assertTrue(resp["ok"], resp)
        deliver.assert_called_once_with(BRAVO, ab.codex_message("claude-a", "uds:/tmp/cc-socks/533796.sock", "hi"))

    def test_claude_to_claude_is_told_the_address_for_sendmessage(self):
        d, _ = self.daemon()
        resp = d.send({"from": FROM_CLAUDE, "to": "fcd17def", "text": "hi"})
        self.assertEqual(resp["use_sendmessage"], "uds:/tmp/cc-socks/42.sock")
        self.assertIn("itself", d.send({"from": FROM_CLAUDE, "to": "6aa35b10", "text": "hi"})["error"])

    def test_codex_to_claude_by_id_goes_to_its_inbox_through_the_stand_in(self):
        d, stand_in = self.daemon()
        with patch.object(stand_in, "send", return_value=(True, "queued there")) as send:
            resp = d.send({"from": FROM_ALPHA, "to": "6aa35b10", "text": "pong"})
        self.assertTrue(resp["ok"], resp)
        send.assert_called_once_with("uds:/tmp/cc-socks/533796.sock", "pong")
        # The sender reads who got it and that it did, not SendMessage's answer
        self.assertEqual((resp["to"], resp["detail"]), ("claude-a", "delivered"))


class SendCommand(unittest.TestCase):
    def test_the_caller_is_whichever_agent_its_shell_belongs_to(self):
        self.assertEqual(ab.caller({"CODEX_THREAD_ID": ALPHA}), FROM_ALPHA)
        self.assertEqual(ab.caller({"CLAUDE_CODE_SESSION_ID": CLAUDE_ID,
                                    "CLAUDE_CODE_MESSAGING_SOCKET": "/tmp/cc-socks/533796.sock"}), FROM_CLAUDE)
        self.assertIsNone(ab.caller({}))

    def test_send_runs_inside_an_agent_session_only(self):
        with patch.dict(ab.os.environ, {}, clear=True), \
             patch("sys.stderr", new_callable=io.StringIO) as err:
            rc = ab.main(["send", "--to", "x", "hi"])
        self.assertEqual(rc, 2)
        self.assertIn("CLAUDE_CODE_SESSION_ID", err.getvalue())

    def test_a_claude_target_from_claude_prints_the_address_to_use(self):
        answer = {"ok": False, "use_sendmessage": "uds:/tmp/cc-socks/42.sock", "error": "x"}
        with patch.dict(ab.os.environ, {"CLAUDE_CODE_SESSION_ID": CLAUDE_ID}, clear=True), \
             patch.object(ab, "ensure_daemon", return_value=True), \
             patch.object(ab, "request", return_value=answer), \
             patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = ab.main(["send", "--to", "fcd17def", "hi"])
        self.assertEqual(rc, 3)
        self.assertIn("Use SendMessage with to='uds:/tmp/cc-socks/42.sock'", out.getvalue())

    def test_codex_s_own_warnings_are_not_what_a_send_reports(self):
        noise = "WARNING: failed to clean up stale arg0 temp dirs: Directory not empty (os error 39)"
        done = SimpleNamespace(returncode=0, stdout=f"Queued message 1 for thread {ALPHA}.\n",
                               stderr=noise + "\n")
        with patch.object(ab.subprocess, "run", return_value=done):
            self.assertEqual(ab.deliver_to_codex(ALPHA, "hi"), (True, "queued"))
        refused = SimpleNamespace(returncode=1, stdout="", stderr=(
            f"{noise}\nError: failed to queue session message: thread/queue/add failed: failed to"
            f" read thread: invalid thread-store request: no rollout found for thread id {ALPHA}\n"))
        with patch.object(ab.subprocess, "run", return_value=refused):
            ok, reason = ab.deliver_to_codex(ALPHA, "hi")
        self.assertFalse(ok)
        self.assertIn("has had no message yet", reason)

    def test_a_held_send_says_so(self):
        answer = {"ok": True, "detail": "queued", "to": "Reply as BRAVO", "held": True}
        with patch.dict(ab.os.environ, {"CODEX_THREAD_ID": ALPHA}, clear=True), \
             patch.object(ab, "ensure_daemon", return_value=True), \
             patch.object(ab, "request", return_value=answer):
            rc, out, _ = run(["send", "--to", "Reply as BRAVO", "hi"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), [
            "Sent to Reply as BRAVO (queued)",
            "Held: its last turn was interrupted, so it reads queued messages only after its next typed one"])


class Logs(unittest.TestCase):
    """Nothing cleans /var/tmp: the daemon keeps its logs in size itself."""

    def test_logs_are_turned_over_and_a_gone_session_s_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            log = run_dir / "daemon.log"
            log.write_text("x" * 50)
            mine, gone, fresh = (run_dir / f"stand-in-{name}.log" for name in ("aaaaaaaa", "bbbbbbbb", "cccccccc"))
            mine.write_text("y" * 50)
            gone.write_text("z")
            fresh.write_text("z")
            os.utime(gone, (time.time() - 2 * 86400,) * 2)
            with patch.object(ab, "RUN_DIR", run_dir), patch.object(ab, "LOG", log), \
                 patch.object(ab, "LOG_MAX", 10), \
                 patch.object(ab.os, "dup2") as dup2:
                ab.turn_logs({"stand-in-aaaaaaaa.log"})
            self.assertEqual((run_dir / "daemon.log.1").read_text(), "x" * 50)
            self.assertEqual(log.read_text(), "")                 # a new one, where stderr goes now
            self.assertEqual([call.args[1] for call in dup2.call_args_list], [1, 2])
            self.assertEqual((run_dir / "stand-in-aaaaaaaa.log.1").read_text(), "y" * 50)
            self.assertEqual(mine.read_text(), "")                # emptied in place: it appends
            self.assertFalse(gone.exists())                       # its session gone a day and more
            self.assertTrue(fresh.exists())                       # gone, but only just


class Interrupted(unittest.TestCase):
    """A Codex session stopped with Esc holds what is queued for it until its next typed message."""

    def rollout(self, home, *events):
        day = Path(home, "sessions/2026/10/11")
        day.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"timestamp": at, "type": "event_msg", "payload": dict(type=kind, **extra)})
                 for at, kind, extra in events]
        (day / f"rollout-2026-10-11T10-00-00-{ALPHA}.jsonl").write_text("\n".join(lines) + "\n")

    @staticmethod
    def stamp(epoch):
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")

    def test_only_an_interruption_this_process_saw_and_nothing_since(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as home, \
             patch.object(ab, "proc_started_at", return_value=now - 3600):
            rec = {"session_id": ALPHA, "agent_home": home, "pid": os.getpid()}
            self.assertIsNone(ab.interrupted_at(rec))                      # no rollout yet
            self.rollout(home, (self.stamp(now - 60), "task_started", {}),
                         (self.stamp(now - 30), "turn_aborted", {"reason": "interrupted"}))
            self.assertAlmostEqual(ab.interrupted_at(rec), now - 30, delta=1)
            self.rollout(home, (self.stamp(now - 30), "turn_aborted", {"reason": "interrupted"}),
                         (self.stamp(now - 20), "task_started", {}),
                         (self.stamp(now - 10), "task_complete", {}))
            self.assertIsNone(ab.interrupted_at(rec))                      # typed into since
            self.rollout(home, (self.stamp(now - 30), "turn_aborted", {"reason": "replaced"}))
            self.assertIsNone(ab.interrupted_at(rec))                      # not an Esc
        # Interrupted before this process started: a resume, holding nothing
        with tempfile.TemporaryDirectory() as home, \
             patch.object(ab, "proc_started_at", return_value=now):
            rec = {"session_id": ALPHA, "agent_home": home, "pid": os.getpid()}
            self.rollout(home, (self.stamp(now - 30), "turn_aborted", {"reason": "interrupted"}))
            self.assertIsNone(ab.interrupted_at(rec))


def run(argv):
    """main(argv) -> (exit status, stdout, stderr), colourless as a pipe has them."""
    with patch("sys.stdout", new_callable=io.StringIO) as out, \
         patch("sys.stderr", new_callable=io.StringIO) as err:
        try:
            rc = ab.main(argv)
        except SystemExit as exc:          # -h
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


class CommandLine(unittest.TestCase):
    """What a person running agent-bridge by hand sees: jcl's tables and words."""

    def test_peers_is_an_address_book(self):
        long_name = "a name longer than the thirty-six columns jcl list keeps"
        peers = [  # in the daemon's order, which is jcl's
            {"name": "PSF 全局 ICM 管理功能", "agent": "codex", "where": "desktop",
             "reachable": "codex only", "session_id": BRAVO, "cwd": "/w"},
            {"name": "claude-a", "agent": "claude", "where": "t:2.0", "reachable": "yes",
             "session_id": CLAUDE_ID, "cwd": "/w"},
            {"name": "Reply as ALPHA", "agent": "codex", "where": "t:1.0", "reachable": "yes",
             "session_id": ALPHA, "cwd": "/w"},
            {"name": long_name, "agent": "claude", "where": "-", "reachable": "no",
             "session_id": "fcd17def-02fb-4afb-869d-cfb285482b52", "cwd": "/w"}]
        with patch.object(ab, "ensure_daemon", return_value=True), \
             patch.object(ab, "request", return_value={"ok": True, "peers": peers}), \
             patch.object(ab, "caller", return_value=None):
            rc, out, _ = run(["peers"])
        lines = out.splitlines()
        self.assertEqual(rc, 0)
        # What --to takes and whether it gets there; where and on what is jcl list's
        self.assertEqual(lines[0].split(), ["NAME", "AGENT", "SESSION", "ID", "REACHABLE"])
        rows = lines[2:6]
        self.assertEqual([row.split()[-1] for row in rows], ["only", "yes", "yes", "no"])
        self.assertEqual(set(lines[1]), {"─"})        # one unbroken line under the header
        self.assertEqual(lines[6], "")                # and a blank one before the summary
        self.assertIn(long_name, rows[3])             # a sender copies it: kept whole
        # Padded by screen columns: a CJK name does not push its row right
        starts = {ab._dwidth(row[:row.index(p["session_id"])]) for row, p in zip(rows, peers)}
        self.assertEqual(len(starts), 1, out)
        self.assertEqual(lines[7], "4 sessions · 2 claude · 2 codex · 2 reachable"
                                   " · 1 codex only · 1 not reachable")
        self.assertTrue(lines[8].startswith("Send with: agent-bridge send --to "))

    def test_status_shows_each_stand_in_beside_its_codex_session(self):
        status = {"ok": True, "pid": 77, "started": time.time() - 7300, "stand_ins": [
            {"thread": ALPHA, "name": "Reply as ALPHA", "wanted": "Reply as ALPHA", "pid": 4242,
             "alive": True, "rss_mb": 205, "uptime": 3700, "sent": 3, "where": "t:1.0"},
            {"thread": BRAVO, "name": "", "wanted": "Reply as BRAVO", "pid": 4343,
             "alive": False, "rss_mb": 0, "uptime": 90, "sent": 0, "where": "desktop"}]}
        with patch.object(ab, "request", return_value=status):
            rc, out, _ = run(["status"])
        lines = out.splitlines()
        self.assertEqual(rc, 0)
        self.assertEqual(lines[0], f"Daemon 77, up 2h, log {ab.LOG}")
        self.assertEqual(lines[1].split(), ["CODEX", "NAME", "STAND-IN", "RSS", "UP", "SENT",
                                            "CODEX", "SESSION", "ID"])
        self.assertEqual(lines[3].split(), ["t:1.0", "Reply", "as", "ALPHA", "4242", "205", "MB",
                                            "1h", "3", ALPHA])
        self.assertEqual(lines[4].split(), ["app", "Reply", "as", "BRAVO", "4343", "exited", "0", "MB",
                                            "1m", "0", BRAVO])
        self.assertEqual(lines[-2:], ["", "2 stand-ins · 205 MB"])

    def test_status_when_no_daemon_runs_says_what_starts_one(self):
        with patch.object(ab, "request", side_effect=OSError("no socket")):
            rc, out, err = run(["status"])
        self.assertEqual((rc, err), (1, ""))          # a state, said with the rest of status
        self.assertEqual(out.splitlines(), [
            "agent-bridge is not running: Claude and Codex sessions cannot message each other.",
            "Start it with: agent-bridge start"])

    def test_under_jcl_bridge_it_names_that_and_leaves_send_out(self):
        with patch.object(ab, "PROG", "jcl bridge"), \
             patch.object(ab, "request", side_effect=OSError("no socket")):
            _, out, _ = run(["status"])
            _, help_text, _ = run(["-h"])
        self.assertIn("Start it with: jcl bridge start", out)
        self.assertTrue(help_text.startswith("usage: jcl bridge "), help_text)
        self.assertEqual(re.findall(r"^    (\S+)", help_text, re.M),
                         ["peers", "status", "scan", "start", "stop", "restart"])   # send is the agents'

    def test_start_leaves_a_running_daemon_alone(self):
        with patch.object(ab, "request", return_value={"ok": True, "pid": 77}), \
             patch.object(ab, "ensure_daemon") as ensure:
            rc, out, _ = run(["start"])
        self.assertEqual(rc, 0)
        self.assertIn("agent-bridge daemon 77 is already running", out)
        ensure.assert_not_called()

    def test_start_brings_back_a_stopped_daemon(self):
        answers = [OSError("no socket"), {"ok": True, "pid": 78}]
        with patch.object(ab, "request", side_effect=answers), \
             patch.object(ab, "ensure_daemon", return_value=True) as ensure:
            rc, out, _ = run(["start"])
        self.assertEqual(rc, 0)
        self.assertIn("Started agent-bridge daemon 78", out)
        ensure.assert_called_once()

    def test_restart_shows_status_once_the_stand_ins_are_back(self):
        calls = []
        with patch.object(ab, "cmd_stop", side_effect=lambda a: calls.append("stop") or 0), \
             patch.object(ab, "cmd_start", side_effect=lambda a: calls.append("start") or 0), \
             patch.object(ab, "request", side_effect=lambda req, **kw: calls.append(req["op"]) or {}), \
             patch.object(ab, "cmd_status", side_effect=lambda a: calls.append("status") or 0):
            self.assertEqual(ab.main(["restart"]), 0)
        self.assertEqual(calls, ["stop", "start", "scan", "status"])

    def test_alone_it_runs_status_which_starts_nothing(self):
        with patch.object(ab, "cmd_status", return_value=0) as status, \
             patch.object(ab, "ensure_daemon") as ensure:
            self.assertEqual(ab.main([]), 0)
        status.assert_called_once()
        ensure.assert_not_called()

    def test_help_leaves_out_what_only_agent_bridge_runs(self):
        rc, out, _ = run(["-h"])
        self.assertEqual(rc, 0)
        self.assertIn("{send,peers,status,scan,start,stop,restart}", out)
        listed = re.findall(r"^    (\S+)", out, re.M)
        self.assertEqual(listed, ["send", "peers", "status", "scan", "start", "stop", "restart"])


class Completion(unittest.TestCase):
    """completion/agent-bridge_completion.bash, kept in step with the parser."""

    def complete(self, *words, ids=()):
        script = ("source completion/agent-bridge_completion.bash\n"
                  f"_agent_bridge_session_ids() {{ printf '%s\\n' {' '.join(ids)}; }}\n"
                  f"COMP_WORDS=({' '.join(shlex.quote(w) for w in words)}); COMP_CWORD={len(words) - 1}\n"
                  "_agent_bridge_complete\nprintf '%s\\n' \"${COMPREPLY[@]}\"\n")
        proc = subprocess.run(["bash", "-c", script], cwd=ROOT, text=True, capture_output=True, check=True)
        return sorted(proc.stdout.split())

    def test_commands_and_options_are_the_parser_s(self):
        _, out, _ = run(["-h"])
        commands = re.search(r"\{([a-z,]+)\}", out)[1].split(",")
        self.assertEqual(self.complete("agent-bridge", ""), sorted(commands))
        for command in commands:
            _, out, _ = run([command, "-h"])
            options = sorted(set(re.findall(r"(?<![\w-])(--?[a-z][a-z-]*)", out.split("options:")[1])))
            self.assertEqual(self.complete("agent-bridge", command, "-"), options, command)

    def test_to_offers_session_ids(self):
        self.assertEqual(self.complete("agent-bridge", "send", "--to", "01a1", ids=(ALPHA, CLAUDE_ID)),
                         [ALPHA])
        self.assertEqual(self.complete("agent-bridge", "send", ""), ["--to"])  # until it is given
        self.assertEqual(self.complete("agent-bridge", "send", "--to", ALPHA, ""), [])


if __name__ == "__main__":
    unittest.main()
