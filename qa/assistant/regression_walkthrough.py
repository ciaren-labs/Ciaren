"""Exercise the same three-CSV training flow in simulation and paid one-turn acceptance."""

import csv
import math
import re
from contextlib import nullcontext

from editor_smoke import ROOT
from playwright.sync_api import expect
from walkthrough_checks import check_profile, check_turn, require

PROMPT = (
    "Join orders to customers and catalog. Predict shipping cost from distance and weight "
    "with linear regression. Evaluate on held-out orders."
)
FILES = ("orders.csv", "customers.csv", "catalog.csv")


def verify_proposal(reply, ids):
    require(bool(reply.get("proposal")), "No regression proposal was offered.")
    delta = reply["delta"]
    nodes, edges = delta["added"], delta["connected"]
    types = [n["type"] for n in nodes]
    expected = (
        ["fileInput"] * 3
        + ["join"] * 2
        + ["trainTestSplit", "mlTrainRegressor", "mlPredict", "mlEvaluate", "fileOutput"]
    )
    require(sorted(types) == sorted(expected) and len(edges) == 10, "Unexpected training graph topology.")

    def node(kind):
        return next(n for n in nodes if n["type"] == kind)

    inputs = {n["data"]["config"]["dataset_id"]: n for n in nodes if n["type"] == "fileInput"}
    require(
        set(inputs) == set(ids) and all(n["data"]["config"]["dataset_version"] == 1 for n in inputs.values()),
        "Input bindings changed.",
    )
    joins = {tuple(n["data"]["config"]["on"]): n for n in nodes if n["type"] == "join"}
    require(set(joins) == {("customer_id",), ("sku",)}, "Join keys did not match the selected files.")
    first, second = joins[("customer_id",)], joins[("sku",)]
    require(all(j["data"]["config"]["how"] == "inner" for j in (first, second)), "Unexpected Join mode.")
    split, train, predict, evaluate, output = [node(t) for t in expected[-5:]]
    cfg = train["data"]["config"]
    require(
        cfg["model_type"] == "linear_regression"
        and cfg["target_column"] == "shipping_cost"
        and cfg["feature_columns"] == ["distance_km", "weight_kg"],
        "Regressor target or features did not match.",
    )
    require(split["data"]["config"] == {"test_size": 0.2, "seed": 42}, "Unexpected holdout configuration.")
    wiring = {(e["source"], e["sourceHandle"], e["target"], e["targetHandle"]) for e in edges}
    expected_wiring = [
        (inputs[ids[0]], "out", first, "left"),
        (inputs[ids[1]], "out", first, "right"),
        (first, "out", second, "left"),
        (inputs[ids[2]], "out", second, "right"),
        (second, "out", split, "in"),
        (split, "train", train, "in"),
        (split, "test", predict, "in"),
        (train, "model", predict, "model"),
        (predict, "out", evaluate, "in"),
        (evaluate, "out", output, "in"),
    ]
    require(
        wiring == {(a["id"], ah, b["id"], bh) for a, ah, b, bh in expected_wiring},
        "Unexpected training or holdout wiring.",
    )
    return output["id"]


