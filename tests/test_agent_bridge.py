"""agent-bridge regressions. No real agent, daemon, or Codex queue is touched."""
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shlex
import socket
import stat
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

# What Claude Code 2.1.283's SendMessage wrote into an inbox, byte for byte, and
# a reply a Claude session sent to a reply socket (2026-10-12)
CAPTURED = '{"msgV":1,"msg_id":"42dff115-f898-48c0-aa7e-06892a784642","type":"user","message":{"role":"user","content":"<cross-session-message from=\\"uds:/tmp/cc-socks/1948062.sock\\" from-name=\\"claude-codex-cross-session-messaging\\" from-mode=\\"prompting\\">\\nagent-bridge wire-format probe: capture only, no reply needed.\\n</cross-session-message>"},"priority":"next","from":"uds:/tmp/cc-socks/1948062.sock"}\n'
CAPTURED_REPLY = '{"msgV":1,"msg_id":"1032f797-ec2f-42e4-b80e-ae8d736222ba","type":"user","message":{"role":"user","content":"<cross-session-message from=\\"uds:/tmp/cc-socks/1174056.sock\\" hop-chain=\\"3eccaeabecff8319f1ba29b9\\" from-name=\\"probe-recv\\" from-mode=\\"prompting\\">\\nsecond probe received\\n</cross-session-message>"},"priority":"next","from":"uds:/tmp/cc-socks/1174056.sock"}\n'
# A line Claude Desktop's own CLI, 2.1.293, wrote: from-session and hop-chain
# more in its envelope (2026-10-12)
CAPTURED_293 = '{"msgV":1,"msg_id":"b215045e-5b84-4b3e-8e3c-69fb03da484f","type":"user","message":{"role":"user","content":"<cross-session-message from=\\"uds:/tmp/cc-socks/2326136.sock\\" from-session=\\"local_f0172f2b-dd49-4d60-94be-0c7a8604c5d3\\" hop-chain=\\"61045271f6ebd4e4a7ad6bf1,846de9aa93c6d1aaeb51d846,61045271f6ebd4e4a7ad6bf1\\" from-name=\\"PSF 全局 ICM 管理功能\\" from-mode=\\"prompting\\">\\n2.1.293 wire-format sample\\n</cross-session-message>"},"priority":"next","from":"uds:/tmp/cc-socks/2326136.sock"}\n'


def envelope(text, sender="claude-a", address=ME):
    return (f'<cross-session-message from="{address}" from-name="{sender}" '
            f'from-mode="prompting">\n{text}\n</cross-session-message>')


def codex(sid, name="", empty=False):
    return {"agent": "codex", "session_id": sid, "name": name, "alive": True, "kind": "interactive",
            "empty": empty, "target": "t:1.0", "cwd": "/w"}


def claude(name, inbox="/tmp/cc-socks/1.sock"):
    return {"agent": "claude", "session_id": f"c-{name}", "name": name, "alive": True,
            "kind": "interactive", "inbox": inbox, "target": "t:2.0", "cwd": "/w"}


def short_tmp():
    """A directory whose sockets fit in AF_UNIX's 108 bytes."""
    return tempfile.TemporaryDirectory(dir="/tmp", prefix="ab-")


