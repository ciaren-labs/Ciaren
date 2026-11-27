"""Failure reporting and teardown cases that the successful editor recording cannot cover."""

import errno
import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

import provider_walkthrough as walk


def windows_error(code):
    error = OSError("private-path-canary")
    error.winerror = code
    return error


class CleanupTests(unittest.TestCase):
    def test_primary_failure_survives_multiple_cleanup_errors(self):
        order = []
        transcript = StringIO()

        def close(label, exc=None):
            order.append(label)
            if exc:
                raise exc

        with (
            redirect_stdout(transcript),
            self.assertRaises(walk.Failed) as raised,
            walk.managed_run() as (stage, defer),
        ):
            defer("temporary workspace", lambda: close("directory", windows_error(267)))
            defer("server", lambda: close("server"))
            defer("browser", lambda: close("browser", RuntimeError("sensitive-response-canary")))
            stage("unsupported request")
            raise AssertionError("secret-header-canary")

        self.assertEqual(order, ["browser", "server", "directory"])
        self.assertEqual(transcript.getvalue(), "STAGE unsupported request\n")
        self.assertEqual(
            str(raised.exception).splitlines(),
            [
                "FAIL unsupported request: editor assertion failed",
                "CLEANUP browser: unexpected operation failure",
                "CLEANUP temporary workspace: Windows error 267",
            ],
        )

    def test_cleanup_failure_after_acceptance_is_not_success(self):
        with self.assertRaises(walk.Failed) as raised, walk.managed_run() as (_, defer):
            defer("temporary workspace", Mock(side_effect=windows_error(5)))
        self.assertEqual(str(raised.exception), "CLEANUP temporary workspace: Windows error 5")

    def test_windows_lock_is_retried_and_permanent_failures_surface(self):
        with patch.object(walk.time, "sleep") as sleep:
            transient = Mock()
            transient.cleanup.side_effect = [windows_error(32), windows_error(267), None]
            walk.remove_workspace(transient)
            self.assertEqual(transient.cleanup.call_count, 3)
            self.assertEqual(sleep.call_count, 2)

            denied = Mock()
            denied.cleanup.side_effect = windows_error(5)
            with self.assertRaises(OSError):
                walk.remove_workspace(denied)
            self.assertEqual(denied.cleanup.call_count, 6)

            unrelated = Mock()
            unrelated.cleanup.side_effect = OSError(errno.EIO, "private-path-canary")
            with self.assertRaises(OSError):
                walk.remove_workspace(unrelated)
            unrelated.cleanup.assert_called_once()

    def test_windows_consoleless_cleanup_targets_only_owned_tree(self):
        proc = Mock(pid=2345)
        proc.poll.return_value = None
        proc.send_signal.side_effect = OSError("no console")
        with (
            patch.object(walk.sys, "platform", "win32"),
            patch.object(walk.signal, "CTRL_BREAK_EVENT", 1, create=True),
            patch.dict(walk.os.environ, SYSTEMROOT="Windows"),
            patch.object(walk.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            walk.stop_server(proc)
        self.assertEqual(run.call_args.args[0][1:], ["/PID", "2345", "/T", "/F"])
        proc.wait.assert_called_once_with(timeout=10)

    def test_tree_shutdown_failure_still_reaps_owned_process(self):
        for error in (OSError(5, "private executable path"), subprocess.TimeoutExpired("private command", 10)):
            with self.subTest(kind=type(error).__name__):
                proc = Mock(pid=2345)
                proc.poll.return_value = None
                proc.send_signal.side_effect = OSError("no console")
                with (
                    patch.object(walk.sys, "platform", "win32"),
                    patch.object(walk.signal, "CTRL_BREAK_EVENT", 1, create=True),
                    patch.dict(walk.os.environ, SYSTEMROOT="Windows"),
                    patch.object(walk.subprocess, "run", side_effect=error),
                    self.assertRaisesRegex(walk.Failed, "^Owned server tree shutdown could not be confirmed.$"),
                ):
                    walk.stop_server(proc)
                proc.kill.assert_called_once()
                proc.wait.assert_called_once_with(timeout=5)


if __name__ == "__main__":
    unittest.main()
