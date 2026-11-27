"""Exercise a packaged editor with synthetic CSVs. Paid DeepSeek needs explicit opt-in."""

import argparse
import io
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from editor_smoke import KEY, ROOT, fixture_env
from playwright.sync_api import Error as BrowserError
from playwright.sync_api import TimeoutError as BrowserTimeout
from playwright.sync_api import expect, sync_playwright

DIRECT_KEY = "CIAREN_ASSISTANT_DEEPSEEK_API_KEY"
BUILD = "Keep all orders by sku. Flag ready_to_fulfill when catalog_status equals active. Sort by order_id."
GUIDE = "How do I connect the two inputs of a Join?"
REPAIR = "Order 104 is missing. Keep every order, including orders without a catalog match."
UNSUPPORTED = "Schedule a nightly refresh. Leave the Join unchanged."


class Failed(Exception):
    """A fixed diagnostic suitable for printing; never embed request or exception contents."""


# Match only fixed Ciaren diagnostics. Never echo arbitrary server detail, nested validation input or provider text.
TURN_ERRORS = {
    "The provider returned an unsupported Join proposal.": "JOIN_PLAN_SCHEMA",
    "The repair references an unavailable Join.": "JOIN_REFERENCE_MISMATCH",
    "The provider returned an incomplete structured answer.": "PROVIDER_OUTPUT_INVALID",
    "The provider request timed out.": "PROVIDER_TIMEOUT",
    "The provider request or response transfer failed.": "PROVIDER_TRANSPORT",
    "Provider request failed or returned an incomplete structured answer.": "PROVIDER_TRANSPORT_OR_OUTPUT",
    "Assistant hourly turn budget reached.": "LOCAL_TURN_BUDGET",
    "Choose an available dataset in this flow's project.": "INPUT_UNAVAILABLE",
    "Invalid input version.": "INPUT_VERSION",
    "Assistant request cancelled.": "TURN_CANCELLED",
    "Too many open proposals. Retry after existing proposals expire.": "PROPOSAL_CAPACITY",
}


def turn_error_code(response):
    try:
        body = response.json()
    except (ValueError, BrowserError):
        return "UNCLASSIFIED"
    detail = body.get("detail") if isinstance(body, dict) else None
    if not isinstance(detail, str):
        return "UNCLASSIFIED"
    if detail in TURN_ERRORS:
        return TURN_ERRORS[detail]
    for status in (400, 401, 402, 403, 404, 422, 429, 500, 502, 503, 504):
        if detail == f"Provider returned HTTP {status}. Check credentials, model and quota.":
            return f"UPSTREAM_HTTP_{status}"
    return "UNCLASSIFIED"


def check_turn(response, before, snapshot):
    failure = "" if response.ok else f"HTTP {response.status} [{turn_error_code(response)}]. "
    try:
        after = snapshot()
    except Exception:
        raise Failed(failure + "Saved state could not be verified.") from None
    if after != before:
        raise Failed(failure + "A proposal changed server state before approval.")
    if failure:
        raise Failed(failure.rstrip(". "))


def require(condition, message):
    if not condition:
        raise Failed(message)


def reason(exc):
    if isinstance(exc, Failed):
        return str(exc)  # Only fixed checks and numeric HTTP status are used to construct Failed.
    if isinstance(exc, (TimeoutError, BrowserTimeout, subprocess.TimeoutExpired)):
        return "timed out"
    if isinstance(exc, OSError):
        code = getattr(exc, "winerror", None)
        if isinstance(code, int):
            return f"Windows error {code}"
        return f"OS error {exc.errno}" if isinstance(exc.errno, int) else "OS error"
    if isinstance(exc, AssertionError):
        return "editor assertion failed"
    if isinstance(exc, BrowserError):
        return "browser operation failed"
    return "unexpected operation failure"


@contextmanager
def managed_run():
    """Save the acceptance outcome before closing each owned resource in reverse order."""
    current = "initialization"
    errors = []

    def stage(name):
        nonlocal current
        current = name
        print(f"STAGE {name}", flush=True)

    def close(name, callback):
        try:
            callback()
        except Exception as exc:
            errors.append(f"CLEANUP {name}: {reason(exc)}")

    with ExitStack() as stack:
        try:
            yield stage, lambda name, callback: stack.callback(close, name, callback)
        except Exception as exc:
            errors.append(f"FAIL {current}: {reason(exc)}")
    if errors:
        raise Failed("\n".join(errors))


def remove_workspace(directory):
    # Antivirus and handles retiring after process exit can briefly prevent removal on Windows.
    for delay in (0.1, 0.2, 0.4, 0.8, 1.6, None):
        try:
            directory.cleanup()
            return
        except OSError as exc:
            if delay is None or getattr(exc, "winerror", None) not in {5, 32, 33, 145, 267}:
                raise
            time.sleep(delay)


