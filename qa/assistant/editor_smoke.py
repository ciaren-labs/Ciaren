"""Run against a freshly built frontend with Playwright and the backend dev venv.

python qa/assistant/editor_smoke.py --screenshots /tmp/ciaren-assistant-shots
"""

import argparse
import csv
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError

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


def check_contrast(locator):
    """Compute rendered text/background contrast for a solid action or tab."""
    ratio = locator.evaluate("""el => {
      const ctx=document.createElement("canvas").getContext("2d");
      function color(css) {
        ctx.clearRect(0,0,1,1); ctx.fillStyle=css; ctx.fillRect(0,0,1,1);
        return Array.from(ctx.getImageData(0,0,1,1).data);
      }
      function luminance(rgb) {
        const c=rgb.slice(0,3).map(n=>n/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);
        return c[0]*0.2126+c[1]*0.7152+c[2]*0.0722;
      }
      const ink=luminance(color(getComputedStyle(el).color));
      const layers=[];
      for (let node=el;node;node=node.parentElement) {
        const rgba=color(getComputedStyle(node).backgroundColor);
        layers.push(rgba);
        if(rgba[3]===255) {
          const rgb=layers.reverse().reduce((base,layer)=>
            base.map((v,i)=>layer[i]*(layer[3]/255)+v*(1-layer[3]/255)),[255,255,255]);
          const bg=luminance(rgb);
          return (Math.max(ink,bg)+0.05)/(Math.min(ink,bg)+0.05);
        }
      }
      throw Error("No opaque background");
    }""")
    assert ratio >= 4.5, ratio
    return round(ratio, 2)


DEFAULT_PYTHON = ROOT / "backend/.venv/bin/python"


def assert_private_audit(audit):
    assert all(
        value not in audit for value in (KEY, "Conserva todos", "Local annotation", "ready_to_fulfill", "catalog.csv")
    )


