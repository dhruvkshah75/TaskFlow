import keyring
import requests
import os
import json
from pathlib import Path

SERVICE_NAME = "taskflow-cli"
TOKEN_KEY = "jwt_token"

BASE_URL = "http://localhost:8080"


def save_token(token: str):
    """Saves the JWT token to the system's secure keyring."""
    keyring.set_password(SERVICE_NAME, TOKEN_KEY, token)


def get_token():
    """Retrieves the stored token for API requests."""
    return keyring.get_password(SERVICE_NAME, TOKEN_KEY)


def delete_token():
    """Removes the token on logout."""
    keyring.delete_password(SERVICE_NAME, TOKEN_KEY)


def api_request(method, endpoint, **kwargs):
    """Wrapper for requests that automatically injects the Bearer token."""
    token = get_token()
    headers = kwargs.get("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    kwargs["headers"] = headers
    url = f"{BASE_URL}{endpoint}"
    return requests.request(method, url, **kwargs)