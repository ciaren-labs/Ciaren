"""Record the first CSV tutorial in the packaged editor with the simulated provider."""

import csv
import io
import re

from playwright.sync_api import expect


def captioned_frame(page, caption, target, left):
    """Keep controls at browser scale and mark the next action without covering its label."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1000, 780
    png = page.screenshot(
        clip={"x": left, "y": 0, "width": width, "height": height},
        animations="disabled",
    )
    frame = Image.new("RGB", (width, height + 50), "#211838")
    frame.paste(Image.open(io.BytesIO(png)).convert("RGB"))
    ink = ImageDraw.Draw(frame)
    if target is not None:
        box = target.bounding_box()
        x = round(box["x"] - left)
        y = round(box["y"])
        ink.rounded_rectangle(
            (x - 3, y - 3, x + round(box["width"]) + 3, y + round(box["height"]) + 3),
            radius=6,
            outline="#f59e0b",
            width=3,
        )
    ink.rectangle((0, height, 8, height + 50), fill="#b49bff")
    ink.text((24, height + 12), caption, fill="white", font=ImageFont.load_default(size=22))
    return frame


def record_build(context, base, capture, stage):
    page = context.new_page()
    page.set_viewport_size({"width": 1280, "height": 780})
    page.set_default_timeout(12000)
    button = page.get_by_role("button")
    stage("upload tutorial CSV and create blank flow")
    page.goto(base + "/datasets")
    page.locator('input[type="file"]').set_input_files(
        {
            "name": "amounts.csv",
            "mimeType": "text/csv",
            "buffer": b"amount\n4\n3\n3\n2\n",
        }
    )
    expect(page.get_by_text("Uploaded", exact=True)).to_be_visible()
    page.goto(base + "/flows")
    button.filter(has_text="New flow").first.click()
    panel = page.get_by_role("dialog")
    panel.get_by_placeholder("My ETL flow").fill("Amount cleanup")
    panel.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_url(re.compile(r"/flows/[^/]+$"))
    flow_url = page.url
    assistant = page.get_by_role("button", name="Assistant", exact=True)
    expect(assistant).to_be_visible()
    page.get_by_role("button", name="Collapse panel").click()
    assistant.focus()
    expect(page.get_by_role("button", name="Dismiss notification")).to_have_count(0, timeout=10000)
    capture(page, 1800, "Start with an empty canvas and open Assistant.", assistant)
    assistant.click()
    panel.get_by_label("Input dataset", exact=True).select_option(label="amounts.csv")
    capture(
        page,
        1600,
        "Choose amounts.csv from this project.",
        panel.get_by_label("Input dataset", exact=True),
        280,
    )
    stage("generate and review four connected nodes")
    prompt = panel.get_by_label("Request", exact=True)
    for part, duration in (
        ("Keep ten rows", 400),
        (" and remove", 400),
        (" duplicates", 1550),
    ):
        prompt.press_sequentially(part)
        capture(page, duration, "Describe the cleanup in one request.", left=280)
    submit = panel.get_by_role("button", name="Create proposal")
    submit.focus()
    capture(
        page,
        1250,
        "Ask Ciaren to generate the nodes and their connections.",
        submit,
        280,
    )
    submit.click()
    confirm = panel.get_by_role("button", name="Apply and save")
    expect(confirm).to_be_visible()
    expect(page.get_by_text("Proposed changes")).to_be_visible()
    api = context.request
    flow_id = flow_url.rsplit("/", 1)[1]
    flow_api = base + "/api/flows/" + flow_id
    assert not api.get(flow_api).json()["graph_json"].get("nodes")
    assert not api.get(base + "/api/runs").json()
    capture(page, 2800, "Review the proposed flow: four nodes, three connections.", left=280)
    confirm.focus()
    capture(page, 1550, "Approve the proposal to save it to the canvas.", confirm, 280)
    confirm.click()
    nodes = page.locator(".react-flow__node")
    expect(nodes).to_have_count(4)
    expect(page.locator(".react-flow__edge")).to_have_count(3)
    assert not api.get(base + "/api/runs").json()
    # Let React Flow finish fitting the newly measured graph before recording it.
    page.wait_for_timeout(600)
    capture(page, 2900, "The connected flow is saved and ready to run.")
    stage("manual run and download")
    run = page.get_by_role("button", name="Run", exact=True)
    run.focus()
    capture(page, 1150, "Choose Run to execute the flow.", run)
    run.click()
    page.wait_for_url(re.compile(r"/runs/[^/]+$"))
    graph = api.get(flow_api).json()["graph_json"]
    output = next(n for n in graph["nodes"] if n["type"] == "fileOutput")
    page.locator(f'.react-flow__node[data-id="{output["id"]}"]').click()
    download = page.get_by_role("button", name="Download output")
    with page.expect_download() as saved:
        download.click()
    with saved.value.path().open(encoding="utf-8-sig", newline="") as file:
        assert sorted(row["amount"] for row in csv.DictReader(file)) == ["2", "3", "4"]
    capture(page, 3000, "Four input rows become three distinct amounts.", download, 280)
    stage("check canvas, citation and activity reversal")
    page.goto(flow_url)
    node = next(n for n in graph["nodes"] if n["type"] == "limitRows")
    page.locator(f'.react-flow__node[data-id="{node["id"]}"]').click()
    assistant.click()
    panel.get_by_role("button", name="Explain selected node").click()
    expect(panel.get_by_role("link", name="Ciaren node guide")).to_be_visible()
    panel.get_by_role("button", name="Check canvas").click()
    expect(panel.get_by_text("Canvas checks passed.", exact=False)).to_be_visible()
    panel.get_by_role("button", name="Guides", exact=True).click()
    prompt.fill("How do I connect the two inputs of a Join?")
    panel.get_by_role("button", name="Ask the guides").click()
    expect(panel.locator('a[href*="/docs/transformations/join.md#L"]')).to_be_visible()
    for question, passage in (
        ("How do I set up an API key?", "To set up or register a provider API key"),
        ("Where can I see the history of assistant changes?", "To revert a saved assistant change"),
    ):
        prompt.fill(question)
        panel.get_by_role("button", name="Ask the guides").click()
        expect(panel.get_by_text(passage, exact=False)).to_be_visible()
        expect(panel.locator('a[href*="/docs/guide/flow-assistant-quick-start.md#L"]')).to_be_visible()
    prompt.fill("zzqxthw")
    panel.get_by_role("button", name="Ask the guides").click()
    expect(panel.get_by_text("I could not find a supporting passage", exact=False)).to_be_visible()
    expect(panel.locator('a[href*="/blob/"]')).to_have_count(0)
    panel.get_by_role("tab", name="Activity").click()
    panel.get_by_role("button", name="Preview reversal").click()
    panel.get_by_role("button", name="Confirm reversal").click()
    expect(panel.get_by_text("Reversal saved to activity.")).to_be_visible()
    page.reload()
    expect(nodes).to_have_count(0)
    assistant.click()
    panel.get_by_role("tab", name="Activity").click()
    expect(panel.get_by_role("listitem")).to_have_count(2)
    assert not api.get(flow_api).json()["graph_json"]["nodes"]
    assert len(api.get(base + "/api/runs").json()) == 1
    print("PASS tutorial: proposal, approval, three output amounts, guide, check and persisted reversal.")
