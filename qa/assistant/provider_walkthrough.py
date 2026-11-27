"""Exercise a packaged editor with synthetic CSVs. Paid DeepSeek needs explicit opt-in."""

import argparse
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from editor_smoke import KEY, ROOT, fixture_env
from playwright.sync_api import expect, sync_playwright

DIRECT_KEY = "CIAREN_ASSISTANT_DEEPSEEK_API_KEY"
BUILD = "Keep all orders by sku. Flag ready_to_fulfill when catalog_status equals active. Sort by order_id."
GUIDE = "How do I connect the two inputs of a Join?"
REPAIR = "Order 104 is missing. Keep every order, including orders without a catalog match."
UNSUPPORTED = "Schedule a nightly refresh. Leave the Join unchanged."


class Failed(Exception):
    """A fixed diagnostic suitable for printing; never embed request or exception contents."""


def require(condition, message):
    if not condition:
        raise Failed(message)


@contextmanager
def server(work, paid, key, token):
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
        [sys.executable, *args], env=env, cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
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
        yield base, provider, model
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def walkthrough(context, base, provider, model, capture):
    api = context.request

    def get(path):
        response = api.get(base + "/api" + path)
        require(response.ok, "Local API read failed.")
        return response.json()

    status = get("/assistant/status")
    require(
        (status.get("provider"), status.get("model"), status.get("state"), status.get("source"))
        == (provider, model, "configured", "env"),
        "Configured adapter, model or credential source did not match.",
    )
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
        require(reply.value.ok, f"{action}: request returned HTTP {reply.value.status}.")
        require(snapshot() == before, "A proposal changed server state before approval.")
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
    apply.click()
    expect(panel).to_have_count(0)
    open_panel.click()
    panel.get_by_role("button", name="Guides", exact=True).click()
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
    graph = get(path)["graph_json"]
    join(graph)["data"]["config"]["how"] = "inner"
    save_edit(graph_json=graph)
    page.reload()
    open_panel.click()
    panel.get_by_role("button", name="Diagnose", exact=True).click()
    refusal = turn(UNSUPPORTED, "Diagnose flow")
    require(
        "proposal" not in refusal and bool(refusal.get("message")), "Unsupported scheduling request was not declined."
    )
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
    capture(page, 3000)
    apply.click()
    expect(panel).to_have_count(0)
    require(get(path)["graph_json"] == expected, "Confirmed repair differs from preview.")
    page.reload()
    join_node = page.locator(f'.react-flow__node[data-id="{join(expected)["id"]}"]')
    join_node.click()
    expect(page.locator("select").filter(has=page.locator('option[value="inner"]')).first).to_have_value("left")
    capture(page, 1700)
    open_panel.click()
    panel.get_by_role("button", name="Explain selected node").click()
    expect(panel.get_by_role("link", name="Ciaren node guide")).to_be_visible()
    panel.get_by_role("button", name="Check canvas").click()
    expect(panel.get_by_text("Canvas checks passed.", exact=False)).to_be_visible()

    def show_activity():
        panel.get_by_role("tab", name="Activity").click()

    show_activity()
    entry = panel.get_by_role("listitem").filter(has=page.get_by_role("heading", name="Saved repair"))
    entry.locator("summary").click()
    expect(entry.get_by_text("inner → left")).to_be_visible()
    capture(page, 2200)
    entry.get_by_role("button", name="Preview reversal").click()
    confirm = panel.get_by_role("button", name="Confirm reversal")
    expect(confirm).to_be_visible()
    # A manual save after preview must survive a stale confirmation.
    independent = deepcopy(expected)
    sort = next(n for n in independent["nodes"] if n["type"] == "sortRows")
    sort["data"]["config"]["ascending"] = False
    save_edit(graph_json=independent)
    before = snapshot()
    with page.expect_response(lambda r: r.url.endswith("/revert")) as conflict:
        confirm.click()
    require(conflict.value.status == 409 and snapshot() == before, "Stale reversal overwrote a concurrent edit.")
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
        "--paid-deepseek", action="store_true", help="Use a direct DeepSeek API key and at most four turns"
    )
    modes.add_argument("--demo-gif", type=Path, metavar="FILE", help="Record the packaged UI with simulated inference")
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

    def capture(page, duration):
        if args.demo_gif:
            from PIL import Image

            png = page.screenshot(clip={"x": 236, "y": 6, "width": 1040, "height": 814}, animations="disabled")
            frames.append(Image.open(io.BytesIO(png)).convert("RGB").quantize(colors=192))
            durations.append(duration)

    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="ciaren-walkthrough-") as folder:
        with server(Path(folder), args.paid_deepseek, key, token) as (base, provider, model), sync_playwright() as pw:
            print(f"{'PAID' if args.paid_deepseek else 'SIMULATED'} {provider} / {model}", flush=True)
            browser = pw.chromium.launch(executable_path=os.environ.get("CIAREN_TEST_CHROMIUM"))
            context = browser.new_context(
                viewport={"width": 1280, "height": 840},
                reduced_motion="reduce",
                extra_http_headers={"Authorization": "Bearer " + token},
                service_workers="block",
            )
            context.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base + "/") else r.abort())
            walkthrough(context, base, provider, model, capture)
            context.close()
            browser.close()
    if args.demo_gif:
        frames[0].save(
            args.demo_gif,
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