def run(base, shots, work, *, python=DEFAULT_PYTHON, legacy=None):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("CIAREN_TEST_CHROMIUM"))
        context = browser.new_context(viewport={"width": 1280, "height": 840})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        api = page.request

        def get(path):
            res = api.get(base + "/api" + path)
            assert res.ok, res.status
            return res.json()

        if legacy:
            flow = get("/flows/" + legacy["flow"])
            assert flow["graph_json"] == legacy["graph"]
            page.goto(base + "/flows/" + legacy["flow"])
            with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/runs")) as admitted:
                page.get_by_role("button", name="Run", exact=True).click()
            result = admitted.value.json()
            assert result["status"] == "success"
            page.wait_for_url(base + "/runs/" + result["id"])
            page.locator('.react-flow__node[data-id="legacy-output"]').click()
            with page.expect_download() as download:
                page.get_by_role("button", name="Download output").click()
            check_csv(download.value.path(), [{"amount": "17"}])
            print("Pre-migration flow kept its graph and produced its original CSV from the editor.")

        page.emulate_media(reduced_motion="reduce")
        empty = api.post(base + "/api/flows", data={"name": "New flow"}).json()
        page.goto(base + "/flows/" + empty["id"])
        button = page.get_by_role("button", name="Assistant", exact=True)
        button.click()
        dialog = page.get_by_role("dialog")
        expect(dialog.get_by_role("link", name="Open settings")).to_be_visible()
        dialog.get_by_role("button", name="Check canvas").click()
        expect(dialog.get_by_text("The flow is empty.", exact=False)).to_be_visible()
        page.screenshot(path=shots / "empty.png")
        conversation = dialog.get_by_role("tab", name="Conversation")
        activity = dialog.get_by_role("tab", name="Activity")
        conversation.focus()
        page.keyboard.press("ArrowRight")
        expect(activity).to_be_focused()
        expect(dialog.get_by_text("No saved changes yet")).to_be_visible()
        assert "tablist" in dialog.aria_snapshot()
        print("Light active tab contrast:", check_contrast(activity))
        page.keyboard.press("Escape")
        expect(button).to_be_focused()

        page.get_by_role("button", name="Switch to dark mode").click()
        button.click()
        expect(dialog.get_by_role("link", name="Open settings")).to_be_visible()
        print(
            "Dark settings action contrast:",
            check_contrast(dialog.get_by_role("link", name="Open settings")),
        )
        assert page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches')
        page.screenshot(path=shots / "empty-dark.png")
        dialog.get_by_role("link", name="Open settings").click()
        page.wait_for_url(base + "/settings#assistant")
        page.get_by_role("button", name="Switch to light mode").click()
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
        send = page.get_by_role(
            "button",
            name=re.compile("^(Create proposal|Diagnose flow|Ask the guides)$"),
        )
        apply = page.get_by_role("button", name="Apply and save")
        page.get_by_label("Input dataset").select_option(ds["id"])
        request.fill("Keep ten rows and remove duplicates")
        send.click()
        expect(page.get_by_text("Proposed changes")).to_be_visible()
        assert not get(path)["graph_json"].get("nodes")
        assert not get("/assistant" + path + "/activity")["entries"]
        print("Light save action contrast:", check_contrast(apply))
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
        button.click()
        activity.click()
        expect(dialog.get_by_text("Save or discard your pending", exact=False)).to_be_visible()
        expect(dialog.get_by_role("button", name="Preview reversal")).to_be_disabled()
        page.keyboard.press("Escape")
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
        page.get_by_role("button", name="Guides", exact=True).click()
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
        assert 'dialog "Flow assistant"' in tree and 'textbox "Request"' in tree and "link" in tree
        page.screenshot(path=shots / "assistant-mobile.png")
        page.keyboard.press("Escape")
        expect(dialog).to_have_count(0)
        expect(button).to_be_focused()
        page.set_viewport_size({"width": 1280, "height": 840})

        def run_and_check_download(engine, expected_rows, evidence=None):
            saved = get(path)
            output = next(n["id"] for n in saved["graph_json"]["nodes"] if n["type"] == "fileOutput")
            page.get_by_title("Execution engine").select_option(engine)
            with page.expect_response(
                lambda r: r.url == base + "/api" + path + "/runs" and r.request.method == "POST"
            ) as execution:
                page.get_by_role("button", name="Run", exact=True).click()
            result = execution.value.json()
            assert result["status"] == "success" and result["engine"] == engine, result["status"]
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
        page.get_by_role("button", name="Diagnose", exact=True).click()
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
        page.get_by_role("button", name="Build", exact=True).click()
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
        if not page.get_by_label("Include column names in this request").is_visible():
            page.get_by_text("Data shared with provider", exact=True).click()
        page.get_by_label("Include column names in this request").check()
        request.fill(
            "Conserva todos los pedidos, une el catálogo por SKU, marca ready_to_fulfill si el estado es active, "
            "ordena por order_id y escribe un CSV."
        )
        send.click()
        expect(apply).to_be_visible()
        dialog.locator("summary").filter(has_text="Connections (").click()
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
        if not page.get_by_label("Include column names in this request").is_visible():
            page.get_by_text("Data shared with provider", exact=True).click()
        page.get_by_label("Include column names in this request").check()
        send.click()
        expect(apply).to_be_visible()
        expect(dialog.get_by_text("catalog.csv · version 2", exact=True)).to_be_visible()
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

        def check_exports(stage, rows):
            exports = api.post(base + "/api" + path + "/export/python")
            assert exports.ok and all(exports.json().get(k) for k in ("code", "polars"))
            portable = exports.json()["flow_document"]
            assert "activity" not in portable and KEY not in exports.text()
            # The exports run outside the server with only the fixture CSVs and the installed engine.
            output_name = next(
                n["data"]["config"]["dataset_name"]
                for n in get(path)["graph_json"]["nodes"]
                if n["type"] == "fileOutput"
            )
            for field in ("code", "polars", "polars_lazy"):
                standalone = work / f"{stage}-{field}"
                standalone.mkdir()
                for filename in ("orders.csv", "catalog.csv"):
                    shutil.copyfile(example / filename, standalone / filename)
                script = standalone / "audit.py"
                script.write_text(exports.json()[field], encoding="utf-8")
                subprocess.run(
                    [str(python), "-I", str(script)],
                    cwd=standalone,
                    env={k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "SYSTEMROOT", "TMPDIR"}},
                    check=True,
                    timeout=45,
                )
                check_csv(standalone / f"{output_name}.csv", rows)

        check_exports("created", expected)
        # Seed a semantically wrong join; its successful inner run loses order 104.
        wrong = get(path)["graph_json"]
        next(n for n in wrong["nodes"] if n["type"] == "join")["data"]["config"]["how"] = "inner"
        assert api.put(base + "/api" + path, data={"graph_json": wrong}).ok
        page.reload()
        run_and_check_download("pandas", [r for r in expected if r["order_id"] != "104"], "join-inner")
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
        next(n for n in after["nodes"] if n["type"] == "join")["data"]["config"]["how"] = "left"
        button.click()
        page.get_by_role("button", name="Diagnose", exact=True).click()
        request.fill("El pedido 104 desaparece. Conserva todos los pedidos de la izquierda sin cambiar nada más.")
        send.click()
        expect(apply).to_be_visible()
        assert before == get(path)["graph_json"]
        expect(dialog.get_by_text("Update Join / Merge", exact=True)).to_be_visible()
        expect(page.locator(".assistant-review-node")).to_have_count(1)
        page.screenshot(path=shots / "join-repair.png")
        dialog.get_by_role("button", name="Inspect on canvas").click()
        join_node = page.locator(
            '.react-flow__node[data-id="' + next(n["id"] for n in before["nodes"] if n["type"] == "join") + '"]'
        )
        expect(join_node).to_be_focused()
        expect(page.locator(".assistant-review-node")).to_have_count(0)
        button.click()
        dialog.get_by_role("button", name="Diagnose", exact=True).click()
        request.fill("Conserva los pedidos que no tienen coincidencia.")
        send.click()
        expect(apply).to_be_visible()
        apply.click()
        expect(dialog).to_have_count(0)
        assert get(path)["graph_json"] == after
        for engine in ("pandas", "polars"):
            run_and_check_download(engine, expected, "join-repaired")
        join_id = next(n["id"] for n in after["nodes"] if n["type"] == "join")
        sort_id = next(n["id"] for n in after["nodes"] if n["type"] == "sortRows")

        def open_node_select(tab, node_id, option):
            tab.locator(f'.react-flow__node[data-id="{node_id}"]').click()
            return tab.locator("select").filter(has=tab.locator(f'option[value="{option}"]')).first

        def save_in_editor(tab):
            with tab.expect_response(lambda r: r.request.method == "PUT" and r.url == base + "/api" + path) as response:
                tab.get_by_role("button", name="Save", exact=True).click()
            assert response.value.ok, response.value.text()

        stale_tabs = []
        for action in ("Save", "Run"):
            stale = page.context.new_page()
            stale.goto(base + path)
            draft = open_node_select(stale, join_id, "inner")
            draft.select_option("inner")
            stale_tabs.append((action, stale, draft))
        page.get_by_title("Execution engine").select_option(after["engine"])
        open_node_select(page, sort_id, "false").select_option("false")
        save_in_editor(page)
        saved = get(path)["graph_json"]
        assert next(n for n in saved["nodes"] if n["id"] == sort_id)["data"]["config"]["ascending"] is False
        assert next(n for n in saved["nodes"] if n["id"] == join_id)["data"]["config"]["how"] == "left"
        baseline_runs = len(get("/runs"))
        for action, stale, draft in stale_tabs:
            with stale.expect_response(
                lambda r: r.request.method == "PUT" and r.url == base + "/api" + path
            ) as response:
                stale.get_by_role("button", name=action, exact=True).click()
            assert response.value.status == 409
            expect(stale.get_by_text("Your canvas is still open.", exact=False)).to_be_visible()
            expect(stale.get_by_role("link", name="Compare saved flow in a new tab")).to_be_visible()
            expect(draft).to_have_value("inner")
            assert get(path)["graph_json"] == saved and len(get("/runs")) == baseline_runs
            stale.screenshot(path=shots / ("stale-" + action.lower() + ".png"))
            stale.close()
        print(
            "Two stale drafts, one using Save and one using Run: 409 each; local Join edits preserved, database "
            "unchanged, zero runs."
        )

        page.reload()
        page.locator(f'.react-flow__node[data-id="{join_id}"]').click()
        button.click()
        dialog.get_by_role("button", name="Explain selected node").click()
        guide = dialog.get_by_role("link", name="Ciaren node guide")
        expect(guide).to_be_visible()
        assert "/blob/" in guide.get_attribute("href")
        dialog.get_by_role("button", name="Check canvas").click()
        expect(dialog.get_by_text("Canvas checks passed.", exact=False)).to_be_visible()
        activity.click()
        repair = dialog.get_by_role("listitem").filter(has=page.get_by_role("heading", name="Saved repair"))
        repair.locator("summary").click()
        expect(repair.get_by_text("inner → left")).to_be_visible()
        page.screenshot(path=shots / "history-desktop.png")
        page.set_viewport_size({"width": 390, "height": 844})
        expect(repair.get_by_role("button", name="Preview reversal")).to_be_in_viewport()
        page.screenshot(path=shots / "history-mobile.png")
        page.set_viewport_size({"width": 1280, "height": 840})
        runs = len(get("/runs"))
        repair.get_by_role("button", name="Preview reversal").click()
        expect(dialog.get_by_role("heading", name="Review reversal")).to_be_focused()
        expect(dialog.get_by_text("left → inner")).to_be_visible()
        page.screenshot(path=shots / "reversal-preview.png")
        dialog.get_by_role("button", name="Cancel reversal").click()
        assert get(path)["graph_json"] == saved and len(get("/assistant" + path + "/activity")["entries"]) == 2
        repair.get_by_role("button", name="Preview reversal").click()
        confirm = dialog.get_by_role("button", name="Confirm reversal")
        expect(confirm).to_be_visible()
        assert api.put(base + "/api" + path, data={"name": "Fulfillment audit · reviewed"}).ok
        confirm.click()
        expect(dialog.get_by_role("alert")).to_contain_text("changed")
        page.screenshot(path=shots / "reversal-conflict.png")
        assert get(path)["graph_json"] == saved
        page.reload()
        button.click()
        activity.click()
        repair.get_by_role("button", name="Preview reversal").click()
        confirm.click()
        expect(dialog.get_by_text("Reversal saved to activity.")).to_be_visible()
        assert len(get("/runs")) == runs
        saved_join = next(n for n in saved["nodes"] if n["type"] == "join")
        saved_join["data"]["config"]["how"] = "inner"
        assert get(path)["graph_json"] == saved
        page.reload()
        button.click()
        activity.click()
        expect(repair.get_by_text("Already reverted")).to_be_visible()
        reversed_card = dialog.get_by_role("listitem").filter(has=page.get_by_role("heading", name="Reverted change"))
        reversed_card.locator("summary").click()
        expect(reversed_card.get_by_text("left → inner")).to_be_visible()
        page.screenshot(path=shots / "reverted.png")
        rows = get("/assistant" + path + "/activity")["entries"]
        assert [x["source"] for x in rows] == ["revert", "diagnose", "build"]
        assert rows[0]["reverses"] == rows[1]["id"]
        check_exports("reverted", [r for r in reversed(expected) if r["order_id"] != "104"])
        page.keyboard.press("Escape")
        run_and_check_download(
            "pandas",
            [r for r in reversed(expected) if r["order_id"] != "104"],
            "join-reverted",
        )
        # A fresh repair followed by a manual edit to that very field must conflict,
        # including when the reversal uses a newly loaded revision.
        button.click()
        dialog.get_by_role("button", name="Diagnose", exact=True).click()
        request.fill("Conserva los pedidos sin coincidencia.")
        send.click()
        expect(apply).to_be_visible()
        apply.click()
        expect(dialog).to_have_count(0)
        open_node_select(page, join_id, "inner").select_option("inner")
        save_in_editor(page)
        same_field = get(path)["graph_json"]
        button.click()
        activity.click()
        dialog.get_by_role("button", name="Preview reversal").first.click()
        expect(dialog.get_by_role("alert")).to_contain_text("since changed")
        assert get(path)["graph_json"] == same_field
        page.screenshot(path=shots / "same-setting-conflict.png")
        page.keyboard.press("Escape")
        # A second tab commits after the first tab's pre-run save and before its
        # run request arrives. The server must reject the stale execution snapshot.
        gate = {}
        run_url = base + "/api" + path + "/runs"

        def gate_creation(route):
            gate["route"] = route

        runs_before = len(get("/runs"))
        page.route(run_url, gate_creation)
        page.get_by_role("button", name="Run", exact=True).click()
        for _ in range(100):
            if gate:
                break
            page.wait_for_timeout(50)
        assert "route" in gate
        winner = context.new_page()
        winner.goto(base + path)
        open_node_select(winner, sort_id, "true").select_option("true")
        save_in_editor(winner)
        with page.expect_response(lambda r: r.url == run_url and r.request.method == "POST") as blocked:
            gate["route"].continue_()
        assert blocked.value.status == 409 and len(get("/runs")) == runs_before
        expect(page.get_by_role("link", name="Compare saved flow in a new tab")).to_be_visible()
        same_field = get(path)["graph_json"]
        assert next(n for n in same_field["nodes"] if n["id"] == sort_id)["data"]["config"]["ascending"] is True
        winner.close()
        page.unroute(run_url, gate_creation)
        page.reload()
        print(
            "A second tab saved between pre-run save and execution admission. Stale POST /runs returned 409 "
            "without creating a run."
        )
        # While a real compute thread is paused, a second tab can still commit.
        (work / "hold-compute").touch()
        page.get_by_role("button", name="Run", exact=True).click()
        for _ in range(200):
            if (work / "computing").exists():
                break
            page.wait_for_timeout(50)
        assert (work / "computing").exists()
        live_draft = open_node_select(page, join_id, "left")
        live_draft.select_option("left")
        winner = context.new_page()
        winner.goto(base + path)
        open_node_select(winner, sort_id, "false").select_option("false")
        save_in_editor(winner)
        winner.close()
        (work / "release-compute").touch()
        result_link = page.get_by_role("link", name="View run in a new tab")
        expect(result_link).to_be_visible()
        run_id = result_link.get_attribute("href").split("/")[-1]
        finished = get("/runs/" + run_id)
        assert finished["status"] == "success"
        snapshot = finished["graph_snapshot"]
        assert next(n for n in snapshot["nodes"] if n["id"] == sort_id)["data"]["config"]["ascending"] is True
        expect(live_draft).to_have_value("left")
        current = get(path)["graph_json"]
        assert next(n for n in current["nodes"] if n["id"] == sort_id)["data"]["config"]["ascending"] is False
        assert next(n for n in current["nodes"] if n["id"] == join_id)["data"]["config"]["how"] == "inner"
        print(
            "While a real run was computing a second tab saved; only the admitted snapshot ran. The first "
            "retained its newer unsaved Join edit and linked to the result."
        )
        print(
            "Activity survived reload. Confirmed reversal preserved manual sort, recorded one event, and made "
            "zero runs. Keyboard, dirty canvas, cancellation, stale preview and local node help passed."
        )
        # Independent HTTP connections compete for the same database revision.
        race = api.post(base + "/api/flows", data={"name": "Race", "project_id": ds["project_id"]}).json()
        url = "/assistant/flows/" + race["id"]
        body = dict(
            mode="build",
            provider="openai",
            question="Bound rows",
            revision=race["updated_at"],
            graph={"nodes": [], "edges": [], "engine": "pandas"},
            dataset_id=ds["id"],
        )
        plans = [api.post(base + "/api" + url + "/turn", data=body).json() for _ in range(2)]

        def compete(method, endpoint, payloads):
            gate = threading.Barrier(2)

            def write(payload):
                req = urllib.request.Request(
                    base + "/api" + endpoint,
                    method=method,
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )
                gate.wait(timeout=10)
                try:
                    with urllib.request.urlopen(req, timeout=15) as response:
                        return response.status, json.load(response)
                except HTTPError as error:
                    return error.code, {}

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(write, payloads))
            statuses = [r[0] for r in results]
            assert sorted(statuses) == [200, 409], statuses
            winner = statuses.index(200)
            return winner, results[winner][1]

        winner, commit = compete("POST", url + "/apply", [{"proposal": p["proposal"]} for p in plans])
        race_path = "/flows/" + race["id"]
        stored = get(race_path)
        assert stored["updated_at"] == commit["revision"]
        assert stored["graph_json"]["nodes"] == plans[winner]["delta"]["added"]
        assert stored["graph_json"]["edges"] == plans[winner]["delta"]["connected"]
        (entry,) = get(url + "/activity")["entries"]
        endpoint = url + "/activity/" + entry["id"]
        rev = {"revision": stored["updated_at"]}
        previews = [api.post(base + "/api" + endpoint + "/preview", data=rev).json()["confirmation"] for _ in range(2)]
        _, undo = compete("POST", endpoint + "/revert", [{"proposal": p} for p in previews])
        reverted, original = get(url + "/activity")["entries"]
        restored = get(race_path)["graph_json"]
        assert restored["nodes"] == [] and restored["edges"] == []
        assert reverted["id"] == undo["activity"] and reverted["reverses"] == original["id"] == entry["id"]
        changes = [
            {"expected_revision": undo["revision"], "graph_json": {"nodes": [], "edges": [], "engine": engine}}
            for engine in ("pandas", "polars")
        ]
        winner, latest = compete("PUT", race_path, changes)
        assert get(race_path)["graph_json"] == latest["graph_json"] == changes[winner]["graph_json"]
        assert [e["id"] for e in get(url + "/activity")["entries"]] == [reverted["id"], entry["id"]]
        print(
            "Racing two ordinary saves, two applies and two reversals: HTTP 200/409 each time; persisted graph "
            "and audit matched the winners."
        )
        print(
            "orders-audit CSV matched all six columns and five rows on both engines; all three standalone exports "
            "matched before and after reversal; inner lost 104; repair changed only how."
        )
        assert KEY not in repr(page.evaluate("() => [Object.entries(localStorage), Object.entries(sessionStorage)]"))
        assert not errors, errors
        browser.close()
        return race["id"], entry["id"], reverted["id"], latest["graph_json"]


