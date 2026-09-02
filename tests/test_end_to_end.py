"""End-to-end pipeline smoke test.

Exercises the full chain:

    synthetic event data -> NetworkState construction -> normalize -> sequences
        -> World Model training -> risk head -> evaluation (+ baselines, unseen)
        -> K-step forecast -> MITRE mapping -> predictive graph -> SHAP
        -> counterfactual defensive simulation -> recommendation

Uses the fast LinearWorldModel (monkeypatched instead of the LSTM) so the whole
journey runs in seconds while still exercising every stage of the pipeline.
"""

import pytest

import main.netwatch.pipeline as pipeline_mod
from main.netwatch.pipeline import Pipeline


@pytest.fixture()
def pipe(monkeypatch):
    monkeypatch.setattr(pipeline_mod, "WORLD_MODEL_TYPE", "linear")
    pipe = Pipeline()
    data_info = pipe.load_data(n_traces=2, seed=42, duration_minutes=60)
    assert data_info["n_states"] > 0
    return pipe


def test_full_pipeline_end_to_end(pipe):
    # train
    train_info = pipe.train()
    assert train_info["risk_head_trained"] is True
    assert pipe.trainer.model.is_trained
    assert train_info["n_train_sequences"] > 0

    # evaluate (continuous world-model + baselines + unseen-attack)
    evals = pipe.evaluate()
    me = evals["model_evaluation"]
    assert me["world_model"]["prediction_metrics"]["continuous"]
    assert me["world_model"]["prediction_metrics"]["classification"]
    assert "baselines" in me and "logreg" in me["baselines"]
    assert "continuous" in evals["unseen_attack"]

    # forecast + counterfactual
    out = pipe.forecast_and_simulate(k=4)
    forecast = out["forecast"]
    assert forecast["status"] == "ok"
    assert len(forecast["future"]) == 4
    assert "current" in forecast and {"risk", "stage"} <= set(forecast["current"])

    # predictive attack graph
    graph = out["graph"]
    assert "nodes" in graph and "edges" in graph
    assert graph["counts"]["nodes"] == len(graph["nodes"])

    # MITRE trajectory covers current + future stages
    mitre = out["mitre_trajectory"]
    assert len(mitre) == 1 + 4
    assert all("has_mitre" in m and "technique_id" in m for m in mitre)

    # explanations attached to every forecast step
    for step in forecast["future"]:
        assert "explanation" in step
        assert step["explanation"]["top_features"]

    # counterfactual simulation + recommendation
    sim = out["counterfactual"]
    rec = sim["recommendation"]
    assert sim["status"] == "ok"
    assert "no_action" in sim["results"]
    assert rec["status"] == "ok"
    assert rec["recommended_action"]
    assert rec["risk_reduction"] >= 0.0
    assert rec["reason"]


def test_save_report_and_reload_linear(tmp_path, pipe):
    pipe.train()
    # save/load of the (linear) world model must round-trip
    model_path = tmp_path / "model.pkl"
    pipe.trainer.save(str(model_path))
    import pickle
    assert model_path.exists()
    with open(model_path, "rb") as f:
        assert pickle.load(f)["n_features"] > 0