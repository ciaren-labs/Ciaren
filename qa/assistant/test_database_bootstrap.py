"""Fail initialization deliberately and check that disposable credentials stay in the input pipe."""

import secrets
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from database_smoke import database


class DatabaseBootstrapTest(unittest.TestCase):
    def test_failed_initialization_keeps_credentials_out_of_files_and_diagnostics(self):
        for engine in ("postgresql", "mysql"):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as temp:
                work = Path(temp)
                args = Namespace(
                    engine=engine,
                    pg_bindir=work,
                    mysqld=work / "mysqld",
                    pg_share=None,
                    mysql_basedir=None,
                    mysql_messages=None,
                )
                marker = secrets.token_hex(24).encode()

                def fail_init(cmd, **kwargs):
                    for file in work.iterdir():
                        if file.is_file():
                            self.assertFalse(marker in file.read_bytes(), "credential in temporary file")
                    self.assertFalse(marker in repr((cmd, kwargs["env"])).encode(), "credential in launch parameters")
                    self.assertTrue(marker in kwargs["input"], "missing initializer input")
                    self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
                    self.assertIn(kwargs["stderr"], (subprocess.DEVNULL, subprocess.STDOUT))
                    return subprocess.CompletedProcess(cmd, 1)

                with (
                    patch("database_smoke.secrets.token_hex", return_value=marker.decode()),
                    patch("database_smoke.subprocess.run", side_effect=fail_init),
                    self.assertRaisesRegex(RuntimeError, r"^Private database initialization failed with status 1\Z"),
                    database(args, work),
                ):
                    self.fail("server started after initialization failed")


if __name__ == "__main__":
    unittest.main()
