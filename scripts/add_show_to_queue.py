"""
Harvest public radio playlists.
"""

import argparse
import logging
import sys

from dotenv import dotenv_values

from spotify.client import Spotify
from spotify.utils import get_auth_file

config = dotenv_values()


stdout_handler = logging.StreamHandler(stream=sys.stdout)
handlers = [stdout_handler]

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=handlers,
)

auth_file = get_auth_file()


def main():
    program_map = {
        "npr-news-now": {
            "name": "NPR News Now",
            "id": "6BRSvIBNQnB68GuoXJRCnQ",
        },
        "wsj-briefing": {
            "name": "WSJ Minute Briefing",
            "id": "44BcTpDWnfhcn02ADzs7iB",
        },
    }
    program_choices = list(program_map.keys())
    parser = argparse.ArgumentParser(description="Add shows to queue.")
    parser.add_argument("program", nargs="+", choices=program_choices)
    parser.add_argument(
        "--force",
        required=False,
        help="Force. Will add to queue if user is not currently listening.",
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        required=False,
        help="Dry run. Will get latest episode from Spotify but not add to queue.",
        action="store_true",
    )

    args = parser.parse_args()
    program_slugs = args.program

    api = Spotify(auth_file=auth_file)

    for slug in program_slugs:

        if args.force is True:
            pass
        else:
            if api.get_state() is False:
                print("Player is not active. Not adding to queue.")
                return

        program_info = program_map.get(slug)
        if program_info is None:
            raise Exception("Unable to locate show: {slug}")

        show_id = program_info["id"]

        show = api.get_show(show_id)
        # Latest episode
        show_uri = show["episodes"]["items"][0]["uri"]
        print(f"Located latest episode of {program_info['name']} - {show_uri}")
        # Make sure not in queue already or any other episodes
        # from same show
        user_queue = api.get_queue()
        queued_tracks = [t["uri"] for t in user_queue["queue"]]
        if user_queue.get("currently_playing") is not None:
            queued_tracks += user_queue["currently_playing"]["uri"]
        if show_uri in queued_tracks:
            print(f"{show_uri} already in queue. Skipping.")
        else:
            if args.dry_run is True:
                print(f"Dry run. Not adding {show_uri} to queue.")
            else:
                print(f"Adding {show_uri} to queue.")
                _ = api.add_to_queue(
                    show_uri
                )


if __name__ == "__main__":
    logger = logging.getLogger()
    main()
