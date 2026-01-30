"""Shared utilities for spotify-bot scripts."""

from pathlib import Path


def get_auth_file() -> Path:
    """Get the Spotify authentication file path and verify it exists.
    
    Returns:
        Path: The path to the .spotify-auth.json file
        
    Raises:
        FileNotFoundError: If the authentication file does not exist
    """
    auth_file = Path(__file__).parent.parent.joinpath(".spotify-auth.json")
    if not auth_file.exists():
        raise FileNotFoundError(
            f"Authentication file not found at {auth_file}. "
            "Run authentication.py as described in the README."
        )
    return auth_file


def get_project_root() -> Path:
    """Get the project root directory.
    
    Returns:
        Path: The project root directory
    """
    return Path(__file__).parent.parent
