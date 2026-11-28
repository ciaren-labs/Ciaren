"""Three-input regression uses pinned project files and a closed provider contract."""

from unittest.mock import AsyncMock

import pytest

from app.core.config import get_settings
from app.services import assistant_provider, assistant_training


def answer(context):
    return {
        "joins": [s["join"] for s in context["lookups"]],
        "target": context["target"]["ref"],
        "features": [s["features"][0]["ref"] for s in context["lookups"]],
        "model": "linear_regression",
    }


@pytest.fixture
async def case(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ASSISTANT_PROVIDER", "openai")
    monkeypatch.setattr(settings, "ML_ENABLED", True)
    flow = (await client.post("/api/flows", json={"name": "Regression"})).json()
    sources = [
        ("facts.csv", "private_customer,private_sku,private_target\n" + "PRIVATE-C,PRIVATE-P,15\n" * 20),
        ("first.csv", "private_customer,private_x\nPRIVATE-C,4\n"),
        ("second.csv", "private_sku,private_z\nPRIVATE-P,6\n"),
    ]
    datasets = []
    for name, csv in sources:
        response = await client.post("/api/datasets/upload", files={"file": (name, csv)})
        assert response.status_code == 201
        datasets.append(response.json()["id"])
    body = {
        "provider": "openai",
        "mode": "build",
        "question": "Estimate shipping costs",
        "revision": flow["updated_at"],
        "dataset_id": datasets[0],
        "second_dataset_id": datasets[1],
        "training": {"dataset_id": datasets[2], "versions": [1, 1, 1], "target": "private_target"},
    }
    url = f"/api/assistant/flows/{flow['id']}"
    mock = AsyncMock(side_effect=lambda p, i, c: answer(c))
    monkeypatch.setattr(assistant_provider, "complete", mock)
    return url, body, datasets, sources, mock


async def test_training_review_privacy_and_reversal(client, case):
    url, body, ids, _, mock = case
    r = await client.post(url + "/turn", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    outbound = repr(mock.await_args.args[2])
    assert all(
        token not in outbound for token in [*ids, "private_", "PRIVATE-", "facts.csv", "first.csv", "second.csv"]
    )
    assert not (await client.get(url.replace("/assistant", ""))).json()["graph_json"].get("nodes")
    assert not (await client.get(url + "/activity")).json()["entries"]
    assert not (await client.get("/api/runs")).json()
    delta = data["delta"]
    assert len(delta["added"]) == len(delta["connected"]) == 10
    train = next(n for n in delta["added"] if n["type"] == "mlTrainRegressor")
    assert train["data"]["config"]["feature_columns"] == ["private_x", "private_z"]
    assert train["data"]["config"]["target_column"] == "private_target"
    saved = await client.post(url + "/apply", json={"proposal": data["proposal"]})
    assert saved.is_success
    entry = (await client.get(url + "/activity")).json()["entries"][0]
    assert "private_" not in repr(entry) and all(i not in repr(entry) for i in ids)
    assert {f["source_port"] for f in entry["details"] if "source_port" in f} == {"model", "train", "test"}
    event_url = url + "/activity/" + entry["id"]
    preview = await client.post(event_url + "/preview", json={"revision": saved.json()["revision"]})
    assert preview.is_success
    assert (await client.post(event_url + "/revert", json={"proposal": preview.json()["confirmation"]})).is_success
    assert not (await client.get(url.replace("/assistant", ""))).json()["graph_json"]["nodes"]
    assert not (await client.get("/api/runs")).json()


@pytest.mark.parametrize("side", [0, 1, 2])
async def test_check_three_versions_at_review_and_confirmation(client, case, side):
    url, body, _, sources, _ = case
    r = await client.post(url + "/turn", json=body)
    assert r.is_success, r.text
    name, csv = sources[side]
    assert (await client.post("/api/datasets/upload", files={"file": (name, csv)})).is_success
    assert (await client.post(url + "/apply", json={"proposal": r.json()["proposal"]})).status_code == 409
    assert (await client.post(url + "/turn", json=body)).status_code == 409
    assert not (await client.get(url + "/activity")).json()["entries"]


@pytest.mark.parametrize(
    "fault", ["extra", "model", "swap", "wrong_target", "unknown_feature", "abstain", "cross_source"]
)
async def test_reject_unsupported_provider_plans(client, case, fault):
    url, body, _, _, mock = case

    def broken(provider, instruction, context):
        plan = answer(context)
        if fault == "extra":
            plan["nodes"] = ["pythonScript"]
        if fault == "model":
            plan["model"] = "custom"
        if fault == "swap":
            plan["joins"].reverse()
        if fault == "wrong_target":
            plan["target"] = plan["features"][0]
        if fault == "unknown_feature":
            plan["features"][1] = "unbound"
        if fault == "cross_source":
            plan["features"].reverse()
        return {} if fault == "abstain" else plan

    mock.side_effect = broken
    r = await client.post(url + "/turn", json=body)
    assert r.status_code == (200 if fault == "abstain" else 400)
    assert "proposal" not in r.json() and not (await client.get(url + "/activity")).json()["entries"]


@pytest.mark.parametrize(
    "fault",
    [
        "disabled",
        "uninstalled",
        "target",
        "duplicate",
        "scope",
        "repeat",
        "non_numeric",
        "incompatible",
        "prediction_collision",
        "ambiguous",
        "small",
        "missing_target",
    ],
)
async def test_validate_inputs_before_request(client, case, monkeypatch, fault):
    url, body, ids, _, mock = case
    if fault == "disabled":
        monkeypatch.setattr(get_settings(), "ML_ENABLED", False)
    if fault == "uninstalled":
        registry = assistant_training.get_registry()
        specs = [s for s in registry.node_specs() if s.id != "mlPredict"]
        monkeypatch.setattr(registry, "node_specs", lambda: specs)
    if fault == "target":
        body["training"]["target"] = "private_sku"
    if fault == "repeat":
        body["training"]["dataset_id"] = ids[1]
    if fault == "scope":
        project = (await client.post("/api/projects", json={"name": "Other"})).json()
        ds = (
            await client.post(
                "/api/datasets/upload",
                params={"project_id": project["id"]},
                files={"file": ("other.csv", "private_sku,extra\nPRIVATE-P,9\n")},
            )
        ).json()
        body["training"]["dataset_id"] = ds["id"]
    if fault == "missing_target":
        csv = "private_customer,private_sku,private_target\n" + "C,P,1.5\n" * 15 + "C,P,\n"
        ds = await client.post("/api/datasets/upload", files={"file": ("incomplete.csv", csv)})
        body["dataset_id"] = ds.json()["id"]
    if fault == "small":
        ds = await client.post(
            "/api/datasets/upload",
            files={"file": ("small.csv", "private_customer,private_sku,private_target\nC,P,1\n")},
        )
        body["dataset_id"] = ds.json()["id"]
    invalid = {
        "ambiguous": "private_sku,weight,volume\nPRIVATE-P,2,5\n",
        "duplicate": "private_sku,private_z\nPRIVATE-P,1\nPRIVATE-P,2\n",
        "incompatible": "private_sku,private_z\n14,5\n",
        "non_numeric": "private_sku,private_z\nPRIVATE-P,literal\n",
        "prediction_collision": "private_sku,ciaren_prediction\nPRIVATE-P,6\n",
    }
    if fault in invalid:
        response = await client.post("/api/datasets/upload", files={"file": ("replacement.csv", invalid[fault])})
        body["training"]["dataset_id"] = response.json()["id"]
    response = await client.post(url + "/turn", json=body)
    if fault == "disabled":
        assert response.status_code == 200 and response.json()["reason"] == "ml_disabled"
        assert "enable_ml" in {s["action"] for s in response.json()["suggestions"]}
    else:
        assert response.status_code == 400
    mock.assert_not_awaited()


async def test_ml_disabled_after_review(client, case, monkeypatch):
    url, body, _, _, _ = case
    proposal = (await client.post(url + "/turn", json=body)).json()["proposal"]
    monkeypatch.setattr(get_settings(), "ML_ENABLED", False)
    assert (await client.post(url + "/apply", json={"proposal": proposal})).status_code == 400
    assert not (await client.get(url + "/activity")).json()["entries"]