class EnvelopeAndNames(unittest.TestCase):
    def test_each_envelope_in_a_prompt_is_a_message(self):
        # Several envelopes in one content are several messages
        prompt = envelope("first") + "\n" + envelope("second &amp; last", sender="a &quot;b&quot;")
        found = ab.parse_envelopes(prompt)
        self.assertEqual([m["text"] for m in found], ["first", "second &amp; last"])
        self.assertEqual(found[1]["from_name"], 'a "b"')
        self.assertEqual(found[0]["from"], ME)
        self.assertEqual(ab.parse_envelopes("plain text, no envelope"), [])

    def test_names_are_titles_or_id_tails_and_never_clash(self):
        names = ab.unique_names([
            claude("Read-PSF-feature"),
            codex(ALPHA), codex(BRAVO),                       # untitled, same id head
            codex("01aaaaaa-0000-7000-8000-00000000aaaa", "Read PSF feature"),
            codex("01bbbbbb-0000-7000-8000-00000000bbbb", "Same  title"),
            codex("01cccccc-0000-7000-8000-00000000cccc", "Same title"),
        ])
        self.assertEqual(names[ALPHA], "codex-192bd8")
        self.assertEqual(names[BRAVO], "codex-7c129d")
        # Spaces as hyphens, as Claude names its sessions: copied whole, no quotes
        self.assertEqual(names["01aaaaaa-0000-7000-8000-00000000aaaa"], "Read-PSF-feature-aaaa")
        self.assertEqual(names["01bbbbbb-0000-7000-8000-00000000bbbb"], "Same-title")
        self.assertEqual(names["01cccccc-0000-7000-8000-00000000cccc"], "Same-title-cccc")

    def test_a_codex_message_says_who_sent_it_and_how_to_answer(self):
        text = ab.codex_message("claude a", ME, "hello")
        first, body = text.split("\n", 1)
        self.assertTrue(first.startswith("Message from @claude a - another agent. Reply with: "))
        self.assertIn(f"agent-bridge send --to {ME} ", first)
        self.assertIn("agent-bridge send --to 'Reply as ALPHA' ",
                      ab.codex_message("x", "Reply as ALPHA", "y"))
        self.assertEqual(body, "hello")


class OwnView(unittest.TestCase):
    def test_each_claude_session_gets_its_inbox_from_its_own_record(self):
        recs = [claude("claude-a", inbox=None) | {"pid": 1}, claude("claude-b", inbox=None) | {"pid": 2},
                codex(ALPHA, "Reply as ALPHA")]
        records = {1: {"messagingSocketPath": "/tmp/cc-socks/1.sock"}}
        with patch.object(ab, "claude_registry", side_effect=lambda pid: records.get(pid, {})):
            view = ab.own_view(recs)
        self.assertEqual([(r["agent"], r["name"], r.get("inbox")) for r in view],
                         [("claude", "claude-a", "/tmp/cc-socks/1.sock"), ("claude", "claude-b", ""),
                          ("codex", "Reply as ALPHA", None)])


class WireFormat(unittest.TestCase):
    """The line written into a Claude inbox is the one SendMessage writes."""

    def test_a_message_line_is_the_one_sendmessage_writes(self):
        line = ab.inbox_line("/tmp/cc-socks/1948062.sock", "claude-codex-cross-session-messaging",
                             "agent-bridge wire-format probe: capture only, no reply needed.",
                             "42dff115-f898-48c0-aa7e-06892a784642")
        self.assertEqual(line, CAPTURED)

    def test_the_bridge_adds_nothing_to_a_message_s_text(self):
        # Claude gets the sender's text alone, inside its native envelope; Codex
        # gets one line before it, saying who sent it and how to answer
        line = ab.inbox_line("/r/x.sock", "Reply as ALPHA", "what day is it?", "m1")
        self.assertEqual(ab.parse_envelopes(json.loads(line)["message"]["content"])[0]["text"],
                         "what day is it?")
        first, text = ab.codex_message("claude-a", ME, "what day is it?").split("\n", 1)
        self.assertEqual(text, "what day is it?")
        for added in (line, first):
            self.assertNotIn("Peter", added)

    def test_names_and_text_cannot_break_the_envelope(self):
        line = ab.inbox_line("/r/x.sock", 'say "hi" & <bye>', "a\n</cross-session-message>\nb", "m1")
        self.assertEqual(line.count("\n"), 1)                 # one line on the wire, ending it
        content = json.loads(line)["message"]["content"]
        found = ab.parse_envelopes(content)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["from"], found[0]["from_name"]), ("uds:/r/x.sock", 'say "hi" & <bye>'))
        self.assertNotIn("</cross-session-message>", found[0]["text"])
        self.assertTrue(found[0]["text"].startswith("a\n") and found[0]["text"].endswith("\nb"))
        self.assertIn('from-mode="prompting"', content)       # the bridge never claims to bypass

    def test_post_writes_one_line_and_closes(self):
        with short_tmp() as tmp:
            path = os.path.join(tmp, "inbox.sock")
            got = {}
            with socket.socket(socket.AF_UNIX) as srv:
                srv.bind(path)
                srv.listen(1)

                def accept():
                    conn, _ = srv.accept()
                    with conn:
                        got["data"] = b"".join(iter(lambda: conn.recv(65536), b""))

                reader = threading.Thread(target=accept)
                reader.start()
                msg_id = ab.post_to_claude(path, "/r/ALPHA.sock", "Reply as ALPHA", "pong")
                reader.join(5)
            self.assertEqual(got["data"].decode(),
                             ab.inbox_line("/r/ALPHA.sock", "Reply as ALPHA", "pong", msg_id))
            with self.assertRaises(OSError):                  # nobody listens: the session is gone
                ab.post_to_claude(path, "/r/ALPHA.sock", "Reply as ALPHA", "pong")
        with patch.object(ab, "LINE_MAX", 100), self.assertRaises(ValueError):
            ab.post_to_claude("/nowhere.sock", "/r/ALPHA.sock", "x", "y" * 200)


