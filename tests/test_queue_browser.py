"""The AI page while the AI is taken (Seam 1): the place in the queue and "busy", in both languages, in headless
Chrome. Skipped the same way as the other browser tests when Chrome or the test tools are missing."""
import os
import subprocess
import threading
import unittest

from servedkit import REPO, ServedKit
from standins import ANSWER
from test_queue import MAIN, Ask
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class QueuePageTest(unittest.TestCase):
    def setUp(self):
        self.kit = ServedKit()
        self.kit.start()
        self.hold = threading.Event()
        self.kit.ai.holds.append(self.hold)
        self.asks = [Ask(self.kit, MAIN)]
        self.asks[0].line()   # another visitor's answer is running and stays so
        self.proc = None

    def tearDown(self):
        self.hold.set()
        if self.proc:
            self.proc.kill()
        for a in self.asks:
            a.close()
        self.kit.stop()

    def start_page(self, scenario):
        env = dict(os.environ, EK_TEST_URL=self.kit.url, EK_CHROME=find_chrome(), EK_TEST_ANSWER=ANSWER,
                   EK_TEST_SCENARIO=scenario, EK_TEST_LIBRARY_PORT=str(self.kit.library_port))
        self.proc = subprocess.Popen(["node", os.path.join(REPO, "tests", "browser", "ai-queue.js")], env=env, cwd=REPO,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def test_a_waiting_visitor_sees_the_place_in_both_languages_and_then_the_answer(self):
        self.assertIsNone(why_skip())
        self.start_page("queue")
        seen = []
        for line in self.proc.stdout:
            seen.append(line)
            if line.strip() == "waiting":
                break
        self.hold.set()   # the other answer finishes
        self.proc.stdin.write("go\n")
        self.proc.stdin.flush()
        rest = self.proc.communicate(timeout=60)[0]
        out = "".join(seen) + rest
        self.assertEqual(self.proc.returncode, 0, out)
        self.assertEqual(out.count("ok - "), 3, out)

    def test_the_sixth_waiting_visitor_is_told_busy_with_the_way_out(self):
        self.assertIsNone(why_skip())
        for n in range(1, 6):
            waiting = Ask(self.kit, MAIN)
            self.asks.append(waiting)
            self.assertEqual(waiting.line(), {"queue": n})
        self.start_page("busy")
        out = self.proc.communicate(timeout=60)[0]
        self.assertEqual(self.proc.returncode, 0, out)
        self.assertEqual(out.count("ok - "), 2, out)


if __name__ == "__main__":
    unittest.main()
