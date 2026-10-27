"""Stopping Chrome's process group after a render (render/build_cv.py), with the OS call faked so it runs anywhere."""
import signal
import unittest
from unittest import mock

from render import build_cv


def killpg_raising(error):
    return mock.patch.object(build_cv.os, "killpg", side_effect=error)


class KillGroup(unittest.TestCase):
    def test_kills_the_whole_group(self):
        with mock.patch.object(build_cv.os, "killpg") as killpg:
            build_cv._kill_group(4321)
        killpg.assert_called_once_with(4321, signal.SIGKILL)

    def test_a_group_that_is_already_gone_is_fine(self):
        with killpg_raising(ProcessLookupError):
            build_cv._kill_group(4321)

    def test_macos_refusal_for_an_exited_leader_is_tolerated(self):
        with killpg_raising(PermissionError(1, "Operation not permitted")), mock.patch.object(build_cv.sys, "platform", "darwin"):
            build_cv._kill_group(4321)

    def test_a_refusal_on_linux_still_raises(self):
        with killpg_raising(PermissionError(1, "Operation not permitted")), mock.patch.object(build_cv.sys, "platform", "linux"):
            with self.assertRaises(PermissionError):
                build_cv._kill_group(4321)


if __name__ == "__main__":
    unittest.main()