@contextmanager
def serve(work, env, python):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [str(python), str(Path(__file__).with_name("fixture_server.py").resolve()), str(port)], cwd=work, env=env
    )
    try:
        for _ in range(200):
            if proc.poll() is not None:
                raise RuntimeError("fixture server stopped")
            try:
                with urllib.request.urlopen(base + "/ready", timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise TimeoutError("Ciaren did not become ready")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def fixture_env(work):
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "SYSTEMROOT", "TMPDIR"}}
    env.update(HOME=str(work), CIAREN_SEED_DEMO="false", CIAREN_SCHEDULER_ENABLED="false", CIAREN_ML_ENABLED="false")
    return env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", required=True, type=Path)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        env = fixture_env(work)
        env["CIAREN_FRONTEND_DIST"] = str(ROOT / "frontend/dist")
        with serve(work, env, DEFAULT_PYTHON) as base:
            run(base, args.screenshots.resolve(), work)
        with sqlite3.connect(work / "ciaren.db") as conn:
            assert_private_audit(repr(conn.execute("select details,inverse from assistant_activity").fetchall()))
        assert KEY not in (work / "ciaren.db").read_bytes().decode("latin1")
    print("Desktop and mobile editor smoke passed (mock provider and keychain).")


if __name__ == "__main__":
    main()