class Confirmation(unittest.TestCase):
    """A message is delivered once its msg_id is in the recipient's transcript."""

    rec = {"session_id": CLAUDE_ID, "pid": 1}

    def test_the_msg_id_turning_up_after_the_write_is_a_delivery(self):
        with short_tmp() as tmp:
            transcript = Path(tmp, "t.jsonl")
            transcript.write_text('{"origin": {"msg_id": "m1"}}\n')     # an earlier delivery
            offset = transcript.stat().st_size

            def arrive():
                time.sleep(0.3)
                with open(transcript, "a") as fh:
                    fh.write('{"origin": {"kind": "peer", "msg_id": "m2"}}\n')

            threading.Thread(target=arrive).start()
            self.assertEqual(ab.confirm_delivery(self.rec, transcript, offset, "m2", wait=5), "delivered")
            with patch.object(ab, "claude_registry", return_value={"status": "idle"}):
                # Only what came after the write counts
                self.assertEqual(ab.confirm_delivery(self.rec, transcript, offset, "m1", wait=0.2),
                                 "unconfirmed")

    def test_not_taken_yet_says_why_by_the_session_s_own_status(self):
        with patch.object(ab, "claude_transcript", return_value=None):
            for status, state in (("busy", "busy"), ("waiting", "waiting"), ("idle", "unconfirmed"),
                                  (None, "unconfirmed")):
                with patch.object(ab, "claude_registry", return_value={"status": status}):
                    self.assertEqual(ab.confirm_delivery(self.rec, None, 0, "m1", wait=0), state)

    def test_a_session_with_no_turn_yet_is_known_by_its_command_line(self):
        with short_tmp() as tmp:
            cmdline = Path(tmp, "cmdline")
            real_read = Path.read_bytes
            for argv, mode in ((["claude", "--dangerously-skip-permissions"], "bypassPermissions"),
                               (["claude", "--permission-mode", "plan"], "plan"),
                               (["claude", "--permission-mode=acceptEdits"], "acceptEdits"),
                               (["claude", "--model", "haiku"], "")):
                cmdline.write_bytes("\0".join(argv).encode() + b"\0")
                with patch.object(Path, "read_bytes",
                                  lambda self: real_read(cmdline) if str(self).endswith("/cmdline") else real_read(self)):
                    self.assertEqual(ab.permission_mode(self.rec, None), mode, argv)

    def test_a_session_whose_mode_holds_messages_is_not_taken_for_a_format_change(self):
        # Holding, it tells no address the bridge has: its last permission mode says so
        with short_tmp() as tmp, patch.object(ab, "claude_registry", return_value={"status": "idle"}), \
             patch.object(Path, "read_bytes", side_effect=OSError("no such process")):
            transcript = Path(tmp, "t.jsonl")
            for modes, state in ((["auto", "bypassPermissions"], "held"), (["default", "plan"], "held"),
                                 (["bypassPermissions", "auto"], "unconfirmed"), ([], "unconfirmed")):
                transcript.write_text("".join(f'{{"type":"user","permissionMode":"{m}"}}\n' for m in modes))
                self.assertEqual(ab.confirm_delivery(self.rec, transcript, 0, "m1", wait=0), state, modes)


