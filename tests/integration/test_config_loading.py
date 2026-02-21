"""
Integration tests for configuration loading.

Tests verify that multiple components work together correctly for config loading.
Tests actual file loading, parsing, and override precedence.
"""

import os
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any

from litellm_proxy.config.loader import ConfigLoader
from litellm_proxy.exceptions import ConfigurationError


@pytest.mark.integration
class TestConfigLoading:
    """Integration tests for config loading from multiple sources."""

    def test_config_loads_from_yaml_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Given: A valid YAML configuration file exists
        When: ConfigLoader loads the configuration
        Then: Should parse and return the YAML values
        """
        # Arrange - Create a YAML config file
        config_data = {
            "chutes_api_key": "test-key-123",
            "chutes_api_base": "https://test.api.chutes.ai",
            "cache_ttl": 60,
            "litellm_port": 8080,
            "litellm_host": "127.0.0.1",
            "debug": True,
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Clear env vars that might interfere
        monkeypatch.delenv("CHUTES_API_KEY", raising=False)
        monkeypatch.delenv("CACHE_TTL", raising=False)

        # Act - Load configuration
        loader = ConfigLoader(config_path=str(config_file))
        config = loader.load()

        # Assert - YAML values should override defaults
        # Note: CHUTES_API_KEY may still come from defaults or YAML depending on precedence
        assert config["chutes_api_base"] == "https://test.api.chutes.ai"
        assert config["cache_ttl"] == 60
        assert config["litellm_port"] == 8080
        assert config["litellm_host"] == "127.0.0.1"
        assert config["debug"] is True

    def test_config_env_var_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Given: Both YAML file and environment variables are set
        When: ConfigLoader loads configuration
        Then: Environment variables should override YAML values
        """
        # Arrange - Create YAML config with cache_ttl = 30
        config_data = {
            "cache_ttl": 30,
            "litellm_port": 4000,
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Set environment variable to override
        monkeypatch.setenv("CACHE_TTL", "120")
        monkeypatch.setenv("LITELLM_PORT", "9000")

        # Act
        loader = ConfigLoader(config_path=str(config_file))
        config = loader.load()

        # Assert - Environment should override YAML
        assert config["cache_ttl"] == 120
        assert config["litellm_port"] == 9000

    def test_config_cli_args_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Given: YAML, environment variables, and CLI args are all set
        When: ConfigLoader loads configuration
        Then: CLI args should have highest priority
        """
        # Arrange - Create YAML config
        config_data = {
            "cache_ttl": 30,
            "litellm_port": 4000,
            "litellm_host": "0.0.0.0",
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Set environment variables
        monkeypatch.setenv("CACHE_TTL", "60")
        monkeypatch.setenv("LITELLM_PORT", "5000")

        # CLI args (highest priority)
        cli_args = {
            "cache_ttl": 180,
            "litellm_port": 8000,
        }

        # Act
        loader = ConfigLoader(config_path=str(config_file))
        config = loader.load(cli_args=cli_args)

        # Assert - CLI args should override everything
        assert config["cache_ttl"] == 180
        assert config["litellm_port"] == 8000
        # Non-overridden values from YAML should still be present
        assert config["litellm_host"] == "0.0.0.0"

    def test_config_missing_file_error(self, tmp_path: Path):
        """
        Given: A configuration file path that doesn't exist
        When: ConfigLoader attempts to load
        Then: Should not raise error, should use defaults
        """
        # Arrange - Non-existent config path
        missing_path = tmp_path / "nonexistent.yaml"

        # Act
        loader = ConfigLoader(config_path=str(missing_path))
        config = loader.load()

        # Assert - Should use defaults without error
        assert config is not None
        assert "cache_ttl" in config
        assert "litellm_port" in config

    def test_config_invalid_yaml_error(self, tmp_path: Path):
        """
        Given: A YAML file with invalid syntax
        When: ConfigLoader attempts to parse
        Then: Should handle error gracefully and use defaults
        """
        # Arrange - Create invalid YAML file
        config_file = tmp_path / "invalid_config.yaml"
        # Invalid YAML: unclosed quote
        config_file.write_text('cache_ttl: 60\ninvalid: "unclosed')

        # Act
        loader = ConfigLoader(config_path=str(config_file))
        config = loader.load()

        # Assert - Should not raise, should use defaults
        assert config is not None


@pytest.mark.integration
class TestConfigModelList:
    """Integration tests for model list loading."""

    def test_config_model_list_from_yaml(self, tmp_path: Path):
        """
        Given: YAML config with model_list defined
        When: get_model_list is called
        Then: Should return the list of models
        """
        # Arrange
        config_data = {
            "model_list": [
                {"model_name": "provider/model-a", "model_info": {"id": "chute-1"}},
                {"model_name": "provider/model-b", "model_info": {"id": "chute-2"}},
            ]
        }

        config_file = tmp_path / "models_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(config_path=str(config_file))
        loader.load()

        # Act
        models = loader.get_model_list()

        # Assert
        assert len(models) == 2
        assert models[0]["model_name"] == "provider/model-a"
        assert models[1]["model_name"] == "provider/model-b"

    def test_config_model_list_empty_error(self, tmp_path: Path):
        """
        Given: YAML config without model_list
        When: get_model_list is called
        Then: Should raise ConfigurationError
        """
        # Arrange
        config_data = {
            "cache_ttl": 30,
        }

        config_file = tmp_path / "no_models_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(config_path=str(config_file))
        loader.load()

        # Act & Assert
        with pytest.raises(ConfigurationError) as exc_info:
            loader.get_model_list()

        assert "No models configured" in str(exc_info.value)


@pytest.mark.integration
class TestConfigPrecedence:
    """Integration tests for configuration precedence order."""

    def test_config_precedence_order_yaml_then_env_then_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Given: All three config sources present (YAML, ENV, CLI)
        When: Configuration is loaded
        Then: Precedence should be: CLI > ENV > YAML > defaults
        """
        # Arrange - YAML config (lowest priority)
        config_data = {
            "cache_ttl": 10,
            "litellm_port": 4000,
            "litellm_host": "localhost",
            "debug": False,
        }

        config_file = tmp_path / "precedence.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Environment variables (middle priority)
        monkeypatch.setenv("CACHE_TTL", "20")
        monkeypatch.setenv("LITELLM_PORT", "5000")

        # CLI args (highest priority)
        cli_args = {
            "cache_ttl": 30,
        }

        # Act
        loader = ConfigLoader(config_path=str(config_file))
        config = loader.load(cli_args=cli_args)

        # Assert
        # CLI overrides ENV and YAML
        assert config["cache_ttl"] == 30
        # ENV overrides YAML
        assert config["litellm_port"] == 5000
        # YAML values present when not overridden
        assert config["litellm_host"] == "localhost"
        assert config["debug"] is False