def walkthrough(context, base, provider, model, gif, work, stage):
    api = context.request

    def get(path):
        r = api.get(base + "/api" + path)
        require(r.ok, "Local API read failed.")
        return r.json()

    stage("regression configuration")
    check_profile(get, provider, model)
    stage("regression fixtures")
    datasets = []
    for name in FILES:
        response = api.post(
            base + "/api/datasets/upload",
            multipart={
                "file": {
                    "name": name,
                    "mimeType": "text/csv",
                    "buffer": (ROOT / "examples/shipping-regression" / name).read_bytes(),
                }
            },
        )
        require(response.ok, "Synthetic CSV upload failed.")
        datasets.append(response.json())
    ids = [d["id"] for d in datasets]
    flow = api.post(base + "/api/flows", data={"name": "Shipping cost", "project_id": datasets[0]["project_id"]})
    require(flow.ok, "Blank flow creation failed.")
    path = "/flows/" + flow.json()["id"]
    activity = "/assistant" + path + "/activity"

    def snapshot():
        return get(path), get(activity)["entries"], get("/runs")

    page = context.new_page()
    page.set_viewport_size({"width": 1160, "height": 780})
    page.set_default_timeout(15000)
    page.goto(base + path)
    assistant = page.get_by_role("button", name="Assistant", exact=True)
    expect(assistant).to_be_visible()
    page.get_by_role("button", name="Collapse panel").click()
    if gif:
        from smooth_recording import recording

        capture = recording(page, gif, work)
    else:
        capture = nullcontext(None)
    with capture as recorder:

        def pause(label, ms):
            if recorder:
                recorder.caption(label)
                page.wait_for_timeout(ms)

        def point(locator):
            locator.scroll_into_view_if_needed()
            if recorder:
                recorder.point(locator)

        def click(locator):
            point(locator)
            locator.click()

        pause("01   Start with three project CSVs", 650)
        click(assistant)
        panel = page.get_by_role("dialog")
        for select, value in (
            ("Input dataset", ids[0]),
            ("Right input for Join", ids[1]),
            ("Second lookup for regression", ids[2]),
            ("Regression target", "shipping_cost"),
        ):
            field = panel.get_by_label(select, exact=(select == "Input dataset"))
            point(field)
            field.select_option(value)
            if recorder:
                page.wait_for_timeout(360)
        privacy = panel.get_by_label("Include column names in this request")
        if not privacy.is_visible():
            click(panel.get_by_text("Data shared with provider", exact=True))
        privacy.check()
        click(panel.get_by_text("Data shared with provider", exact=True))
        question = panel.get_by_label("Request", exact=True)
        pause("02   Describe the joins, predictors and held-out test", 300)
        click(question)
        question.press_sequentially(PROMPT, delay=22 if recorder else 0)
        pause("02   Describe the joins, predictors and held-out test", 1100)
        before = snapshot()
        require(
            not before[0]["graph_json"].get("nodes") and not before[1] and not before[2], "Expected a blank saved flow."
        )
        stage("regression proposal")
        with page.expect_response(
            lambda r: r.url == base + "/api/assistant" + path + "/turn" and r.request.method == "POST", timeout=45000
        ) as response:
            click(panel.get_by_role("button", name="Create proposal"))
        check_turn(response.value, before, snapshot)
        output_id = verify_proposal(response.value.json(), ids)
        expect(panel.get_by_text("Proposed changes")).to_be_visible()
        pause("03   Review the generated nodes and connections", 1900)
        training = panel.get_by_text("linear_regression ·", exact=False)
        point(training)
        pause("03   Train on 80% and score the other 20%", 1350)
        stage("approve regression")
        click(panel.get_by_role("button", name="Apply and save"))
        expect(page.locator(".react-flow__node")).to_have_count(10)
        require(
            len(get(activity)["entries"]) == 1 and not get("/runs"), "Approval must save once without starting a run."
        )
        require(len(get(path)["graph_json"]["edges"]) == 10, "Saved connections did not match the preview.")
        pause("04   The connected flow is saved", 1800)
        stage("run and verify held-out shipping cost metrics")
        run = page.get_by_role("button", name="Run", exact=True)
        point(run)
        pause("05   Run the model explicitly", 550)
        click(run)
        page.wait_for_url(re.compile(r"/runs/[^/]+$"), timeout=180000)
        result = get("/runs/" + page.url.rsplit("/", 1)[1])
        require(result["status"] == "success", "Regression execution did not succeed.")
        results = result["node_results"]
        rows = {r["type"]: r for r in results}
        require(
            all(r["rows"] == 80 for r in results if r["type"] == "join")
            and rows["trainTestSplit"]["rows"] == 64
            and rows["mlPredict"]["rows"] == 16,
            "Unexpected train/test counts.",
        )
        require(bool(rows["mlTrainRegressor"]["mlflow_run_id"]), "Training produced no model run.")
        output_node = page.locator(f'.react-flow__node-runNode[data-id="{output_id}"]')
        expect(output_node).to_be_visible()
        click(output_node)
        download = page.get_by_role("button", name="Download output")
        with page.expect_download() as saved:
            download.click()
        with saved.value.path().open(encoding="utf-8-sig", newline="") as f:
            metrics = {r["metric"]: float(r["value"]) for r in csv.DictReader(f)}
        require(
            set(metrics) == {"mae", "r2"}
            and all(math.isfinite(v) for v in metrics.values())
            and 0 < metrics["mae"] < 0.6
            and 0.98 < metrics["r2"] <= 1,
            "Held-out metrics outside the synthetic fixture bounds.",
        )
        pause(f"06   Held-out orders: MAE ${metrics['mae']:.2f}  ·  R² {metrics['r2']:.3f}", 2300)
        print(
            f"PASS 2 joins, 64 train / 16 test, saved model, held-out MAE={metrics['mae']:.4f} R2={metrics['r2']:.4f}"
        )
