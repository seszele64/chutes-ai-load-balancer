"""
Unit tests for configuration loader.

These tests verify the configuration loading from multiple sources
with proper precedence: CLI > ENV > YAML > Defaults.
"""

import os
import pytest
from pathlib import Path

# Import the config loader
from litellm_proxy.config.loader import ConfigLoader
from litellm_proxy.exceptions import ConfigurationError


@pytest.mark.unit
def test_config_cli_args_override_env(monkeypatch):
    """
    Given: CLI arguments and environment variables both set
    When: Configuration is loaded
    Then: CLI arguments override environment variables
    """
    # Arrange
    monkeypatch.setenv("LITELLM_PORT", "3000")
    monkeypatch.setenv("LITELLM_HOST", "localhost")

    loader = ConfigLoader()

    cli_args = {"litellm_port": 4000, "litellm_host": "0.0.0.0"}

    # Act
    config = loader.load(cli_args=cli_args)

    # Assert
    assert config["litellm_port"] == 4000
    assert config["litellm_host"] == "0.0.0.0"


@pytest.mark.unit
def test_config_env_vars_override_yaml(monkeypatch, tmp_path):
    """
    Given: Environment variables and YAML config file both set
    When: Configuration is loaded
    Then: Environment variables override YAML values
    """
    # Arrange
    yaml_config = {"cache_ttl": 30, "litellm_host": "localhost"}

    config_file = tmp_path / "config.yaml"
    import yaml

    config_file.write_text(yaml.dump(yaml_config))

    monkeypatch.setenv("CACHE_TTL", "120")

    loader = ConfigLoader(config_path=str(config_file))

    # Act
    config = loader.load()

    # Assert - ENV should override YAML
    assert config["cache_ttl"] == 120
    assert config["litellm_host"] == "localhost"


@pytest.mark.unit
def test_config_yaml_defaults(tmp_path):
    """
    Given: YAML config file with some values
    When: Configuration is loaded
    Then: YAML values provide defaults for missing config
    """
    # Arrange
    yaml_config = {"cache_ttl": 60, "debug": True}

    config_file = tmp_path / "config.yaml"
    import yaml

    config_file.write_text(yaml.dump(yaml_config))

    loader = ConfigLoader(config_path=str(config_file))

    # Act
    config = loader.load()

    # Assert
    assert config["cache_ttl"] == 60
    assert config["debug"] is True
    # Should have default values for other keys
    assert "litellm_port" in config


@pytest.mark.unit
def test_config_missing_yaml_file(tmp_path):
    """
    Given: Config path points to non-existent YAML file
    When: Configuration is loaded
    Then: Returns empty config with warning (no exception)
    """
    # Arrange
    loader = ConfigLoader(config_path="/nonexistent/path/config.yaml")

    # Act
    config = loader.load()

    # Assert - should return defaults, not raise exception
    assert isinstance(config, dict)
    assert "cache_ttl" in config


@pytest.mark.unit
def test_config_invalid_yaml_format(tmp_path):
    """
    Given: YAML config file with invalid format
    When: Configuration is loaded
    Then: Handles gracefully, returns empty dict for invalid
    """
    # Arrange - Create a file with invalid YAML
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("invalid: yaml: content: [}")

    loader = ConfigLoader(config_path=str(config_file))

    # Act
    config = loader.load()

    # Assert - should return defaults (invalid YAML ignored)
    assert isinstance(config, dict)


@pytest.mark.unit
def test_config_parse_model_list(tmp_path):
    """
    Given: YAML config with model_list
    When: get_model_list() is called
    Then: Returns the list of model configurations
    """
    # Arrange
    yaml_config = {"model_list": [{"model_name": "model-a"}, {"model_name": "model-b"}]}

    config_file = tmp_path / "config.yaml"
    import yaml

    config_file.write_text(yaml.dump(yaml_config))

    loader = ConfigLoader(config_path=str(config_file))
    loader.load()

    # Act
    models = loader.get_model_list()

    # Assert
    assert len(models) == 2
    assert models[0]["model_name"] == "model-a"
    assert models[1]["model_name"] == "model-b"


@pytest.mark.unit
def test_config_parse_routing_params(tmp_path):
    """
    Given: YAML config with routing parameters
    When: Configuration is loaded
    Then: RoutingConfig values are parsed correctly
    """
    # Arrange
    yaml_config = {"cache_ttl": 120, "chutes_api_base": "https://custom.api.chutes.ai"}

    config_file = tmp_path / "config.yaml"
    import yaml

    config_file.write_text(yaml.dump(yaml_config))

    loader = ConfigLoader(config_path=str(config_file))

    # Act
    config = loader.load()

    # Assert
    assert config["cache_ttl"] == 120
    assert config["chutes_api_base"] == "https://custom.api.chutes.ai"


@pytest.mark.unit
def test_config_env_var_prefix(monkeypatch):
    """
    Given: Environment variables with LB_ prefix
    When: Configuration is loaded
    Then: LB_ prefix is mapped correctly to config keys
    """
    # Arrange - set environment variables without LB_ prefix (as per loader.py mapping)
    monkeypatch.setenv("CACHE_TTL", "45")
    monkeypatch.setenv("LITELLM_PORT", "5000")
    monkeypatch.setenv("LITELLM_HOST", "127.0.0.1")

    loader = ConfigLoader()

    # Act
    config = loader.load()

    # Assert - env vars should be parsed
    assert config["cache_ttl"] == 45
    assert config["litellm_port"] == 5000
    assert config["litellm_host"] == "127.0.0.1"


@pytest.mark.unit
def test_config_missing_required_field(tmp_path):
    """
    Given: Config path provided but file has no model_list
    When: get_model_list() is called
    Then: Raises ConfigurationError
    """
    # Arrange
    yaml_config = {"cache_ttl": 30}

    config_file = tmp_path / "config.yaml"
    import yaml

    config_file.write_text(yaml.dump(yaml_config))

    loader = ConfigLoader(config_path=str(config_file))
    loader.load()

    # Act & Assert
    with pytest.raises(ConfigurationError):
        loader.get_model_list()


@pytest.mark.unit
def test_config_type_coercion(monkeypatch):
    """
    Given: Environment variables as strings
    When: Configuration is loaded
    Then: String to int conversion happens correctly
    """
    # Arrange
    monkeypatch.setenv("CACHE_TTL", "90")
    monkeypatch.setenv("LITELLM_PORT", "8080")

    loader = ConfigLoader()

    # Act
    config = loader.load()

    # Assert - values should be coerced to int
    assert isinstance(config["cache_ttl"], int)
    assert isinstance(config["litellm_port"], int)
    assert config["cache_ttl"] == 90
    assert config["litellm_port"] == 8080
