"""
Aggregate public radio playlists.
"""

import argparse
import logging
import logging.handlers
import sys
from datetime import date
from math import log
from pathlib import Path

from dotenv import dotenv_values
from harvest_public_radio_playlist import COMBINED_PLAYLIST_ID, PROGRAMS

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
        "--combined-playlist-id",
        required=False,
        default=COMBINED_PLAYLIST_ID,
        help="Playlist ID for the playlist to be aggregated.",
    )
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

    logger.info(f"Total tracks: {len(all_tracks)}")

    existing_tracks = api.get_playlist_tracks(COMBINED_PLAYLIST_ID)

    already_in_playlist = set(all_tracks) & set(existing_tracks)
    logger.info(f"Already in playlist: {len(already_in_playlist)}")

    to_remove = set(existing_tracks) - set(all_tracks)
    to_add = set(all_tracks) - set(existing_tracks)

    if args.dry_run:
        logger.info("Dry run. Exiting.")
        return
    else:
        if len(to_remove) > 0:
            logger.info(f"Removing {len(to_remove)} tracks from combined playlist.")
            _ = api.remove_tracks_from_playlist(COMBINED_PLAYLIST_ID, to_remove)

        if len(to_add) > 0:
            logger.info(f"Adding {len(to_add)} tracks to combined playlist.")
            _ = api.add_tracks_to_playlist(COMBINED_PLAYLIST_ID, to_add)

        if (len(to_remove) > 0) or (len(to_add) > 0):
            formatted_date = date.today().strftime("%Y-%m-%d")
            details = {
                "description": f"Aggregation of tracks from various public radio programs. DJs > bots. Last updated {formatted_date}.",
                "name": "Undiscovered Daily",
            }
            _ = api.update_playlist_details(COMBINED_PLAYLIST_ID, details)


if __name__ == "__main__":
    logger = logging.getLogger()
    main()
