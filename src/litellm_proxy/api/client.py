"""
Chutes API Client for fetching utilization data.

This module provides a client for communicating with the Chutes AI API
to retrieve real-time utilization data for model deployments.
"""

import logging
from typing import Optional, Dict, Any, List

import requests

from litellm_proxy.exceptions import (
    ChutesAPIConnectionError,
    ChutesAPITimeoutError,
    ChutesAPIError,
)

logger = logging.getLogger(__name__)


class ChutesAPIClient:
    """
    Client for interacting with the Chutes AI API.

    This client handles all HTTP communication with the Chutes API,
    including fetching utilization data for model deployments.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.chutes.ai",
        timeout: int = 5,
    ):
        """
        Initialize the Chutes API client.

        Args:
            api_key: API key for Chutes API authentication.
            base_url: Base URL for the Chutes API (default: https://api.chutes.ai)
            timeout: Request timeout in seconds (default: 5)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        """Get or create a requests session."""
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "X-API-Key": self.api_key or "",
            "Content-Type": "application/json",
        }

    def get_utilization(self, chute_id: str) -> Optional[float]:
        """
        Fetch utilization for a specific chute.

        Args:
            chute_id: The Chutes deployment ID to check

        Returns:
            Utilization value (0.0 to 1.0), or None if unavailable
        """
        if not self.api_key:
            logger.warning(f"No Chutes API key available for chute {chute_id}")
            return None

        try:
            url = f"{self.base_url}/chutes/utilization"
            headers = self._get_headers()

            logger.debug(f"Fetching utilization for {chute_id} from {url}")
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            utilization = self._parse_utilization_response(data, chute_id)

            if utilization is not None:
                logger.info(f"Fetched utilization for {chute_id}: {utilization}")

            return utilization

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching utilization for {chute_id}")
            raise ChutesAPITimeoutError(f"Timeout fetching utilization for {chute_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching utilization for {chute_id}: {e}")
            raise ChutesAPIConnectionError(
                f"Error fetching utilization for {chute_id}: {e}"
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing utilization response for {chute_id}: {e}")
            raise ChutesAPIError(
                f"Error parsing utilization response for {chute_id}: {e}"
            )

    def get_bulk_utilization(self) -> Dict[str, float]:
        """
        Fetch utilization for all chutes in a single API call.

        Returns:
            Dictionary mapping chute_id to utilization value
        """
        if not self.api_key:
            logger.warning("No Chutes API key available")
            return {}

        try:
            url = f"{self.base_url}/chutes/utilization"
            headers = self._get_headers()

            logger.debug(f"Fetching bulk utilization from {url}")
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return self._parse_bulk_utilization(data)

        except requests.exceptions.Timeout:
            logger.error("Timeout fetching bulk utilization")
            raise ChutesAPITimeoutError("Timeout fetching bulk utilization")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching bulk utilization: {e}")
            raise ChutesAPIConnectionError(f"Error fetching bulk utilization: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing bulk utilization response: {e}")
            raise ChutesAPIError(f"Error parsing bulk utilization response: {e}")

    def _parse_utilization_response(
        self, data: Dict[str, Any], chute_id: str
    ) -> Optional[float]:
        """
        Parse utilization from API response.

        The API returns a list of chute utilization objects.

        Args:
            data: API response data (list or dict)
            chute_id: The chute ID being queried

        Returns:
            Utilization value (0.0 to 1.0) or None if not found
        """
        # Handle list response format (actual Chutes API format)
        if isinstance(data, list):
            # Try to find matching chute by chute_id first
            for item in data:
                if item.get("chute_id") == chute_id:
                    # Use current utilization (most real-time)
                    util = item.get("utilization_current")
                    if util is not None:
                        return float(util)
                    # Fallback to 5m average
                    util = item.get("utilization_5m")
                    if util is not None:
                        return float(util)
                    # Fallback to 15m average
                    util = item.get("utilization_15m")
                    if util is not None:
                        return float(util)

            # If not found by chute_id, try to match by name/model
            for item in data:
                name = item.get("name", "")
                chute_id_normalized = (
                    chute_id.replace("chute_", "").replace("_", "-").lower()
                )
                name_normalized = name.replace("/", " ").replace("-", " ").lower()
                if (
                    chute_id_normalized in name_normalized
                    or name_normalized in chute_id_normalized
                ):
                    util = item.get("utilization_current")
                    if util is not None:
                        return float(util)

            logger.warning(f"Could not find chute {chute_id} in utilization response")
            return None

        # Handle dict response format (legacy/alternative format)
        if isinstance(data, dict):
            # Try common field names
            for field in ["utilization", "util", "usage", "load", "capacity"]:
                if field in data:
                    value = data[field]
                    if isinstance(value, (int, float)):
                        return float(value)

            # Format 2: Per-chute data
            if "chutes" in data and isinstance(data["chutes"], dict):
                chute_data = data["chutes"].get(chute_id, {})
                for field in ["utilization", "util", "usage", "load"]:
                    if field in chute_data:
                        return float(chute_data[field])

                # Try getting from the first available chute
                if not chute_data:
                    for cid, cdata in data["chutes"].items():
                        for field in ["utilization", "util", "usage", "load"]:
                            if field in cdata:
                                return float(cdata[field])

            # Format 3: Array of chute data
            if isinstance(data.get("data"), list):
                for item in data["data"]:
                    if item.get("chute_id") == chute_id or item.get("id") == chute_id:
                        for field in ["utilization", "util", "usage", "load"]:
                            if field in item:
                                return float(item[field])

        logger.warning(f"Could not parse utilization from response: {data}")
        return None

    def _parse_bulk_utilization(self, data: Any) -> Dict[str, float]:
        """
        Parse bulk utilization data from API response.

        Args:
            data: API response data (list or dict)

        Returns:
            Dictionary mapping chute_id to utilization value
        """
        utilizations: Dict[str, float] = {}

        if isinstance(data, list):
            for item in data:
                chute_id = item.get("chute_id") or item.get("id")
                if chute_id:
                    util = item.get("utilization_current")
                    if util is not None:
                        utilizations[chute_id] = float(util)
                    else:
                        util = item.get("utilization_5m")
                        if util is not None:
                            utilizations[chute_id] = float(util)

        elif isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    chute_id = item.get("chute_id") or item.get("id")
                    if chute_id:
                        util = item.get("utilization_current")
                        if util is not None:
                            utilizations[chute_id] = float(util)

        return utilizations

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None
