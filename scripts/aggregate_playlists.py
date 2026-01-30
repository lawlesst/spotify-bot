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
from harvest_public_radio_playlist import (
    PROGRAMS,
    UNDISCOVERED_DAILY_PLAYLIST_ID,
    UNDISCOVERED_WEEKLY_PLAYLIST_ID,
)
from spotify.client import Spotify
from spotify.utils import get_auth_file

config = dotenv_values()



cwd = Path(__file__).parent

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

auth_file = get_auth_file()


def main():
    playlist_choices = list(PROGRAMS.keys()) + ["all"]
    parser = argparse.ArgumentParser(
        description="Aggregate playlists into one large playlist."
    )
    parser.add_argument("program", choices=playlist_choices, nargs="+")
    parser.add_argument(
        "--playlist-type",
        default='daily',
        choices=['daily', 'weekly'],
        help="Aggregate tracks into a daily or weekly playlist.",
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

    if args.playlist_type == 'daily':
        logger.info("Aggregating into daily playlist.")
        target_playlist_id = UNDISCOVERED_DAILY_PLAYLIST_ID
    else:
        logger.info("Aggregating into weekly playlist.")
        target_playlist_id = UNDISCOVERED_WEEKLY_PLAYLIST_ID

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

    existing_tracks = api.get_playlist_tracks(target_playlist_id)

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
            _ = api.remove_tracks_from_playlist(target_playlist_id, to_remove)

        if len(to_add) > 0:
            logger.info(f"Adding {len(to_add)} tracks to combined playlist.")
            _ = api.add_tracks_to_playlist(target_playlist_id, to_add)

        if (len(to_remove) > 0) or (len(to_add) > 0):
            formatted_date = date.today().strftime("%Y-%m-%d")
            if args.playlist_type == 'daily':
                details = {
                    "description": f"Aggregation of tracks from various public radio programs. DJs > bots. Last updated {formatted_date}.",
                    "name": "Undiscovered Daily",
                }
            else:
                details = {
                    "description": f"Aggregation of tracks from various weekly public radio programs. DJs > bots. Last updated {formatted_date}.",
                    "name": "Undiscovered Weekly",
                }
            logger.info(f"Updating playlist details: {details['name']} - {formatted_date}")
            _ = api.update_playlist_details(target_playlist_id, details)


if __name__ == "__main__":
    logger = logging.getLogger()
    main()
#