class ReplySockets(unittest.TestCase):
    """Each Codex session's reply socket: where Claude sessions answer it."""

    def test_a_reply_is_queued_into_the_codex_session_whose_socket_it_came_to(self):
        with short_tmp() as tmp, patch.object(ab, "REPLY_DIR", Path(tmp, "r")):
            d = ab.Daemon()
            got = threading.Event()
            with patch.object(d, "inbound", side_effect=lambda req: got.set()) as inbound:
                self.assertTrue(d.open_reply(ALPHA))
                path = ab.reply_socket(ALPHA)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.connect(str(path))
                    sock.sendall(CAPTURED_REPLY.encode())
                self.assertTrue(got.wait(5))
            self.assertEqual(inbound.call_args.args[0], {"thread": ALPHA, "messages": [
                {"from": "uds:/tmp/cc-socks/1174056.sock", "from_name": "probe-recv",
                 "text": "second probe received"}]})
            d.close_reply(ALPHA)
            self.assertFalse(path.exists())

    def test_a_reply_from_claude_desktop_s_newer_cli_reads_the_same(self):
        d = ab.Daemon()
        with patch.object(d, "inbound") as inbound:
            d.reply_line(ALPHA, CAPTURED_293.encode())
        self.assertEqual(inbound.call_args.args[0]["messages"], [
            {"from": "uds:/tmp/cc-socks/2326136.sock", "from_name": "PSF 全局 ICM 管理功能",
             "text": "2.1.293 wire-format sample"}])

    def test_scans_keep_a_socket_for_each_codex_session_that_can_take_a_message(self):
        listed = [codex(ALPHA, "Reply as ALPHA"), codex(BRAVO, "Fresh", empty=True)]
        with short_tmp() as tmp, patch.object(ab, "REPLY_DIR", Path(tmp, "r")):
            d = ab.Daemon()
            with patch.object(ab.subprocess, "run",
                              side_effect=lambda *a, **k: SimpleNamespace(stdout=json.dumps(listed))):
                d.scan()
                self.assertEqual(sorted(d.replies), [ALPHA])     # nothing can queue into BRAVO yet
                self.assertTrue(ab.reply_socket(ALPHA).exists())
                listed = [codex(BRAVO, "Fresh")]                 # ALPHA gone, BRAVO had a message
                d.scan()
                self.assertEqual(sorted(d.replies), [BRAVO])
                self.assertFalse(ab.reply_socket(ALPHA).exists())
            d.close_reply(BRAVO)

    def test_claude_s_word_on_a_held_message_reaches_its_sender(self):
        d = ab.Daemon()
        d.sessions = [claude("claude-a", inbox="/tmp/cc-socks/222428.sock")]
        # As a 2.1.283 session in hold sent one (2026-10-12): who, and why, not which message
        notice = {"type": "control", "action": "peer_message_status", "status": "held",
                  "reason": "Your message is held for the recipient user's approval before it reaches"
                            " their Claude session (permission-mode parity).",
                  "from": "uds:/tmp/cc-socks/222428.sock", "msgV": 1,
                  "msg_id": "2e5c50da-5f40-4fcf-97c9-3fce2470d892"}
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")) as deliver:
            d.reply_line(ALPHA, json.dumps(notice).encode())
            d.reply_line(ALPHA, b"not json")
        deliver.assert_called_once_with(ALPHA, "agent-bridge: claude-a holds your message for its user's approval.")


