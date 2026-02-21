"""
Configuration Loader for LiteLLM Proxy.

This module provides a multi-source configuration loader that supports
loading from CLI arguments, environment variables, YAML files, and defaults.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Multi-source configuration loader.

    Loads configuration from multiple sources with precedence:
    1. CLI arguments (highest priority)
    2. Environment variables
    3. YAML configuration file
    4. Default values (lowest priority)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        defaults: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the configuration loader.

        Args:
            config_path: Path to YAML configuration file
            defaults: Default configuration values
        """
        self.config_path = config_path
        self.defaults = defaults or self._get_default_config()
        self._config: Dict[str, Any] = {}

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration values.

        Returns:
            Dictionary of default configuration
        """
        return {
            "chutes_api_key": os.environ.get("CHUTES_API_KEY", ""),
            "chutes_api_base": "https://api.chutes.ai",
            "cache_ttl": 30,
            "litellm_port": int(os.environ.get("LITELLM_PORT", "4000")),
            "litellm_host": os.environ.get("LITELLM_HOST", "0.0.0.0"),
            "litellm_master_key": os.environ.get("LITELLM_MASTER_KEY", ""),
            "debug": False,
        }

    def load(self, cli_args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Load configuration from all sources.

        Args:
            cli_args: CLI arguments dictionary (highest priority)

        Returns:
            Merged configuration dictionary
        """
        # Start with defaults
        config = self.defaults.copy()

        # Load from YAML if available
        if self.config_path:
            yaml_config = self._parse_yaml()
            if yaml_config:
                config = self._merge_config(config, yaml_config)

        # Load from environment variables
        env_config = self._parse_env()
        config = self._merge_config(config, env_config)

        # Load from CLI args (highest priority)
        if cli_args:
            config = self._merge_config(config, cli_args)

        self._config = config
        logger.info(f"Configuration loaded: {len(config)} keys")

        return config

    def _parse_yaml(self) -> Dict[str, Any]:
        """
        Parse YAML configuration file.

        Returns:
            Configuration dictionary from YAML file
        """
        if not self.config_path:
            return {}

        config_path = Path(self.config_path)
        if not config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return {}

        try:
            import yaml

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            if config and isinstance(config, dict):
                logger.info(f"Loaded config from {self.config_path}")
                return config

        except ImportError:
            logger.warning("PyYAML not installed, skipping YAML config")
        except Exception as e:
            logger.error(f"Error parsing YAML config: {e}")

        return {}

    def _parse_env(self) -> Dict[str, Any]:
        """
        Parse configuration from environment variables.

        Returns:
            Configuration dictionary from environment
        """
        config: Dict[str, Any] = {}

        # Map environment variables to config keys
        env_mappings = {
            "CHUTES_API_KEY": "chutes_api_key",
            "CHUTES_API_BASE": "chutes_api_base",
            "CACHE_TTL": "cache_ttl",
            "LITELLM_PORT": "litellm_port",
            "LITELLM_HOST": "litellm_host",
            "LITELLM_MASTER_KEY": "litellm_master_key",
            "DEBUG": "debug",
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Type conversion
                if config_key in ("cache_ttl", "litellm_port"):
                    try:
                        config[config_key] = int(value)
                    except ValueError:
                        config[config_key] = value
                elif config_key == "debug":
                    config[config_key] = value.lower() in ("true", "1", "yes")
                else:
                    config[config_key] = value

        return config

    def _merge_config(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries.

        Args:
            base: Base configuration
            override: Override configuration (takes precedence)

        Returns:
            Merged configuration dictionary
        """
        result = base.copy()
        result.update(override)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def get_model_list(self) -> list:
        """
        Get the model list from configuration.

        Returns:
            List of model configurations
        """
        if not self.config_path:
            return self._get_default_model_list()

        config_path = Path(self.config_path)
        if not config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._get_default_model_list()

        try:
            import yaml

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            return config.get("model_list", [])

        except ImportError:
            logger.warning("PyYAML not installed, using default model list")
            return self._get_default_model_list()
        except Exception as e:
            logger.error(f"Error loading model list: {e}")
            return self._get_default_model_list()

    def _get_default_model_list(self) -> list:
        """
        Get default model list if config file is not available.

        Returns:
            Default list of model configurations
        """
        chutes_api_key = os.environ.get("CHUTES_API_KEY", "")
        return [
            {
                "model_name": "chutes-models",
                "litellm_params": {
                    "model": "openai/moonshotai/Kimi-K2.5-TEE",
                    "api_base": "https://llm.chutes.ai/v1",
                    "api_key": chutes_api_key,
                },
                "model_info": {
                    "id": "kimi-k2.5-tee",
                    "chute_id": "chute_kimi_k2.5_tee",
                    "order": 1,
                },
            },
            {
                "model_name": "chutes-models",
                "litellm_params": {
                    "model": "openai/zai-org/GLM-5-TEE",
                    "api_base": "https://llm.chutes.ai/v1",
                    "api_key": chutes_api_key,
                },
                "model_info": {
                    "id": "glm-5-tee",
                    "chute_id": "chute_glm_5_tee",
                    "order": 2,
                },
            },
            {
                "model_name": "chutes-models",
                "litellm_params": {
                    "model": "openai/Qwen/Qwen3.5-397B-A17B-TEE",
                    "api_base": "https://llm.chutes.ai/v1",
                    "api_key": chutes_api_key,
                },
                "model_info": {
                    "id": "qwen3.5-397b-tee",
                    "chute_id": "chute_qwen3.5_397b_tee",
                    "order": 3,
                },
            },
        ]
