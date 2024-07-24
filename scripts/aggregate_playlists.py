"""
Aggregate public radio playlists.
"""

import argparse
import logging
import logging.handlers
import sys
from datetime import date
from pathlib import Path

from dotenv import dotenv_values
from harvest_public_radio_playlist import PROGRAMS

config = dotenv_values()

cwd = Path(__file__).parent
parent_cwd = cwd.parent
sys.path.append(str(parent_cwd))
# Add client to path.
from spotify.client import Spotify

file_handler = logging.handlers.RotatingFileHandler(
    filename=cwd.joinpath("pr.log"),
    mode="a",
    maxBytes=5 * 1024 * 1024,
    backupCount=0,
    encoding=None,
    delay=0,
)
stdout_handler = logging.StreamHandler(stream=sys.stdout)
handlers = [file_handler, stdout_handler]

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=handlers,
)

auth_file = parent_cwd.joinpath(".spotify-auth.json")
if not auth_file.exists():
    raise Exception(
        f"Authentication file not found at {auth_file}. Run authentication.py as described in the README."
    )


def main():
    playlist_choices = list(PROGRAMS.keys()) + ["all"]
    parser = argparse.ArgumentParser(
        description="Aggregate playlists into one large playlist."
    )
    parser.add_argument("program", choices=playlist_choices, nargs="+")
    parser.add_argument(
        "--dry-run",
        required=False,
        help="Dry run. Will harvest playlist but not upload to Spotify.",
        action="store_true",
    )

    args = parser.parse_args()
    program_slugs = args.program
    spotify_user = config["SPOTIFY_USER_ID"]

    if "all" in program_slugs:
        to_aggregate = [v for v in PROGRAMS.values()]
    else:
        to_aggregate = [PROGRAMS[p] for p in program_slugs]

    api = Spotify(auth_file=auth_file)

    all_tracks = []

    for program in to_aggregate:
        playlist_details = api.get_user_playlist_by_name(spotify_user, program["name"])
        if playlist_details is None:
            continue
        tracks = api.get_playlist_tracks(playlist_details["id"])
        logger.info(f"{playlist_details['name']} -- {len(tracks)} tracks.")
        all_tracks.extend(tracks)

    to_add = set(all_tracks)
    logger.info(f"Total tracks: {len(to_add)}")

    combined_playlist_id = "6DkqWyHXFG7721R277gsjt"

    logger.info(f"Clearing existing tracks from {combined_playlist_id}.")
    _ = api.clear_playlist_tracks(combined_playlist_id)
    logger.info(f"Adding {len(to_add)} tracks to {combined_playlist_id}.")
    _ = api.add_tracks_to_playlist(combined_playlist_id, to_add)

    formatted_date = date.today().strftime("%Y-%m-%d")
    details = {
        "description": f"Aggregation of tracks from various public radio programs. DJs > bots. Last updated {formatted_date}.",
        "name": "Undiscovered Daily",
    }
    _ = api.update_playlist_details(combined_playlist_id, details)


if __name__ == "__main__":
    logger = logging.getLogger()
    main()