class Routing(unittest.TestCase):
    def daemon(self):
        d = ab.Daemon()
        me = claude("claude-a", inbox="/tmp/cc-socks/533796.sock") | {"session_id": CLAUDE_ID}
        other = claude("claude-b", inbox="/tmp/cc-socks/42.sock") | {"session_id": "fcd17def-02fb-4afb-869d-cfb285482b52"}
        d.sessions = [codex(ALPHA, "Reply as ALPHA"), codex(BRAVO, "Reply as BRAVO"), me, other]
        return d

    def writing(self, d, state="delivered", **post):
        """Stub the writer and its confirmation: nothing is written anywhere."""
        return (patch.object(d, "open_reply", return_value=True),
                patch.object(ab, "post_to_claude", **(post or {"return_value": "m1"})),
                patch.object(ab, "confirm_delivery", return_value=state),
                patch.object(ab, "claude_transcript", return_value=None))

    def test_codex_to_codex_goes_straight_to_the_queue(self):
        d = self.daemon()
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")) as deliver:
            resp = d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "hi"})
        self.assertTrue(resp["ok"])
        deliver.assert_called_once_with(BRAVO, ab.codex_message("Reply-as-ALPHA", "Reply-as-ALPHA", "hi"))

    def test_codex_to_claude_is_written_into_its_inbox_from_the_codex_session_s_reply_socket(self):
        d = self.daemon()
        reply, post, confirm, transcript = self.writing(d)
        with reply, post as write, confirm, transcript:
            resp = d.send({"from": FROM_ALPHA, "to": "claude-b", "text": "pong"})
            by_address = d.send({"from": FROM_ALPHA, "to": ME, "text": "ping"})
        self.assertEqual((resp["ok"], resp["to"], resp["detail"]), (True, "claude-b", "delivered"))
        self.assertEqual(write.call_args_list[0].args,
                         ("/tmp/cc-socks/42.sock", ab.reply_socket(ALPHA), "Reply-as-ALPHA", "pong"))
        self.assertEqual(by_address["to"], "claude-a")
        self.assertEqual(write.call_args_list[1].args[0], "/tmp/cc-socks/533796.sock")

    def test_what_a_send_to_claude_reports(self):
        cases = [("busy", {}, True, "queued: it is busy"),
                 ("waiting", {}, True, "queued: it is waiting for its user"),
                 ("held", {}, True, "held: its permission mode keeps messages"),
                 ("unconfirmed", {}, True, "not confirmed: claude-b is idle and holds nothing"),
                 ("delivered", {"side_effect": OSError("refused")}, False, "has it exited?"),
                 ("delivered", {"side_effect": ValueError("2000000 characters")}, False, "too long")]
        for state, post, ok, said in cases:
            d = self.daemon()
            reply, write, confirm, transcript = self.writing(d, state, **post)
            with reply, write, confirm, transcript:
                resp = d.send({"from": FROM_ALPHA, "to": "claude-b", "text": "pong"})
            self.assertEqual(resp["ok"], ok, resp)
            self.assertIn(said, resp.get("detail") or resp.get("error"))
            self.assertEqual(resp.get("unconfirmed", False), state == "unconfirmed" and ok)

    def test_a_claude_name_must_name_one_live_session(self):
        d = self.daemon()
        d.sessions += [claude("twin") | {"session_id": "c-twin-1"}, claude("twin") | {"session_id": "c-twin-2"}]
        with patch.object(d, "scan") as scan:
            self.assertIn("no session 'nobody'",
                          d.send({"from": FROM_ALPHA, "to": "nobody", "text": "t"})["error"])
            scan.assert_called_once()                         # looked again before saying so
            self.assertIn("2 Claude sessions are named 'twin'",
                          d.send({"from": FROM_ALPHA, "to": "twin", "text": "t"})["error"])

    def test_refusals(self):
        d = self.daemon()
        with patch.object(d, "scan"):
            self.assertIn("no live codex session", d.send({"from": {"agent": "codex", "id": "gone"}, "to": "x", "text": "t"})["error"])
        self.assertIn("itself", d.send({"from": FROM_ALPHA, "to": "Reply as ALPHA", "text": "t"})["error"])
        self.assertIn("itself", d.send({"from": FROM_ALPHA, "to": f"uds:{ab.reply_socket(ALPHA)}",
                                        "text": "t"})["error"])
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")):
            for _ in range(ab.RATE_LIMIT[0]):
                self.assertTrue(d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["ok"])
            self.assertIn("too many", d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["error"])

    def test_an_undeliverable_message_is_reported_to_its_sender(self):
        d = self.daemon()
        told = threading.Event()
        with patch.object(ab, "deliver_to_codex", return_value=(False, "no message yet")), \
             patch.object(d, "open_reply", return_value=True), \
             patch.object(ab, "post_to_claude", side_effect=lambda *a: told.set() or "m9") as post:
            d.inbound({"thread": ALPHA, "messages": [{"from": ME, "from_name": "claude-a", "text": "x"}]})
            worker = threading.Thread(target=d.delivery_worker, daemon=True)
            worker.start()
            self.assertTrue(told.wait(5))
            d.stop_event.set()
        inbox, reply, name, text = post.call_args.args
        self.assertEqual((inbox, reply, name),
                         ("/tmp/cc-socks/533796.sock", ab.reply_socket(ALPHA), "agent-bridge"))
        self.assertIn("was not delivered: no message yet", text)

    def test_a_sender_hears_once_that_an_interrupted_session_holds_its_messages(self):
        d = self.daemon()
        notices = []
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")), \
             patch.object(ab, "interrupted_at", side_effect=[100.0, 100.0, 200.0]), \
             patch.object(d, "open_reply", return_value=True), \
             patch.object(ab, "post_to_claude", side_effect=lambda *a: notices.append(a[3]) or "m9"):
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
        d = self.daemon()
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")), \
             patch.object(ab, "interrupted_at", return_value=100.0):
            self.assertTrue(d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["held"])
        with patch.object(ab, "deliver_to_codex", return_value=(True, "queued")), \
             patch.object(ab, "interrupted_at", return_value=None):
            self.assertFalse(d.send({"from": FROM_ALPHA, "to": "Reply as BRAVO", "text": "t"})["held"])

    def test_peers_list_both_agents_with_who_can_receive(self):
        d = self.daemon()
        d.sessions.append(codex("01dddddd-0000-7000-8000-00000000dddd", "Fresh", empty=True))
        rows = {p["name"]: p["reachable"] for p in d.peers()}
        self.assertEqual(rows, {"Reply-as-ALPHA": "yes", "Reply-as-BRAVO": "yes",
                                "claude-a": "yes", "claude-b": "yes", "Fresh": "empty"})
        self.assertIn(CLAUDE_ID, [p["session_id"] for p in d.peers()])


