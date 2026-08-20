"""Tests for OpenAPI SDK generation (Python + TypeScript)."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.main import app


class TestSchemaExport:
    def test_schema_file_written(self) -> None:
        from scripts.generate_sdks import SCHEMA_PATH

        # Verify schema path is under docs/
        assert str(SCHEMA_PATH).endswith("docs/openapi.json")

    def test_openapi_schema_is_valid_json(self) -> None:
        schema = app.openapi()
        assert "openapi" in schema
        assert "paths" in schema
        assert len(schema["paths"]) > 0


class TestPythonSDKGeneration:
    def test_config_file_exists(self) -> None:
        config = Path(".openapi-python-client.toml")
        assert config.exists()
        content = config.read_text()
        assert "project_name" in content
        assert "output_path" in content

    def test_sdk_output_dir_exists(self) -> None:
        sdk_dir = Path("sdk/python")
        assert sdk_dir.exists()
        assert (sdk_dir / ".gitkeep").exists()

    def test_generate_python_sdk_function_exists(self) -> None:
        from scripts.generate_sdks import generate_python_sdk
        assert callable(generate_python_sdk)


class TestTypeScriptSDKGeneration:
    def test_sdk_output_dir_exists(self) -> None:
        sdk_dir = Path("sdk/typescript")
        assert sdk_dir.exists()
        assert (sdk_dir / ".gitkeep").exists()

    def test_generate_typescript_sdk_function_exists(self) -> None:
        from scripts.generate_sdks import generate_typescript_sdk
        assert callable(generate_typescript_sdk)


class TestCLIGenerateSDKs:
    def test_generate_sdks_command_exists(self) -> None:
        from app.cli import app as cli_app
        commands = [cmd.name for cmd in cli_app.registered_commands]
        assert "generate-sdks" in commands


class TestGitignore:
    def test_sdk_dirs_ignored(self) -> None:
        gi = Path(".gitignore").read_text()
        assert "sdk/python/" in gi
        assert "sdk/typescript/" in gi

    def test_gitkeep_preserved(self) -> None:
        gi = Path(".gitignore").read_text()
        assert "!sdk/**/.gitkeep" in gi


class TestCIWorkflow:
    def test_workflow_file_exists(self) -> None:
        wf = Path(".github/workflows/generate-sdks.yml")
        assert wf.exists()

    def test_workflow_triggers_on_release(self) -> None:
        wf = yaml.safe_load(Path(".github/workflows/generate-sdks.yml").read_text())
        # PyYAML parses bare "on" as boolean True
        assert "release" in wf.get("on", wf.get(True, {}))

    def test_workflow_has_generate_step(self) -> None:
        wf = yaml.safe_load(Path(".github/workflows/generate-sdks.yml").read_text())
        steps = wf["jobs"]["generate"]["steps"]
        step_names = [s.get("name", "") for s in steps]
        assert any("Generate SDKs" in name for name in step_names)
