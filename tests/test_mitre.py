"""Unit tests for MITRE ATT&CK mapping."""

import pytest

from netwatch.mitre.attack_mapper import AttackMapper, STAGE_TO_MITRE


def test_known_stages_map():
    mapper = AttackMapper()
    for stage, mitre in STAGE_TO_MITRE.items():
        m = mapper.map(stage)
        assert m["has_mitre"] is True
        assert m["tactic"] == mitre["tactic"]
        assert m["technique_id"] == mitre["technique_id"]


def test_benign_and_none_are_unmapped():
    mapper = AttackMapper()
    for stage in (None, "", "Benign"):
        m = mapper.map(stage)
        assert m["has_mitre"] is False
        assert m["technique_id"] == "UNKNOWN"


def test_unknown_stage_unmapped():
    mapper = AttackMapper()
    m = mapper.map("NotARealStage")
    assert m["has_mitre"] is False


def test_map_trajectory_length():
    mapper = AttackMapper()
    stages = ["Reconnaissance", "Initial Access", "Execution", "Benign"]
    traj = mapper.map_trajectory(stages)
    assert len(traj) == len(stages)
    assert traj[0]["has_mitre"] is True
    assert traj[-1]["has_mitre"] is False