class ById(unittest.TestCase):
    """A --to may be a session id, or its first 8 or more characters, as jcl shows it."""
    daemon = Routing.daemon
    writing = Routing.writing

    def test_ids_and_their_starts_resolve_for_both_agents(self):
        d = self.daemon()
        self.assertEqual(d.resolve(CLAUDE_ID), ("claude", "uds:/tmp/cc-socks/533796.sock"))
        self.assertEqual(d.resolve("6aa35b10"), ("claude", "uds:/tmp/cc-socks/533796.sock"))
        self.assertEqual(d.resolve(BRAVO), ("codex", BRAVO))
        self.assertEqual(d.resolve("01a12630-48c1"), ("codex", BRAVO))
        self.assertEqual(d.resolve("claude-b"), ("claude", "claude-b"))     # a Claude session's name
        # A Codex session's name, and the title it came from typed with its spaces
        self.assertEqual(d.resolve("Reply-as-BRAVO"), ("codex", BRAVO))
        self.assertEqual(d.resolve("Reply as BRAVO"), ("codex", BRAVO))
        self.assertEqual(d.resolve("uds:/tmp/cc-socks/9.sock"), ("claude", "uds:/tmp/cc-socks/9.sock"))
        self.assertEqual(d.resolve(f"uds:{ab.reply_socket(BRAVO)}"), ("codex", BRAVO))  # its reply socket
        # Codex ids are UUIDv7: sessions started in the same minute share their head
        with self.assertRaisesRegex(LookupError, "starts 2 session ids"):
            d.resolve("01a12630")

    def test_claude_to_codex_by_id_goes_straight_to_the_queue_with_its_own_inbox_to_reply_to(self):
        d = self.daemon()
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")) as deliver:
            resp = d.send({"from": FROM_CLAUDE, "to": "01a12630-48c1", "text": "hi"})
        self.assertTrue(resp["ok"], resp)
        deliver.assert_called_once_with(BRAVO, ab.codex_message("claude-a", "uds:/tmp/cc-socks/533796.sock", "hi"))

    def test_a_claude_sender_is_known_by_its_inbox(self):
        d = self.daemon()
        by_socket = {"agent": "claude", "id": "", "socket": "/tmp/cc-socks/533796.sock"}
        with patch.object(ab, "deliver_to_codex", return_value=(True, "Queued")) as deliver:
            self.assertTrue(d.send({"from": by_socket, "to": "01a12630-48c1", "text": "hi"})["ok"])
        deliver.assert_called_once_with(BRAVO, ab.codex_message("claude-a", "uds:/tmp/cc-socks/533796.sock", "hi"))

    def test_claude_to_claude_is_told_the_address_for_sendmessage(self):
        d = self.daemon()
        resp = d.send({"from": FROM_CLAUDE, "to": "fcd17def", "text": "hi"})
        self.assertEqual(resp["use_sendmessage"], "uds:/tmp/cc-socks/42.sock")
        self.assertIn("itself", d.send({"from": FROM_CLAUDE, "to": "6aa35b10", "text": "hi"})["error"])

    def test_codex_to_claude_by_id_is_written_into_its_inbox(self):
        d = self.daemon()
        reply, post, confirm, transcript = self.writing(d)
        with reply, post as write, confirm, transcript:
            resp = d.send({"from": FROM_ALPHA, "to": "6aa35b10", "text": "pong"})
        self.assertTrue(resp["ok"], resp)
        self.assertEqual(write.call_args.args[0], "/tmp/cc-socks/533796.sock")
        # The sender reads who got it and that it did
        self.assertEqual((resp["to"], resp["detail"]), ("claude-a", "delivered"))


