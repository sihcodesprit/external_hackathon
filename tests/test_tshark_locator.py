"""Tests for tshark_locator module."""

import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest

from netwatch.live.tshark_command import (
    build_live_capture_command,
    build_version_command,
)
from netwatch.live.tshark_locator import (
    detect_tshark,
    discover_candidates,
    env_tshark_hint,
    find_tshark,
    get_tshark_capabilities,
    get_tshark_version,
    health_check,
    locate_tshark,
    resolve_tshark,
    validate_tshark,
)
from netwatch.live.tshark_runner import (
    MockTsharkRunner,
    RealTsharkRunner,
)


class TestTsharkLocator:
    """Test TShark discovery and validation."""

    def test_discover_candidates_returns_list(self):
        candidates = discover_candidates()
        assert isinstance(candidates, list)
        assert all(isinstance(c, str) for c in candidates)
        # Should have at least some candidates
        assert len(candidates) > 0

    def test_env_tshark_hint_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("TSHARK_PATH", raising=False)
        monkeypatch.delenv("NETWATCH_TSHARK_PATH", raising=False)
        assert env_tshark_hint() is None

    def test_env_tshark_hint_tshark_path(self, monkeypatch):
        monkeypatch.setenv("TSHARK_PATH", "/custom/tshark")
        assert env_tshark_hint() == "/custom/tshark"

    def test_env_tshark_hint_legacy(self, monkeypatch):
        monkeypatch.delenv("TSHARK_PATH", raising=False)
        monkeypatch.setenv("NETWATCH_TSHARK_PATH", "/legacy/tshark")
        assert env_tshark_hint() == "/legacy/tshark"

    def test_env_tshark_hint_tshark_path_priority(self, monkeypatch):
        monkeypatch.setenv("TSHARK_PATH", "/explicit/tshark")
        monkeypatch.setenv("NETWATCH_TSHARK_PATH", "/legacy/tshark")
        assert env_tshark_hint() == "/explicit/tshark"

    def test_resolve_tshark_no_hint_returns_path_or_none(self):
        # This will return a path if tshark is on PATH, otherwise None
        result = resolve_tshark("")
        # We can't assert True/False since it depends on the test environment
        # Just verify it doesn't crash
        assert result is None or isinstance(result, str)

    def test_locate_tshark_caches(self, monkeypatch):
        # Call twice, should be fast on second call
        p1 = locate_tshark("")

        p2 = locate_tshark("")

        assert p1 == p2
        # Second call should be faster (cached)
        # Not strictly asserting timing but logic is there

    def test_validate_tshark_shape(self):
        info = validate_tshark("")
        assert "valid" in info
        assert "path" in info
        assert "version" in info
        assert "error" in info

    def test_find_tshark_shape(self):
        info = find_tshark("")
        assert set(info.keys()) >= {
            "installed", "path", "version", "platform",
            "capture_available", "reason"
        }
        assert isinstance(info["installed"], bool)
        assert isinstance(info["capture_available"], bool)

    def test_detect_tshark_shape(self):
        info = detect_tshark("")
        assert set(info.keys()) >= {
            "available", "installed", "capture_available",
            "path", "version", "platform", "reason", "error"
        }
        assert isinstance(info["available"], bool)

    def test_health_check_shape(self):
        info = health_check("")
        assert "tshark" in info
        assert "platform" in info
        assert "capture_available" in info
        tshark_info = info["tshark"]
        assert set(tshark_info.keys()) >= {"installed", "path", "version"}

    def test_get_tshark_capabilities_shape(self):
        info = get_tshark_capabilities("")
        assert set(info.keys()) >= {
            "available", "path", "version", "platform",
            "capture_available", "reason", "interfaces_available", "error"
        }

    def test_get_tshark_version(self):
        ver = get_tshark_version("")
        assert ver is None or isinstance(ver, str)


class TestTsharkCommand:
    """Test safe command builder."""

    def test_build_version_command(self):
        cmd = build_version_command("tshark")
        assert cmd == ["tshark", "--version"]

    def test_build_live_capture_command_basic(self):
        cmd = build_live_capture_command("tshark", "eth0")
        assert cmd[:3] == ["tshark", "-i", "eth0"]
        assert "-l" in cmd
        assert "-T" in cmd
        assert "ek" in cmd
        assert "-a" in cmd
        assert "duration:3600" in cmd

    def test_build_live_capture_command_with_filter(self):
        cmd = build_live_capture_command("tshark", "eth0", bpf_filter="port 80")
        assert "-f" in cmd
        assert "port 80" in cmd

    def test_build_live_capture_command_promiscuous(self):
        cmd = build_live_capture_command("tshark", "eth0", promiscuous=True)
        assert "-p" in cmd

    def test_build_live_capture_command_validates_interface(self):
        with pytest.raises(ValueError):
            build_live_capture_command("tshark", "eth0; rm -rf /")
        with pytest.raises(ValueError):
            build_live_capture_command("tshark", "")
        with pytest.raises(ValueError):
            build_live_capture_command("tshark", "x" * 300)

    def test_validate_output_format(self):
        cmd = build_live_capture_command("tshark", "eth0", output_format="json")
        assert "json" in cmd
        with pytest.raises(ValueError):
            build_live_capture_command("tshark", "eth0", output_format="invalid")


class TestTsharkRunner:
    """Test the TsharkRunner interface and implementations."""

    def test_real_runner_interface(self):
        runner = RealTsharkRunner()
        assert hasattr(runner, "launch")
        assert hasattr(runner, "terminate")

    def test_mock_runner(self):
        runner = MockTsharkRunner(output_lines=["line1", "line2"], stderr_tail="error", exit_code=0)
        proc = runner.launch(["tshark", "--version"])
        assert runner.launched_commands == [["tshark", "--version"]]
        # Read stdout
        lines = list(proc.stdout)
        assert lines == ["line1", "line2"]
        assert proc.poll() is None
        proc.terminate()
        assert proc.poll() == 0

    def test_mock_runner_fail_on_launch(self):
        runner = MockTsharkRunner(fail_on_launch=True)
        with pytest.raises(FileNotFoundError):
            runner.launch(["tshark", "--version"])

    def test_mock_runner_stderr(self):
        runner = MockTsharkRunner(stderr_tail="some error output")
        proc = runner.launch(["tshark"])
        assert proc.stderr.read() == "some error output"
        # Second read returns empty
        assert proc.stderr.read() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
