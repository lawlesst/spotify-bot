import argparse
import json
import logging
import random
import webbrowser
from pathlib import Path

import requests
from dotenv import dotenv_values

config = dotenv_values()

redirect_uri = "https://lawlesst.github.io/"
scope = "playlist-modify-private playlist-modify-public playlist-read-private playlist-read-collaborative"


def get_code():
    r = requests.get(
        "https://accounts.spotify.com/authorize",
        params={
            "response_type": "code",
            "client_id": config["CLIENT_ID"],
            "scope": scope,
            "redirect_uri": redirect_uri,
            "state": random.random(),
        },
    )
    r.raise_for_status()
    logging.info(
        f"Opening {r.url} in browser. Copy code parameter on redirected page."
    )
    # Open the URL
    _ = webbrowser.open(r.url)


def get_refresh_code(code):
    """
    curl -d client_id=$CLIENT_ID -d client_secret=$CLIENT_SECRET -d grant_type=authorization_code -d code=$CODE -d redirect_uri=$REDIRECT_URI https://accounts.spotify.com/api/token

    """
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        params={
            "client_id": config["CLIENT_ID"],
            "client_secret": config["CLIENT_SECRET"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
        },
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Spotify API auth.")
    parser.add_argument("action", choices=["code", "refresh-token"])
    parser.add_argument(
        "--code",
        required=False,
        help="Code obtained from redirect authentication",
    )

    args = parser.parse_args()

    if args.action == "code":
        get_code()
    else:
        if args.code is None:
            raise Exception(
                "Passing a code is required for getting the refresh token."
            )
        logging.info(f"Obtaining authentication details.")
        auth_info = get_refresh_code(args.code)
        auth_info["client_id"] = config["CLIENT_ID"]
        auth_info["client_secret"] = config["CLIENT_SECRET"]
        cwd = Path(__file__).parent
        auth_file = cwd.joinpath(".spotify-auth.json")
        with open(auth_file, "w") as f:
            json.dump(auth_info, f)

        print(f"Writing authentication file to: {auth_file}")
        print(json.dumps(auth_info, indent=2))


if __name__ == "__main__":
    logger = logging.basicConfig(level=logging.INFO)
    main()