def stop_server(proc):
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        # A venv python.exe can launch a second interpreter. Signal only the group created here.
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=5)
            return
        except (OSError, subprocess.TimeoutExpired):
            if proc.poll() is not None:
                return
        # Noninteractive Windows runners may have no console to receive Ctrl+Break.
        taskkill = Path(os.environ["SYSTEMROOT"]) / "System32" / "taskkill.exe"
        try:
            result = subprocess.run(
                [str(taskkill), "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            require(result.returncode == 0 or proc.poll() is not None, "Owned server tree could not be stopped.")
        except (Failed, OSError, subprocess.TimeoutExpired):
            # Reap the owned handle even when the tree operation failed. Descendant exit is unconfirmed.
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            raise Failed("Owned server tree shutdown could not be confirmed.") from None
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def server(work, paid, key, token, defer):
    provider, model = ("deepseek", "deepseek-flash") if paid else ("openai", "gpt-5-mini")
    env = fixture_env(work)
    env.update(
        CIAREN_API_TOKEN=token,
        CIAREN_DATA_DIR=str(work / "data"),
        CIAREN_ASSISTANT_PROVIDER=provider,
        CIAREN_ASSISTANT_TURNS_PER_HOUR="4",
        OTEL_SDK_DISABLED="true",
        USERPROFILE=str(work),
        TEMP=str(work),
        TMP=str(work),
    )
    prefix = "CIAREN_ASSISTANT_" + provider.upper()
    env.update({prefix + "_MODEL": model, prefix + "_KEY_SOURCE": "env", prefix + "_API_KEY": key})
    if paid:
        env[prefix + "_EFFORT"] = "none"
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    args = (
        ["-m", "app.cli", "serve", "--host", "127.0.0.1", "--port", str(port)]
        if paid
        else [str(Path(__file__).with_name("fixture_server.py").resolve()), str(port)]
    )
    proc = subprocess.Popen(
        [sys.executable, *args],
        env=env,
        cwd=work,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    defer("server", lambda: stop_server(proc))
    local = build_opener(ProxyHandler({}))
    for _ in range(200):
        require(proc.poll() is None, "Isolated server exited during startup.")
        try:
            with local.open(base + "/ready", timeout=1):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise Failed("Isolated server did not become ready.")
    return base, provider, model


def walkthrough(context, base, provider, model, capture, stage):
    api = context.request

    def get(path):
        response = api.get(base + "/api" + path)
        require(response.ok, "Local API read failed.")
        return response.json()

    stage("configuration")
    status = get("/assistant/status")
    require(
        (status.get("provider"), status.get("model"), status.get("state"), status.get("source"))
        == (provider, model, "configured", "env"),
        "Configured adapter, model or credential source did not match.",
    )
    stage("synthetic fixtures")
    datasets = []
    for name in ("orders.csv", "catalog.csv"):
        upload = api.post(
            base + "/api/datasets/upload",
            multipart={
                "file": {
                    "name": name,
                    "mimeType": "text/csv",
                    "buffer": (ROOT / "examples/orders-audit" / name).read_bytes(),
                }
            },
        )
        require(upload.ok, "Synthetic CSV upload failed.")
        datasets.append(upload.json())
    created = api.post(base + "/api/flows", data={"name": "Fulfillment audit", "project_id": datasets[0]["project_id"]})
    require(created.ok, "Synthetic flow creation failed.")
    path = "/flows/" + created.json()["id"]
    activity = "/assistant" + path + "/activity"
    page = context.new_page()
    page.set_default_timeout(12000)
    page.goto(base + path)
    panel = page.get_by_role("dialog")
    open_panel = page.get_by_role("button", name="Assistant", exact=True)
    request = panel.get_by_label("Request", exact=True)
    apply = panel.get_by_role("button", name="Apply and save")

    def snapshot():
        return get(path), get(activity)["entries"], get("/runs"), get("/schedules")

    def turn(question, action):
        before = snapshot()
        request.fill(question)
        if question == REPAIR:
            capture(page, 1900)
        with page.expect_response(
            lambda r: r.url == base + "/api/assistant" + path + "/turn" and r.request.method == "POST", timeout=45000
        ) as reply:
            panel.get_by_role("button", name=action, exact=True).click()
        check_turn(reply.value, before, snapshot)
        return reply.value.json()

    def save_edit(**values):
        rev = get(path)["updated_at"]
        response = api.put(base + "/api" + path, data={"expected_revision": rev, **values})
        require(response.ok, "Manual fixture edit failed.")

    def join(graph):
        return next(n for n in graph["nodes"] if n["type"] == "join")

    open_panel.click()
    panel.get_by_label("Input dataset", exact=True).select_option(datasets[0]["id"])
    panel.get_by_label("Right input for Join").select_option(datasets[1]["id"])
    share = panel.get_by_label("Include column names in this request")
    if not share.is_visible():
        panel.get_by_text("Data shared with provider", exact=True).click()
    share.check()
    stage("build proposal")
    built = turn(BUILD, "Create proposal")
    require(
        built.get("proposal") and join({"nodes": built["delta"]["added"]})["data"]["config"]["how"] == "left",
        "Build did not return the requested left Join.",
    )
    proposed = built["delta"]["added"]
    kinds = sorted(n["type"] for n in proposed)
    require(
        kinds == sorted(["fileInput", "fileInput", "join", "conditionalColumn", "sortRows", "fileOutput"]),
        "Build did not produce the requested node set.",
    )
    order = next(n["data"]["config"] for n in proposed if n["type"] == "sortRows")
    flag = next(n["data"]["config"] for n in proposed if n["type"] == "conditionalColumn")
    rule = flag["rules"][0]
    require(
        order["columns"] == ["order_id"]
        and order["ascending"]
        and flag["new_column"] == "ready_to_fulfill"
        and rule["column"] == "catalog_status"
        and rule["value"] == "active",
        "Build settings differ from request.",
    )
    stage("save build")
    apply.click()
    expect(panel).to_have_count(0)
    open_panel.click()
    panel.get_by_role("button", name="Guides", exact=True).click()
    stage("cited guide")
    answer = turn(GUIDE, "Ask the guides")
    citation = answer.get("citation", {}).get("url", "")
    require(
        re.fullmatch(
            r"https://github\.com/ciaren-labs/Ciaren/blob/[0-9a-f]{40}/docs/transformations/join\.md#L\d+(-L\d+)?",
            citation,
        )
        is not None,
        "Guide did not cite the pinned Join page.",
    )
    expect(panel.locator("a").filter(has_text=answer["citation"]["title"]).first).to_be_visible()
    print("PASS build and cited Join guide", flush=True)
    stage("prepare missing-order case")
    graph = get(path)["graph_json"]
    join(graph)["data"]["config"]["how"] = "inner"
    save_edit(graph_json=graph)
    page.reload()
    open_panel.click()
    panel.get_by_role("button", name="Diagnose", exact=True).click()
    stage("unsupported request")
    refusal = turn(UNSUPPORTED, "Diagnose flow")
    require(
        "proposal" not in refusal and bool(refusal.get("message")), "Unsupported scheduling request was not declined."
    )
    stage("repair proposal")
    repair = turn(REPAIR, "Diagnose flow")
    expected = deepcopy(graph)
    join(expected)["data"]["config"]["how"] = "left"
    require(
        repair.get("proposal")
        and repair["delta"] == {"added": [], "connected": [], "disconnected": [], "changed": [join(expected)]},
        "Repair changed the wrong scope.",
    )
    expect(page.locator(".assistant-review-node")).to_have_count(1)
    apply.hover()
    stage("review and save repair")
    capture(page, 3000)
    apply.click()
    expect(panel).to_have_count(0)
    require(get(path)["graph_json"] == expected, "Confirmed repair differs from preview.")
    page.reload()
    join_node = page.locator(f'.react-flow__node[data-id="{join(expected)["id"]}"]')
    join_node.click()
    expect(page.locator("select").filter(has=page.locator('option[value="inner"]')).first).to_have_value("left")
    capture(page, 1700)
    stage("local tools")
    open_panel.click()
    panel.get_by_role("button", name="Explain selected node").click()
    expect(panel.get_by_role("link", name="Ciaren node guide")).to_be_visible()
    panel.get_by_role("button", name="Check canvas").click()
    expect(panel.get_by_text("Canvas checks passed.", exact=False)).to_be_visible()

    def show_activity():
        panel.get_by_role("tab", name="Activity").click()

    stage("activity and reversal preview")
    show_activity()
    entry = panel.get_by_role("listitem").filter(has=page.get_by_role("heading", name="Saved repair"))
    entry.locator("summary").click()
    expect(entry.get_by_text("inner → left")).to_be_visible()
    capture(page, 2200)
    entry.get_by_role("button", name="Preview reversal").click()
    confirm = panel.get_by_role("button", name="Confirm reversal")
    expect(confirm).to_be_visible()
    # A manual save after preview must survive a stale confirmation.
    stage("stale reversal")
    independent = deepcopy(expected)
    sort = next(n for n in independent["nodes"] if n["type"] == "sortRows")
    sort["data"]["config"]["ascending"] = False
    save_edit(graph_json=independent)
    before = snapshot()
    with page.expect_response(lambda r: r.url.endswith("/revert")) as conflict:
        confirm.click()
    require(conflict.value.status == 409 and snapshot() == before, "Stale reversal overwrote a concurrent edit.")
    stage("selective reversal")
    page.reload()
    open_panel.click()
    show_activity()
    entry.get_by_role("button", name="Preview reversal").click()
    expect(panel.get_by_text("left → inner")).to_be_visible()
    confirm.hover()
    capture(page, 2100)
    confirm.click()
    expect(panel.get_by_text("Reversal saved to activity.")).to_be_visible()
    last = panel.get_by_role("listitem").filter(has=page.get_by_role("heading", name="Reverted change"))
    last.locator("summary").click()
    capture(page, 2200)
    stage("activity privacy")
    flow, entries, runs, schedules = snapshot()
    join(independent)["data"]["config"]["how"] = "inner"
    require(flow["graph_json"] == independent, "Reversal lost the independent manual edit.")
    require(
        not runs
        and not schedules
        and [e["source"] for e in entries] == ["revert", "diagnose", "build"]
        and entries[0]["reverses"] == entries[1]["id"],
        "Unexpected run, schedule or history.",
    )
    audit = json.dumps(entries)
    require(
        all(
            value not in audit
            for value in (BUILD, GUIDE, UNSUPPORTED, REPAIR, "MISSING", "SLEEVE", "orders.csv", "ready_to_fulfill")
        ),
        "Activity included a prompt, row, filename or private field.",
    )
    print("PASS unsupported request, repair, local tools, stale preview, selective reversal and redacted activity")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--paid-deepseek",
        action="store_true",
        help="Use a direct DeepSeek API key and at most four turns",
    )
    modes.add_argument(
        "--demo-gif",
        type=Path,
        metavar="FILE",
        help="Record the packaged UI with simulated inference",
    )
    modes.add_argument(
        "--build-gif",
        type=Path,
        metavar="FILE",
        help="Record the first CSV tutorial with simulated inference",
    )
    args = parser.parse_args()
    import app

    require(
        Path(app.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()),
        "Install the Ciaren wheel in a dedicated venv.",
    )
    # Remove the paid key from the parent environment before starting Playwright or Chromium.
    key = os.environ.pop(DIRECT_KEY, None) if args.paid_deepseek else KEY
    require(key, "Direct DeepSeek credential missing from the process environment.")
    # Browser processes need OS paths, not provider credentials, proxy settings or debugging hooks.
    browser_env = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "SYSTEMDRIVE",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "TMP",
        "TEMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR",
        "PLAYWRIGHT_BROWSERS_PATH",
        "CIAREN_TEST_CHROMIUM",
    }
    for name in tuple(os.environ):
        if name.upper() not in browser_env:
            del os.environ[name]
    frames, durations = [], []

    def capture(page, duration, caption=None, target=None, left=0):
        if args.demo_gif or args.build_gif:
            from PIL import Image

            if caption:
                from build_recording import captioned_frame

                frame = captioned_frame(page, caption, target, left)
            else:
                png = page.screenshot(
                    clip={"x": 236, "y": 6, "width": 1040, "height": 814},
                    animations="disabled",
                )
                frame = Image.open(io.BytesIO(png)).convert("RGB")
            frames.append(frame.quantize(colors=192))
            durations.append(duration)

    token = secrets.token_urlsafe(32)
    with managed_run() as (stage, defer):
        directory = tempfile.TemporaryDirectory(prefix="ciaren-walkthrough-")
        defer("temporary workspace", lambda: remove_workspace(directory))
        stage("server startup")
        base, provider, model = server(Path(directory.name), args.paid_deepseek, key, token, defer)
        stage("Playwright startup")
        pw = sync_playwright().start()
        defer("Playwright", pw.stop)
        print(
            f"{'PAID' if args.paid_deepseek else 'SIMULATED'} {provider} / {model}",
            flush=True,
        )
        stage("browser startup")
        browser = pw.chromium.launch(executable_path=os.environ.get("CIAREN_TEST_CHROMIUM"))
        defer("browser", browser.close)
        context = browser.new_context(
            viewport={"width": 1280, "height": 840},
            reduced_motion="reduce",
            extra_http_headers={"Authorization": "Bearer " + token},
            service_workers="block",
        )
        defer("browser context", context.close)
        context.route(
            "**/*",
            lambda r: r.continue_() if r.request.url.startswith(base + "/") else r.abort(),
        )
        if args.build_gif:
            from build_recording import record_build

            record_build(context, base, capture, stage)
        else:
            walkthrough(context, base, provider, model, capture, stage)
        if args.demo_gif or args.build_gif:
            stage("save recording")
            frames[0].save(
                args.demo_gif or args.build_gif,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                optimize=True,
                disposal=1,
            )


if __name__ == "__main__":
    try:
        main()
    except Failed as exc:
        raise SystemExit(str(exc)) from None
    except Exception as exc:
        # Browser/driver exceptions can contain response fragments and local paths.
        raise SystemExit(f"Walkthrough failed ({type(exc).__name__}). No request or response was logged.") from None
