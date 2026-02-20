#!/usr/bin/env python3
"""
LiteLLM Proxy Startup Script with Chutes Utilization Routing.

This script initializes the LiteLLM Router with the custom Chutes utilization
routing strategy and starts the proxy server.

Usage:
    python start_litellm.py

Environment Variables:
    CHUTES_API_KEY: API key for Chutes AI (required)
    LITELLM_MASTER_KEY: Master key for LiteLLM proxy (required)
    LITELLM_PORT: Port to run the proxy on (default: 4000)
    LITELLM_CONFIG_PATH: Path to litellm-config.yaml (default: ./litellm-config.yaml)
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_model_list_from_config(config_path: str) -> list:
    """
    Load model list from YAML configuration file.

    Args:
        config_path: Path to litellm-config.yaml

    Returns:
        List of model configurations
    """
    try:
        import yaml

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config.get("model_list", [])
    except ImportError:
        logger.warning("PyYAML not installed, using default model list")
        return get_default_model_list()
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return get_default_model_list()


def get_default_model_list() -> list:
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


def create_router(
    model_list: list,
    custom_routing_strategy,
    debug: bool = False,
) -> "Router":
    """
    Create and configure the LiteLLM Router.

    Args:
        model_list: List of model configurations
        custom_routing_strategy: Custom routing strategy instance
        debug: Enable debug logging

    Returns:
        Configured Router instance
    """
    from litellm.router import Router

    verbose = debug
    debug_level = "DEBUG" if debug else "INFO"

    router = Router(
        model_list=model_list,
        set_verbose=verbose,
        debug_level=debug_level,
        num_retries=3,
        timeout=300,
        routing_strategy="simple-shuffle",  # Default fallback
    )

    # Set custom routing strategy
    router.set_custom_routing_strategy(custom_routing_strategy)
    logger.info("Custom Chutes utilization routing strategy registered")

    return router


def start_proxy_server(router, port: int = 4000, host: str = "0.0.0.0"):
    """
    Start the LiteLLM proxy server.

    Args:
        router: Configured Router instance
        port: Port to listen on
        host: Host to bind to
    """
    import litellm
    from litellm.proxy.proxy_server import app

    # Set router for the proxy
    litellm.router = router

    logger.info(f"Starting LiteLLM proxy on {host}:{port}")
    logger.info("Press Ctrl+C to stop the server")

    # Run the proxy server
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start LiteLLM proxy with Chutes utilization routing"
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("LITELLM_PORT", "4000")),
        help="Port to run the proxy on (default: 4000)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LITELLM_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("LITELLM_CONFIG_PATH", "./litellm-config.yaml"),
        help="Path to litellm-config.yaml",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=30,
        help="Cache TTL in seconds for utilization data (default: 30)",
    )

    args = parser.parse_args()

    # Validate required environment variables
    chutes_api_key = os.environ.get("CHUTES_API_KEY")
    if not chutes_api_key:
        logger.error("CHUTES_API_KEY environment variable is required")
        sys.exit(1)

    master_key = os.environ.get("LITELLM_MASTER_KEY")
    if not master_key:
        logger.warning("LITELLM_MASTER_KEY not set, proxy will not be secured")

    # Load model list from config
    config_path = Path(args.config)
    if config_path.exists():
        model_list = load_model_list_from_config(str(config_path))
        logger.info(f"Loaded {len(model_list)} models from config")
    else:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        model_list = get_default_model_list()

    # Import and create custom routing strategy
    from chutes_routing import ChutesUtilizationRouting

    custom_routing = ChutesUtilizationRouting(
        chutes_api_key=chutes_api_key,
        cache_ttl=args.cache_ttl,
    )
    logger.info(f"Created Chutes utilization routing with {args.cache_ttl}s cache TTL")

    # Create router with custom strategy
    router = create_router(
        model_list=model_list,
        custom_routing_strategy=custom_routing,
        debug=args.debug,
    )

    # Start proxy server
    try:
        start_proxy_server(router, port=args.port, host=args.host)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