class SendCommand(unittest.TestCase):
    def test_the_caller_is_whichever_agent_its_shell_belongs_to(self):
        self.assertEqual(ab.caller({"CODEX_THREAD_ID": ALPHA}), FROM_ALPHA)
        self.assertEqual(ab.caller({"CLAUDE_CODE_SESSION_ID": CLAUDE_ID,
                                    "CLAUDE_CODE_MESSAGING_SOCKET": "/tmp/cc-socks/533796.sock"}), FROM_CLAUDE)
        # By its inbox alone, which Claude Code documents for scripts
        self.assertEqual(ab.caller({"CLAUDE_CODE_MESSAGING_SOCKET": "/tmp/cc-socks/533796.sock"}),
                         {"agent": "claude", "id": "", "socket": "/tmp/cc-socks/533796.sock"})
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

    def test_a_send_not_seen_taken_says_so_without_failing(self):
        answer = {"ok": True, "to": "claude-a", "unconfirmed": True,
                  "detail": "not confirmed: claude-a is idle but has not taken it"}
        with patch.dict(ab.os.environ, {"CODEX_THREAD_ID": ALPHA}, clear=True), \
             patch.object(ab, "ensure_daemon", return_value=True), \
             patch.object(ab, "request", return_value=answer):
            rc, out, _ = run(["send", "--to", "claude-a", "hi"])
        self.assertEqual((rc, out), (0, "Sent to claude-a (not confirmed: claude-a is idle but has not taken it)\n"))


