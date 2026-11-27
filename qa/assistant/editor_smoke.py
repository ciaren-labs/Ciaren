"""Run against a freshly built frontend with Playwright and the backend dev venv.

python qa/assistant/editor_smoke.py --screenshots /tmp/ciaren-assistant-shots
"""

import argparse
import csv
from copy import deepcopy
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
KEY = "synthetic-editor-key"


def check_csv(file, expected_rows):
    with file.open(encoding="utf-8-sig", newline="") as data:
        rows = list(csv.DictReader(data))
    assert list(rows[0]) == list(expected_rows[0])
    for row in rows:
        if "ready_to_fulfill" in row:
            row["ready_to_fulfill"] = row["ready_to_fulfill"].lower()
    assert rows == expected_rows, rows


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
                    "name": "cleanup.csv",
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

        def run_and_check_download(engine, expected_rows, evidence=None):
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
            check_csv(download.value.path(), expected_rows)
            if evidence:
                download.value.save_as(shots / f"{evidence}-{engine}.csv")
            logs = api.get(base + "/api/runs/" + result["id"] + "/logs/stream")
            assert logs.ok and KEY not in logs.text()
            page.goto(base + path)

        run_and_check_download("pandas", [{"amount": "4"}, {"amount": "3"}])

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
            run_and_check_download(engine, [{"amount": "3"}, {"amount": "4"}])
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
        # Build the repository example with built-ins. Use the project's real CSVs and expected output.
        example = ROOT / "examples/orders-audit"
        inputs = []
        for filename in ("orders.csv", "catalog.csv"):
            response = api.post(
                base + "/api/datasets/upload",
                params={"project_id": ds["project_id"]},
                multipart={
                    "file": {
                        "name": filename,
                        "mimeType": "text/csv",
                        "buffer": (example / filename).read_bytes(),
                    }
                },
            )
            assert response.ok, response.status
            inputs.append(response.json())
        flow = api.post(
            base + "/api/flows",
            data={"name": "Fulfillment audit", "project_id": ds["project_id"]},
        ).json()
        path = "/flows/" + flow["id"]
        page.goto(base + path)
        button.click()
        page.get_by_label("Input dataset", exact=True).select_option(inputs[0]["id"])
        page.get_by_label("Right input for Join").select_option(inputs[1]["id"])
        page.get_by_label("Include column names in this request").check()
        request.fill(
            "Conserva todos los pedidos, une el catálogo por SKU, marca ready_to_fulfill si el estado es active, ordena por order_id y escribe un CSV."
        )
        send.click()
        expect(apply).to_be_visible()
        expect(dialog.get_by_text("left input", exact=False).last).to_be_visible()
        expect(dialog.get_by_text("right input", exact=False).last).to_be_visible()
        assert not get(path)["graph_json"].get("nodes")
        # A newly uploaded right-hand version invalidates the preview, even on an unchanged canvas.
        changed = api.post(
            base + "/api/datasets/upload",
            params={"project_id": ds["project_id"]},
            multipart={
                "file": {
                    "name": "catalog.csv",
                    "mimeType": "text/csv",
                    "buffer": (example / "catalog.csv").read_bytes(),
                }
            },
        )
        assert changed.ok and changed.json()["latest_version"] == 2
        apply.click()
        expect(page.get_by_role("alert")).to_contain_text("changed")
        assert not get(path)["graph_json"].get("nodes")
        page.screenshot(path=shots / "join-stale.png")
        page.get_by_label("Include column names in this request").check()
        send.click()
        expect(apply).to_be_visible()
        expect(
            dialog.get_by_text("catalog.csv · version 2", exact=True)
        ).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        expect(apply).to_be_in_viewport()
        page.screenshot(path=shots / "join-mobile.png")
        page.set_viewport_size({"width": 1280, "height": 840})
        page.screenshot(path=shots / "join-create.png")
        apply.click()
        expect(dialog).to_have_count(0)
        with (example / "expected.csv").open(newline="") as f:
            expected = list(csv.DictReader(f))
        for row in expected:
            row["ready_to_fulfill"] = row["ready_to_fulfill"].lower()
        for engine in ("pandas", "polars"):
            run_and_check_download(engine, expected, "join-created")
        exports = api.post(base + "/api" + path + "/export/python")
        assert exports.ok and all(exports.json().get(k) for k in ("code", "polars"))
        # The exports run outside the server with only the fixture CSVs and the installed engine.
        output_name = next(
            n["data"]["config"]["dataset_name"]
            for n in get(path)["graph_json"]["nodes"]
            if n["type"] == "fileOutput"
        )
        for field in ("code", "polars", "polars_lazy"):
            standalone = work / field
            standalone.mkdir()
            for filename in ("orders.csv", "catalog.csv"):
                shutil.copyfile(example / filename, standalone / filename)
            script = standalone / "audit.py"
            script.write_text(exports.json()[field], encoding="utf-8")
            subprocess.run(
                [str(ROOT / "backend/.venv/bin/python"), "-I", str(script)],
                cwd=standalone,
                env={
                    k: v
                    for k, v in os.environ.items()
                    if k in {"PATH", "LANG", "SYSTEMROOT", "TMPDIR"}
                },
                check=True,
                timeout=45,
            )
            check_csv(standalone / f"{output_name}.csv", expected)
        # Seed a semantically wrong join; its successful inner run loses order 104.
        wrong = get(path)["graph_json"]
        next(n for n in wrong["nodes"] if n["type"] == "join")["data"]["config"][
            "how"
        ] = "inner"
        assert api.put(base + "/api" + path, data={"graph_json": wrong}).ok
        page.reload()
        run_and_check_download(
            "pandas", [r for r in expected if r["order_id"] != "104"], "join-inner"
        )
        before = get(path)["graph_json"]
        before["nodes"][0]["data"]["description"] = "Local annotation"
        before["parameters"] = []
        # The inspector writes the canonical conditions shape after a normal edit.
        flag = next(n for n in before["nodes"] if n["type"] == "conditionalColumn")
        rule = flag["data"]["config"]["rules"][0]
        flag["data"]["config"]["rules"] = [
            {
                "conditions": [{k: rule[k] for k in ("column", "operator", "value")}],
                "match": "all",
                "result": rule["result"],
            }
        ]
        assert api.put(base + "/api" + path, data={"graph_json": before}).ok
        page.reload()
        after = deepcopy(before)
        next(n for n in after["nodes"] if n["type"] == "join")["data"]["config"][
            "how"
        ] = "left"
        button.click()
        page.get_by_label("Task", exact=True).select_option("diagnose")
        request.fill(
            "El pedido 104 desaparece. Conserva todos los pedidos de la izquierda sin cambiar nada más."
        )
        send.click()
        expect(apply).to_be_visible()
        assert before == get(path)["graph_json"]
        expect(dialog.get_by_text("Update Join / Merge", exact=True)).to_be_visible()
        page.screenshot(path=shots / "join-repair.png")
        apply.click()
        expect(dialog).to_have_count(0)
        assert get(path)["graph_json"] == after
        for engine in ("pandas", "polars"):
            run_and_check_download(engine, expected, "join-repaired")
        print(
            "orders-audit CSV matched all six columns and five rows on both engines; three standalone exports matched; inner lost 104; repair changed only how."
        )
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
