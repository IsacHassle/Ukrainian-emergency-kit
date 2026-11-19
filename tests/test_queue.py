"""Seam 1, the AI queue: one answer at a time across the three modes, up to 5 waiting with their places, a
sixth told "busy", and a closed page leaving the queue. Driven over HTTP against the slow stand-in AI.

No test sleeps for a fixed time: a running answer is kept running with a hold (the stand-in stops after the
first word until the test releases it), and tests wait for what they expect to see."""
import http.client
import json
import os
import socket
import ssl
import subprocess
import threading
import time
import unittest

from servedkit import ServedKit
from standins import ANSWER

BOOKS, MAIN, SMALL = "books-chat", "chat-main", "chat-small"


def until(cond, what, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for " + what)


class Ask:
    """One visitor's request, read line by line as the stream arrives. close() is the page being closed."""

    def __init__(self, kit, mode=MAIN, text="How do I stop bleeding?", https=False, wait=True):
        if mode == BOOKS:
            path, payload = "/ai-api/books-chat", {"messages": [{"role": "user", "content": text}]}
        else:
            model = kit.facts["ai"]["models"]["main" if mode == MAIN else "small"]
            path, payload = "/ai-api/chat", {"model": model, "messages": [{"role": "user", "content": text}]}
        if https:   # the same site on the https port (phones that opened the map over https use the AI there too)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
            self.conn = http.client.HTTPSConnection("127.0.0.1", kit.port + 352, timeout=15, context=context)
        else:
            self.conn = http.client.HTTPConnection("127.0.0.1", kit.port, timeout=15)
        self.conn.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
        self.resp = self.conn.getresponse() if wait else None   # headers come with the first line, so this returns once something is known

    def line(self):
        raw = self.resp.readline()
        return json.loads(raw) if raw.strip() else None

    def lines(self):
        out = []
        while True:
            d = self.line()
            if d is None:
                return out
            out.append(d)

    def text(self):
        return "".join(d.get("message", {}).get("content", "") for d in self.lines())

    def close(self):
        if self.resp:
            self.resp.close()   # the response holds the socket open until it is closed too
        self.conn.close()


def make_certificate(kit):
    """A throwaway certificate for the test kit (tools/certs/server.crt and server.key), as scripts/make-cert.sh
    leaves one; the web server then also listens on its https port (port + 352)."""
    folder = os.path.join(kit.kit_dir, "tools", "certs")
    os.makedirs(folder, exist_ok=True)
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=localhost",
                    "-keyout", os.path.join(folder, "server.key"), "-out", os.path.join(folder, "server.crt")],
                   check=True, capture_output=True)
    kit.restart()