class Logs(unittest.TestCase):
    """Nothing cleans /var/tmp: the daemon keeps its log in size itself."""

    def test_the_log_is_turned_over_past_its_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "daemon.log"
            log.write_text("x" * 50)
            with patch.object(ab, "LOG", log), patch.object(ab, "LOG_MAX", 10), \
                 patch.object(ab.os, "dup2") as dup2:
                ab.turn_logs()
            self.assertEqual((Path(tmp) / "daemon.log.1").read_text(), "x" * 50)
            self.assertEqual(log.read_text(), "")                 # a new one, where stderr goes now
            self.assertEqual([call.args[1] for call in dup2.call_args_list], [1, 2])
            log.write_text("y")                                   # under the size: left alone
            with patch.object(ab, "LOG", log), patch.object(ab, "LOG_MAX", 10), \
                 patch.object(ab.os, "dup2") as dup2:
                ab.turn_logs()
            self.assertEqual(log.read_text(), "y")
            dup2.assert_not_called()


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
             "reachable": "yes", "session_id": BRAVO, "cwd": "/w"},
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
        # What --to takes; where and on what is jcl list's
        self.assertEqual(lines[0].split(), ["NAME", "AGENT", "SESSION", "ID"])
        rows = lines[2:6]
        self.assertEqual([row.split()[-1] for row in rows], [p["session_id"] for p in peers])
        self.assertEqual(set(lines[1]), {"─"})        # one unbroken line under the header
        self.assertEqual(lines[6], "")                # and a blank one before the summary
        self.assertIn(long_name, rows[3])             # a sender copies it: kept whole
        # Padded by screen columns: a CJK name does not push its row right
        starts = {ab._dwidth(row[:row.index(p["session_id"])]) for row, p in zip(rows, peers)}
        self.assertEqual(len(starts), 1, out)
        # Only what a message cannot reach is told, by name and why; nothing follows
        self.assertEqual(lines[7:], [f"4 sessions · 2 claude · 2 codex · not reachable: {long_name} (no inbox)"])
        with patch.object(ab, "ensure_daemon", return_value=True), \
             patch.object(ab, "request", return_value={"ok": True, "peers": peers[:3]}):
            _, out, _ = run(["peers"])
        self.assertEqual(out.splitlines()[-1], "3 sessions · 1 claude · 2 codex")

    def test_status_shows_each_codex_session_it_relays_for(self):
        status = {"ok": True, "pid": 77, "started": time.time() - 7300, "codex": [
            {"thread": ALPHA, "name": "Reply-as-ALPHA", "where": "t:1.0"},
            {"thread": BRAVO, "name": "Reply-as-BRAVO", "where": "desktop"}]}
        with patch.object(ab, "request", return_value=status):
            rc, out, _ = run(["status"])
        self.assertEqual(rc, 0)
        # Whether it runs, and for whom: by name and pane, app for Codex Desktop's own
        self.assertEqual(out.splitlines(), [
            f"Daemon 77, up 2h, log {ab.LOG}",
            "Relaying for 2 Codex sessions: Reply-as-ALPHA (t:1.0), Reply-as-BRAVO (app)"])
        with patch.object(ab, "request", return_value={"ok": True, "pid": 77, "codex": []}):
            _, out, _ = run(["status"])
        self.assertIn("No Codex session to relay for", out)

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
                         ["peers", "status", "start", "stop", "restart"])   # send is the agents'

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

    def test_restart_shows_status_once_the_first_scan_is_done(self):
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
        self.assertIn("{send,peers,status,start,stop,restart}", out)
        listed = re.findall(r"^    (\S+)", out, re.M)
        self.assertEqual(listed, ["send", "peers", "status", "start", "stop", "restart"])


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
