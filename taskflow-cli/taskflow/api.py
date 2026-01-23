import requests
import os
import json
from pathlib import Path
from rich.console import Console
from .auth import get_token

console = Console()

BASE_URL = "http://localhost:8080"


def get_headers():
    """Get headers with JWT token if available."""
    headers = {}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_request(method: str, endpoint: str, **kwargs):
    """Make an authenticated API request."""
    headers = kwargs.get("headers", {})
    headers.update(get_headers())
    kwargs["headers"] = headers
    
    # Refresh BASE_URL in case config changed
    url = f"{BASE_URL}{endpoint}"
    
    try:
        response = requests.request(method, url, **kwargs)
        return response
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Connection Error:[/] {e}")
        return None