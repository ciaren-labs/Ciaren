"""Run against a freshly built frontend with Playwright and the backend dev venv.

python qa/assistant/editor_smoke.py --screenshots /tmp/ciaren-assistant-shots
"""

import argparse
import csv
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
KEY = "synthetic-editor-key"


def run(base, shots, work):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CIAREN_TEST_CHROMIUM")
        )
        page = browser.new_page(viewport={"width": 1280, "height": 840})
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        api = page.request

        def get(path):
            res = api.get(base + "/api" + path)
            assert res.ok, res.status
            return res.json()

        page.goto(base + "/settings")
        provider = page.get_by_label("setting-ASSISTANT_PROVIDER")
        provider.select_option("openai")
        page.get_by_label("save-ASSISTANT_PROVIDER").click()
        page.get_by_label("New API key").fill(KEY)
        page.get_by_role("button", name="Save key").click()
        expect(page.get_by_text("openai · keyring · configured")).to_be_visible()
        expect(page.get_by_label("New API key")).to_have_value("")
        section = page.get_by_role("region", name="Assistant", exact=True)
        section.screenshot(path=shots / "settings.png")
        page.set_viewport_size({"width": 390, "height": 844})
        section.screenshot(path=shots / "settings-mobile.png")
        assert section.bounding_box()["width"] <= 390
        page.set_viewport_size({"width": 1280, "height": 840})
        upload = api.post(
            base + "/api/datasets/upload",
            multipart={
                "file": {
                    "name": "orders.csv",
                    "mimeType": "text/csv",
                    "buffer": b"amount\n4\n3\n3\n",
                }
            },
        )
        assert upload.ok, upload.text()
        ds = upload.json()
        flow = api.post(
            base + "/api/flows",
            data={"name": "Order cleanup", "project_id": ds["project_id"]},
        ).json()
        path = "/flows/" + flow["id"]
        page.goto(base + path)
        page.get_by_role("button", name="Rename flow").click()
        edit_dialog = page.get_by_role("dialog")
        edit_dialog.get_by_placeholder("My ETL flow").fill("Order quality check")
        edit_dialog.get_by_role("button", name="Save", exact=True).click()
        expect(edit_dialog).to_have_count(0)
        button = page.get_by_role("button", name="Assistant", exact=True)
        button.click()
        request = page.get_by_label("Request", exact=True)
        send = page.get_by_role("button", name="Send request")
        apply = page.get_by_role("button", name="Apply and save")
        page.get_by_label("Input dataset").select_option(ds["id"])
        request.fill("Keep ten rows and remove duplicates")
        send.click()
        expect(page.get_by_text("Proposed changes")).to_be_visible()
        assert not get(path)["graph_json"].get("nodes")
        page.screenshot(path=shots / "assistant-desktop.png")
        apply.click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        expect(page.locator(".react-flow__node")).to_have_count(4)
        export_button = page.get_by_role("button", name="Export", exact=True)
        expect(export_button).to_be_enabled()
        export_button.click()
        expect(page.get_by_role("tab", name="polars", exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("button", name="Run", exact=True)).to_be_enabled()
        page.keyboard.press("Control+z")
        expect(page.locator(".react-flow__node")).to_have_count(0)
        page.keyboard.press("Control+Shift+z")
        expect(page.locator(".react-flow__node")).to_have_count(4)

        button.click()
        request.fill("Limit rows")
        send.click()
        expect(apply).to_be_visible()
        apply.focus()
        page.keyboard.press("Control+z")
        apply.click()
        expect(page.get_by_role("alert")).to_contain_text("canvas changed")
        page.get_by_role("button", name="Close", exact=True).click()
        page.keyboard.press("Control+Shift+z")
        expect(page.locator(".react-flow__node")).to_have_count(4)
        button.click()
        page.get_by_label("Task", exact=True).select_option("docs")
        request.fill("¿Cómo conecto las dos entradas de Join?")
        send.click()
        cite = page.get_by_role("dialog").locator('a[href*="/blob/"]')
        expect(cite).to_be_visible()
        assert "/docs/transformations/join.md#L" in cite.get_attribute("href")
        expect(page.get_by_text("Combine two inputs", exact=False)).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        dialog = page.get_by_role("dialog")
        bounds = dialog.bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 391
        tree = dialog.aria_snapshot()
        assert (
            'dialog "Flow assistant"' in tree
            and 'textbox "Request"' in tree
            and "link" in tree
        )
        page.screenshot(path=shots / "assistant-mobile.png")
        page.keyboard.press("Escape")
        expect(dialog).to_have_count(0)
        expect(button).to_be_focused()
        page.set_viewport_size({"width": 1280, "height": 840})

        def run_and_check_download(engine, amounts):
            saved = get(path)
            output = next(
                n["id"]
                for n in saved["graph_json"]["nodes"]
                if n["type"] == "fileOutput"
            )
            page.get_by_title("Execution engine").select_option(engine)
            with page.expect_response(
                lambda r: (
                    r.url == base + "/api" + path + "/runs"
                    and r.request.method == "POST"
                )
            ) as execution:
                page.get_by_role("button", name="Run", exact=True).click()
            result = execution.value.json()
            assert result["status"] == "success" and result["engine"] == engine, result[
                "status"
            ]
            page.wait_for_url(base + "/runs/" + result["id"])
            page.locator(f'.react-flow__node[data-id="{output}"]').click()
            with page.expect_download() as download:
                page.get_by_role("button", name="Download output").click()
            with download.value.path().open(encoding="utf-8-sig", newline="") as data:
                assert list(csv.DictReader(data)) == [
                    {"amount": str(n)} for n in amounts
                ]
            logs = api.get(base + "/api/runs/" + result["id"] + "/logs/stream")
            assert logs.ok and KEY not in logs.text()
            page.goto(base + path)

        run_and_check_download("pandas", [4, 3])

        # Exercise a real failed run and repair it from the canvas.
        graph = get(path)["graph_json"]
        node = graph["nodes"][1]
        node.update(
            type="sortRows",
            data={"label": "Sort Rows", "config": {"columns": ["missing_amount"]}},
        )
        assert api.put(base + "/api" + path, data={"graph_json": graph}).ok
        run = api.post(base + "/api" + path + "/runs", data={"engine": "pandas"})
        assert run.ok and run.json()["status"] == "failed", run.text()
        page.reload()
        button.click()
        page.get_by_label("Task", exact=True).select_option("diagnose")
        request.fill("Repair the failed sort")
        send.click()
        expect(page.get_by_text("Proposed changes")).to_be_visible()
        page.screenshot(path=shots / "diagnosis.png")
        apply.click()
        expect(dialog).to_have_count(0)
        for engine in ("pandas", "polars"):
            run_and_check_download(engine, [3, 4])
        exported = api.post(base + "/api" + path + "/export/python")
        assert exported.ok and KEY not in exported.text()

        button.click()
        page.get_by_label("Task", exact=True).select_option("build")
        request.fill("Wait for cancellation")
        send.click()
        for _ in range(100):
            if (work / "waiting").exists():
                break
            time.sleep(0.05)
        assert (work / "waiting").exists()
        page.get_by_role("button", name="Cancel request").click()
        expect(page.get_by_role("alert")).to_contain_text("cancelled")
        for _ in range(100):
            if (work / "cancelled").exists():
                break
            time.sleep(0.05)
        assert (work / "cancelled").exists(), "outbound provider task was not cancelled"
        request.fill("Keep ten rows")
        send.click()
        expect(apply).to_be_visible()
        assert api.put(base + "/api" + path, data={"name": "Concurrent save"}).ok
        apply.click()
        expect(page.get_by_role("alert")).to_contain_text("changed")
        assert get(path)["name"] == "Concurrent save"
        assert KEY not in repr(
            page.evaluate(
                "() => [Object.entries(localStorage), Object.entries(sessionStorage)]"
            )
        )
        assert KEY not in (work / "ciaren.db").read_bytes().decode("latin1")
        assert not errors, errors
        browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", required=True, type=Path)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp, socket.socket() as sock:
        work = Path(temp)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        base = f"http://127.0.0.1:{port}"
        env = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "LANG", "SYSTEMROOT", "TMPDIR"}
        }
        env.update(
            HOME=temp,
            CIAREN_SEED_DEMO="false",
            CIAREN_SCHEDULER_ENABLED="false",
            CIAREN_ML_ENABLED="false",
            CIAREN_FRONTEND_DIST=str(ROOT / "frontend/dist"),
        )
        proc = subprocess.Popen(
            [
                str(ROOT / "backend/.venv/bin/python"),
                str(Path(__file__).with_name("fixture_server.py").resolve()),
                str(port),
            ],
            cwd=temp,
            env=env,
        )
        try:
            for _ in range(160):
                if proc.poll() is not None:
                    raise RuntimeError("fixture server stopped")
                try:
                    with urllib.request.urlopen(base + "/ready", timeout=1):
                        break
                except OSError:
                    time.sleep(0.1)
            run(base, args.screenshots.resolve(), work)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    print("Desktop and mobile editor smoke passed (mock provider and keychain).")


if __name__ == "__main__":
    main()
