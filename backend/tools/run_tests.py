"""Run the entire pytest collection in sequential, disposable module processes.

Collection, per-module inventories and outcomes are recorded before the combined
coverage gate. Use the same runner locally and in CI; do not hand-select shards.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_job_handle = None


def _contain_windows_process() -> None:
    """Own this process and all descendants before importing/running pytest."""
    if os.name != "nt":
        return
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("min_working_set", ctypes.c_size_t),
            ("max_working_set", ctypes.c_size_t),
            ("active_processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimits),
            ("io", IoCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    global _job_handle
    _job_handle = kernel.CreateJobObjectW(None, None)
    if not _job_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway.
    if not kernel.SetInformationJobObject(_job_handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(_job_handle, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    # Keep the non-inheritable handle for this process's lifetime. Windows closes
    # it on exit/termination, killing descendants; explicit close would kill us.


def _child(args: argparse.Namespace) -> int:
    # Match python -m pytest: import the checkout being tested, rather than a
    # different editable installation when the runner is invoked by full path.
    sys.path.insert(0, str(Path.cwd()))
    import pytest

    inventory: dict[str, list[str]] = {}
    executed: set[str] = set()

    class Receipt:
        def pytest_collection_finish(self, session: pytest.Session) -> None:
            for item in session.items:
                module = item.path.relative_to(Path.cwd()).as_posix()
                inventory.setdefault(module, []).append(item.nodeid)
            if args.child == "run":
                expected = json.loads((args.output / "inventory.json").read_text(encoding="utf-8"))
                if inventory != {args.module: expected[args.module]}:
                    raise pytest.UsageError(f"Test inventory changed for {args.module}")

        def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
            executed.add(report.nodeid)

    command = (
        ["tests", "--collect-only", "--no-cov", "-q"]
        if args.child == "collect"
        else [
            args.module,
            "--cov=app",
            "--cov-append",
            "--cov-report=",
            "--cov-fail-under=0",
            "-q",
        ]
    )
    code = int(pytest.main(command, plugins=[Receipt()]))
    if args.child == "collect":
        (args.output / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    else:
        receipt = {"module": args.module, "pid": os.getpid(), "executed": sorted(executed), "exit": code}
        (args.output / "current-module.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        if code == 0 and executed != set(inventory[args.module]):
            print("Test inventory was not fully executed", file=sys.stderr)
            return 1
    return code


def _run(command: list[str], log: Path, timeout: int, env: dict[str, str]) -> int:
    with log.open("w", encoding="utf-8") as output:
        output.write(f"COMMAND: {command}\n")
        output.flush()
        with subprocess.Popen(
            command, stdout=output, stderr=subprocess.STDOUT, env=env, start_new_session=os.name != "nt"
        ) as process:
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()  # Held process handle; its owned job contains descendants.
                else:
                    os.killpg(process.pid, signal.SIGKILL)  # Our new, still-live session.
                process.wait()
                code = 124
            finally:
                if os.name != "nt":
                    # The group belongs to our start_new_session child. Dispose
                    # background members on success/failure as well as timeout.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # The owned group already exited completely.
            output.write(f"EXIT: {code}\n")
    print(f"{log.name}: exit {code}", flush=True)
    return code


def main() -> int:
    _contain_windows_process()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".test-results"))
    parser.add_argument("--timeout", type=int, default=300, help="Deadline in seconds per module/collection")
    parser.add_argument("--child", choices=["collect", "run"], help=argparse.SUPPRESS)
    parser.add_argument("--module", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.child:
        return _child(args)
    if any(args.output.iterdir()):
        parser.error("--output must be empty so previous results cannot count as this run")
    env = os.environ | {"COVERAGE_FILE": str(args.output / ".coverage"), "PYTHONUTF8": "1"}
    child = [sys.executable, str(Path(__file__).resolve()), "--output", str(args.output)]
    code = _run(child + ["--child", "collect"], args.output / "collection.log", args.timeout, env)
    if code:
        return code
    inventory = json.loads((args.output / "inventory.json").read_text(encoding="utf-8"))
    total = sum(len(items) for items in inventory.values())
    if not total or len({item for items in inventory.values() for item in items}) != total:
        print("Empty or duplicate test inventory", file=sys.stderr)
        return 1
    modules = []
    for index, module in enumerate(inventory):
        started = time.monotonic()
        code = _run(
            child + ["--child", "run", "--module", module], args.output / f"module-{index:04d}.log", args.timeout, env
        )
        if code:
            return code
        receipt = json.loads((args.output / "current-module.json").read_text(encoding="utf-8"))
        modules.append(receipt | {"seconds": time.monotonic() - started})
    summary = {"collected": total, "executed": sum(len(module["executed"]) for module in modules), "modules": modules}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for command in (
        [sys.executable, "-m", "coverage", "report", "--fail-under=87"],
        [sys.executable, "-m", "coverage", "xml"],
    ):
        code = _run(command, args.output / f"coverage-{command[3]}.log", args.timeout, env)
        if code:
            return code
    print(f"PASS: all {total} tests accounted for across {len(modules)} isolated modules; coverage >=87%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