class QueueTest(unittest.TestCase):
    HTTPS = False   # the same tests run again over the https port in HttpsQueueTest

    def setUp(self):
        self.kit = ServedKit()
        self.kit.start()
        if self.HTTPS:
            make_certificate(self.kit)
        self.holds = []
        self.asks = []

    def tearDown(self):
        for h in self.holds:
            h.set()
        for a in self.asks:
            a.close()
        self.kit.stop()

    def hold_next(self):
        h = threading.Event()
        self.holds.append(h)
        self.kit.ai.holds.append(h)
        return h

    def ask(self, *a, **kw):
        x = Ask(self.kit, *a, https=self.HTTPS, **kw)
        self.asks.append(x)
        return x

    def running(self, mode=MAIN):
        """An answer that is running and stays so until the returned event is set."""
        h = self.hold_next()
        first = self.ask(mode)
        self.assertIn("sources" if mode == BOOKS else "message", first.line())
        if mode == BOOKS:
            self.assertIn("message", first.line())
        return first, h

    def test_two_answers_never_run_at_the_same_time_across_the_modes(self):
        h = self.hold_next()
        a = self.ask(MAIN)
        a.line()
        others = [self.ask(SMALL), self.ask(BOOKS)]
        results = {}
        threads = [threading.Thread(target=lambda i=i, o=o: results.__setitem__(i, o.lines())) for i, o in enumerate(others)]
        for t in threads:
            t.start()
        time.sleep(0.2)   # a short beat for a wrong implementation to start a second answer
        self.assertEqual(len(self.kit.ai.chat_requests), 1)   # nobody else reached the AI, not even From sources' planning call
        h.set()
        for t in threads:
            t.join(15)
        self.assertEqual(self.kit.ai.max_active, 1)
        for lines in results.values():
            self.assertEqual("".join(d.get("message", {}).get("content", "") for d in lines), ANSWER)
        self.assertEqual(len([d for d in results[1] if "sources" in d]), 1)

    def test_a_waiting_request_gets_its_place_and_every_change_of_it(self):
        _, h = self.running()
        b = self.ask(SMALL)
        self.assertEqual(b.line(), {"queue": 1})
        c = self.ask(BOOKS)
        self.assertEqual(c.line(), {"queue": 2})
        h.set()
        lines_b = b.lines()
        self.assertEqual("".join(d.get("message", {}).get("content", "") for d in lines_b), ANSWER)
        self.assertTrue(all("queue" not in d for d in lines_b))   # b was already first: no further queue line
        lines_c = c.lines()
        self.assertEqual(lines_c[0], {"queue": 1})   # moved up when b started
        self.assertEqual(list(lines_c[1]), ["sources"])   # then its answer, From sources style
        self.assertEqual("".join(d.get("message", {}).get("content", "") for d in lines_c[2:]), ANSWER)

    def test_a_request_that_finds_nobody_ahead_gets_no_queue_line(self):
        a = self.ask(MAIN)
        self.assertIn("message", a.line())
        self.assertTrue(all("queue" not in d for d in a.lines()))

    def test_the_sixth_waiting_request_is_told_busy_at_once(self):
        self.running()
        waiting = [self.ask(MAIN) for _ in range(5)]
        self.assertEqual([w.line() for w in waiting], [{"queue": n} for n in range(1, 6)])
        sixth = self.ask(BOOKS)
        self.assertEqual(sixth.lines(), [{"busy": True}])   # alone, and then the stream ends
        self.assertEqual(len(self.kit.ai.chat_requests), 1)   # it never reached the AI

    def test_closing_a_waiting_page_frees_its_place(self):
        self.running()
        waiting = [self.ask(MAIN) for _ in range(5)]
        for n, w in enumerate(waiting, 1):
            self.assertEqual(w.line(), {"queue": n})
        waiting[1].close()
        waiting[2].close()
        # the 4th and 5th move up, possibly through a place in between
        for w, place in ((waiting[3], 2), (waiting[4], 3)):
            d = w.line()
            while d != {"queue": place}:
                d = w.line()
        late = self.ask(MAIN)
        self.assertEqual(late.line(), {"queue": 4})   # there is room again: not busy

    def test_closing_a_page_while_its_answer_streams_hands_over_at_once(self):
        a, h = self.running(BOOKS)   # silent after its first word: only the closed connection can tell the server
        b = self.ask(MAIN)
        self.assertEqual(b.line(), {"queue": 1})
        a.close()
        self.assertEqual("".join(d.get("message", {}).get("content", "") for d in b.lines()), ANSWER)   # b ran while a's AI was still held
        self.assertFalse(h.is_set())

    def test_closing_a_page_that_waits_for_its_turn_does_not_start_its_answer(self):
        _, h = self.running()
        b = self.ask(BOOKS)
        self.assertEqual(b.line(), {"queue": 1})
        c = self.ask(MAIN)
        self.assertEqual(c.line(), {"queue": 2})
        b.close()
        self.assertEqual(c.line(), {"queue": 1})
        h.set()
        self.assertEqual(c.text(), ANSWER)
        self.assertEqual(len(self.kit.ai.chat_requests), 2)   # a and c only: b's search never ran

    def test_closing_a_page_during_the_planning_call_starts_no_answer_and_frees_the_turn(self):
        """Story 65: From sources first asks the AI to plan the search. A page that closes meanwhile must not
        get an answer made for it, and the next visitor's turn comes as soon as the call returns."""
        plan = threading.Event()
        self.holds.append(plan)
        self.kit.ai.plan_holds.append(plan)
        gone = self.ask(BOOKS, wait=False)   # its first line only comes after the planning call, so do not wait for it
        until(lambda: len(self.kit.ai.chat_requests) == 1, "the planning call to reach the AI")
        gone.close()
        time.sleep(0.5)   # the web server notices the closed connection while the planning call is still open
        waiting = self.ask(MAIN)
        self.assertEqual(waiting.line(), {"queue": 1})
        plan.set()
        self.assertEqual(waiting.text(), ANSWER)
        streamed = [r for r in self.kit.ai.chat_requests if r.get("stream")]
        self.assertEqual(len(streamed), 1)   # only the waiting visitor's answer was made


class HttpsQueueTest(QueueTest):
    """Every queue test again, over the https port: the Watch that notices a closed page cannot peek at a TLS socket."""
    HTTPS = True


if __name__ == "__main__":
    unittest.main()
