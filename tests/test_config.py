"""Tests for config.py — reload, persist, schema generation."""
import os


from config import BrainConfig, reload_config, get_setting_schema, persist_setting


class TestGetSettingSchema:
    def test_returns_all_groups(self):
        schema = get_setting_schema()
        assert "Database" in schema
        assert "Models" in schema
        assert "API" in schema
        assert "Voice" in schema
        assert "Daemons" in schema
        assert "Healing" in schema

    def test_each_group_has_key_and_type(self):
        schema = get_setting_schema()
        for group, fields in schema.items():
            for f in fields:
                assert "key" in f, f"Missing key in {group}"
                assert "type" in f, f"Missing type in {group}"
                assert "label" in f, f"Missing label in {group}"

    def test_model_options_present(self):
        schema = get_setting_schema()
        models = schema["Models"]
        coding = next(f for f in models if f["key"] == "MODEL_CODING")
        assert len(coding.get("options", [])) >= 2


class TestPersistSetting:
    def test_writes_new_setting(self, tmp_path):
        env_path = tmp_path / ".env"
        os.environ["DOTENV_PATH"] = str(env_path)

        persist_setting("TRACING_ENABLED", "false")
        content = env_path.read_text()
        assert "TRACING_ENABLED=false" in content

    def test_updates_existing_setting(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("TRACING_ENABLED=true\nAPI_PORT=8000\n")
        os.environ["DOTENV_PATH"] = str(env_path)

        persist_setting("TRACING_ENABLED", "false")
        content = env_path.read_text()
        assert "TRACING_ENABLED=false" in content
        assert "API_PORT=8000" in content  # preserved


class TestBrainConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("API_PORT", raising=False)
        cfg = BrainConfig()
        assert cfg.api_host == "0.0.0.0"
        assert cfg.api_port == 8000
        assert cfg.tracing_enabled is True

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("API_PORT", "9000")
        monkeypatch.setenv("TRACING_ENABLED", "false")
        cfg = BrainConfig()
        assert cfg.api_port == 9000
        assert cfg.tracing_enabled is False

    def test_summary_returns_dict(self):
        cfg = BrainConfig()
        summary = cfg.summary()
        assert "api" in summary
        assert "models" in summary
        assert isinstance(summary["models"], dict)

    def test_reload_config(self, monkeypatch):
        monkeypatch.delenv("API_PORT", raising=False)
        monkeypatch.setenv("API_PORT", "9876")
        cfg = reload_config()
        assert cfg.api_port == 9876
