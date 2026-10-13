"""Observable contracts for the release suite's process isolation and accounting."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

RUNNER = Path(__file__).resolve().parents[1] / "tools" / "run_tests.py"


def _project(tmp_path: Path, modules: dict[str, str]) -> Path:
    (tmp_path / "app.py").write_text("def value():\n    return 42\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    for name, code in modules.items():
        (tests / name).write_text(code, encoding="utf-8")
    return tmp_path


def _run(project: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--output", "results", "--timeout", str(timeout)],
        cwd=project,
        env=os.environ | {"PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_suite_runner_accounts_for_every_test_and_combines_coverage(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        {
            "test_a.py": "import app\ndef test_value():\n    assert app.value() == 42\n    app.marker = 'mutated'\n",
            "test_b.py": "import app, pytest\n@pytest.mark.parametrize('value', [1, 2])\n"
            "def test_values(value):\n    assert app.other() == 99\n"
            "    assert app.marker == 'clean'\n    assert value > 0\n",
        },
    )
    (project / "app.py").write_text(
        "def value():\n    return 42\ndef other():\n    return 99\nmarker = 'clean'\n", encoding="utf-8"
    )
    result = _run(project)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads((project / "results" / "summary.json").read_text())
    assert receipt["collected"] == receipt["executed"] == 3
    assert len(receipt["modules"]) == 2
    assert (project / "coverage.xml").is_file()


def test_suite_runner_rejects_coverage_below_release_threshold(tmp_path: Path) -> None:
    project = _project(tmp_path, {"test_a.py": "import app\ndef test_value():\n    assert app.value() == 42\n"})
    (project / "app.py").write_text("def value():\n    return 42\ndef other():\n    return 99\n", encoding="utf-8")
    result = _run(project)
    assert result.returncode != 0
    assert "fail-under=87" in (project / "results" / "coverage-report.log").read_text()
    assert not (project / "coverage.xml").exists()


def test_suite_runner_stops_on_a_failed_module(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        {
            "test_a.py": "def test_failure():\n    assert False\n",
            "test_b.py": "from pathlib import Path\ndef test_not_run():\n    Path('ran').write_text('yes')\n",
        },
    )
    result = _run(project)
    assert result.returncode != 0
    assert not (project / "ran").exists()
    assert not (project / "coverage.xml").exists()
    assert "test_a.py" in (project / "results" / "module-0000.log").read_text()


def test_suite_runner_rejects_changed_inventory_before_execution(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        {
            "test_a.py": "from pathlib import Path\ndef test_change_inventory():\n"
            "    Path('tests/test_b.py').write_text('def test_changed():\\n    assert True\\n')\n",
            "test_b.py": "def test_original():\n    assert True\n",
        },
    )
    result = _run(project)
    assert result.returncode != 0
    assert "inventory changed" in (project / "results" / "module-0001.log").read_text()
    assert not (project / "coverage.xml").exists()


@pytest.mark.parametrize("outcome, expected", [("pass", 0), ("fail", 1), ("timeout", 124)])
def test_suite_runner_stops_owned_descendants(tmp_path: Path, outcome: str, expected: int) -> None:
    ending = {"pass": "assert app.value() == 42", "fail": "assert False", "timeout": "time.sleep(60)"}[outcome]
    project = _project(
        tmp_path,
        {
            "test_hang.py": "import app, subprocess, sys, time\nfrom pathlib import Path\ndef test_hang():\n"
            "    subprocess.Popen([sys.executable, 'background.py'])\n"
            "    deadline = time.monotonic() + 10\n"
            "    while not Path('heartbeat').exists():\n"
            "        assert time.monotonic() < deadline\n        time.sleep(.02)\n"
            f"    {ending}\n",
        },
    )
    (project / "background.py").write_text(
        "from pathlib import Path\nimport time\n"
        "deadline = time.monotonic() + 30\nwhile time.monotonic() < deadline:\n"
        "    with Path('heartbeat').open('a') as output:\n        output.write('.')\n    time.sleep(.02)\n",
        encoding="utf-8",
    )
    result = _run(project, timeout=15 if outcome == "timeout" else 30)
    assert result.returncode == expected, result.stdout + result.stderr
    heartbeat = project / "heartbeat"
    assert heartbeat.is_file(), result.stdout + result.stderr
    before = heartbeat.read_bytes()
    time.sleep(0.2)
    assert heartbeat.read_bytes() == before
    assert (project / "coverage.xml").exists() == (outcome == "pass")


def test_release_publication_waits_for_full_matrix_and_both_builds() -> None:
    workflows = RUNNER.parents[2] / ".github" / "workflows"
    package = yaml.load((workflows / "package.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    backend = yaml.load((workflows / "backend-tests.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    for publisher in ("publish-server", "publish-client"):
        assert set(package["jobs"][publisher]["needs"]) == {"build-server", "build-client", "release-tests"}
        assert "always()" not in package["jobs"][publisher]["if"]
        assert "github.event_name == 'push'" in package["jobs"][publisher]["if"]
    assert package["jobs"]["release-tests"]["uses"] == "./.github/workflows/backend-tests.yml"
    assert "workflow_call" in backend["on"]
    assert "tags" not in backend["on"]["push"]
    steps = backend["jobs"]["test"]["steps"]
    assert any(step.get("run") == "uv run python tools/run_tests.py" for step in steps)
    summary = backend["jobs"]["test-summary"]
    assert summary["needs"] == "test"
    assert "needs.test.result" in summary["steps"][0]["run"]
    matrix = backend["jobs"]["setup"]["steps"][0]["run"]
    assert "github.ref_type" in matrix and '= "tag"' in matrix
    full = json.loads(matrix.split("full='")[1].split("'", 1)[0])["include"]
    assert {(entry["os"], entry["python-version"]) for entry in full} == {
        ("ubuntu-latest", "3.12"),
        ("ubuntu-latest", "3.13"),
        ("ubuntu-latest", "3.14"),
        ("windows-latest", "3.12"),
        ("windows-latest", "3.14"),
        ("macos-latest", "3.12"),
        ("macos-latest", "3.14"),
    }


@pytest.mark.parametrize(
    "event, ref_type, base, expected",
    [
        ("push", "tag", "", 7),
        ("pull_request", "branch", "main", 5),
        ("push", "branch", "", 1),
        ("workflow_dispatch", "branch", "", 7),
        ("schedule", "branch", "", 7),
    ],
)
def test_backend_selector_emits_the_required_matrix(
    tmp_path: Path, event: str, ref_type: str, base: str, expected: int
) -> None:
    workflow = RUNNER.parents[2] / ".github/workflows/backend-tests.yml"
    backend = yaml.load(workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    script = backend["jobs"]["setup"]["steps"][0]["run"]
    for name, value in {"event_name": event, "ref_type": ref_type, "base_ref": base}.items():
        script = script.replace("${{ github." + name + " }}", value)
    path = tmp_path / "selector.sh"
    path.write_text(script, encoding="utf-8", newline="\n")
    if os.name == "nt":
        # Windows' system32/bash.exe starts WSL; use the Git Bash that CI/hooks use.
        git_exec = Path(subprocess.check_output(["git", "--exec-path"], text=True).strip())
        bash = str(git_exec.parents[2] / "bin/bash.exe")
    else:
        bash = shutil.which("bash")
        assert bash, "Release selector verification requires bash"
    output = tmp_path / "github-output"
    result = subprocess.run(
        [bash, "--noprofile", "--norc", path.as_posix()],
        env=os.environ | {"GITHUB_OUTPUT": output.as_posix()},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    matrix = json.loads(output.read_text(encoding="utf-8").removeprefix("matrix="))
    assert len(matrix["include"]) == expected
