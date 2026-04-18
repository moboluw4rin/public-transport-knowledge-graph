"""Shared utilities for the London Underground knowledge graph pipelines."""

import os
from typing import Any

import requests
from dotenv import load_dotenv as _load_dotenv # pylint: disable=C0411
from rdflib import Namespace


EX = Namespace("http://example.org/ontology-express#")
INST = Namespace("http://example.org/instances#")

TFL_API_BASE = "https://api.tfl.gov.uk"


def load_env() -> None:
    """Load environment variables from a .env file."""
    _load_dotenv()


def get_env_var(name: str, required: bool = False) -> str | None:
    """Read an environment variable, optionally requiring it."""
    value = os.environ.get(name)
    if required and not value:
        raise EnvironmentError(f"{name} is not set. Run: export {name}=your_key_here")
    return value


def get_tfl_api_key() -> str:
    """Get the TfL API key from the environment."""
    return get_env_var("TFL_API_KEY", required=True)


def safe_uri(value: str) -> str:
    """Convert a raw string into a safe URI fragment."""
    return (
        value.strip()
        .replace(" ", "_")
        .replace("/", "-")
        .replace("'", "")
        .replace("&", "and")
        .replace("(", "")
        .replace(")", "")
    )


def request_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 30,
) -> Any:
    """Fetch JSON from a URL and raise a runtime error on failure."""
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON from {url}: {exc}") from exc
