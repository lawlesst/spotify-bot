import argparse
import json
import logging
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import dotenv_values

config = dotenv_values()

cwd = Path(__file__).parent
parent_cwd = cwd.parent
sys.path.append(str(parent_cwd))

from spotify.client import Spotify

auth_file = parent_cwd.joinpath(".spotify-auth.json")
if not auth_file.exists():
    raise Exception(
        f"Authentication file not found at {auth_file}. Run authentication.py as described in the README."
    )

PROGRAMS = {
    "rmp": {
        "widget": "5187f12ae1c8fae1350fa49f",
        "program_id": "5187f133e1c8fae1350fa4c7",
        "playlist_id": "1683574235827",
        "name": "WEMU Roots Music Project",
        "interval": "weekly",
        "description": """
WEMU - The Roots Music Project with Jeremy Baldwin: https://www.wemu.org/show/the-roots-music-project-with-jeremy-baldwin. Last episode --updated--. Donate to WEMU: https://donate.nprstations.org/wemu/
            """,
    },
    "dead": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5187f5aee1c8c6a808e91ba4",
        "playlist_id": "1683914696382",
        "name": "WNCW Dead Air",
        "interval": "daily",
        "description": """
WNCW Dead Air: https://www.wncw.org/show/dead-air. Last episode --updated--. Donate to WNCW at: https://support.wncw.org/thankyougifts
""",
    },
    "country-gold": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5245f100ea9e43597100048e",
        "playlist_id": "1683916095604",
        "name": "WNCW Country Gold",
        "interval": "weekly",
        "description": """
WNCW Country Gold: https://www.wncw.org/show/country-gold. Last episode --updated--. Donate to WNCW at https://support.wncw.org/thankyougifts
""",
    },
    "cosmic": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5187f5afe1c8c6a808e91bb4",
        "playlist_id": "1683916456546",
        "name": "WNCW Cosmic American Music Show",
        "interval": "weekly",
        "description": """
WNCW Cosmic American Music Show: https://www.wncw.org/show/cosmic-american-music-show. Last episode --updated--. Donate to WNCW at https://support.wncw.org/thankyougifts
""",
    },
    "thelist": {
        "widget": "57c9be5be1c82c3e03c0777b",
        "program_id": "5ddeb21ac3f8702af1379877",
        "playlist_id": "1684505725296",
        "name": "WMOT The List, The Americana Chart Show",
        "skip_tracks_artists": "^LIST|^List",
        "description": """
--name--: https://www.wmot.org/show/the-list-the-americana-chart-show. Last episode --updated--. Donate to WMOT at https://donate.nprstations.org/wmot/2021-main-membership-form
""",
    },
    "highplains": {
        "widget": "51827282e1c82a388d82b12d",
        "program_id": "5182729ce1c82a388d82b1af",
        "playlist_id": "1684868853517",
        "name": "HPPR: High Plains Morning",
        "description": "--name--: https://www.hppr.org/show/high-plains-morning. Last episode: --updated--.",
        "skip_tracks_artists": "^In-Studio Performance",
    },
    "mel": {
        "widget": "51929bfde1c8886d5ccfb1d9",
        "program_id": "5e066050d638004d6fe76dee",
        "playlist_id": "1685106861340",
        "name": "WFPK: Mel's Diner",
        "description": "--name--: https://www.lpm.org/music. Date: --updated--",
        # "start_date": date(2023, 5, 25),
    },
}


def clean_search_term(term):
    # Remove punctuation and limit to 200 characters
    return re.sub(r"[^\w\s]", "", term)[:200]


def date_range(start_date, end_date, interval):
    """Helper for getting date ranges."""
    if interval == "weekly":
        n_interval = 7
    else:
        n_interval = 1
    for n in range(0, int((end_date - start_date).days) + 1, n_interval):
        yield start_date + timedelta(n)


def get_episode(widget, program_id, playlist_id, episode_date):
    url = f"https://api.composer.nprstations.org/v1/widget/{widget}/playlist?t={playlist_id}&prog_id={program_id}&datestamp={episode_date}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    try:
        return data["playlist"][0]
    except IndexError:
        print(
            f"No episode found for {program_id} on {episode_date}",
            file=sys.stderr,
        )
        return {}


# Dead Air: https://api.composer.nprstations.org/v1/widget/5187f56de1c8c6a808e91b8d/playlist?t=1683914696382&prog_id=5187f5aee1c8c6a808e91ba4&datestamp=2023-05-11&order=1&errorMsg=No+results+found.+Please+modify+your+search+and+try+again.


def main():
    playlist_choices = list(PROGRAMS.keys()) + ["all"]
    parser = argparse.ArgumentParser(
        description="Get a playlist from nprstations.org and upload to spotify."
    )
    parser.add_argument("program", choices=playlist_choices)
    parser.add_argument(
        "--dry-run",
        required=False,
        help="Dry run. Will harvest playlist but not upload to Spotify.",
        action="store_true",
    )

    args = parser.parse_args()
    program_slug = args.program

    DATE_CUTOFF = date(2023, 3, 1)

    if program_slug == "all":
        to_harvest = [v for v in PROGRAMS.values()]
    else:
        to_harvest = [PROGRAMS[program_slug]]

    logging.info(f"Will harvest {len(to_harvest)} programs.")

    api = Spotify(auth_file=auth_file)

    for program in to_harvest:
        program_skips = program.get("skip_tracks_artists")
        if program_skips is not None:
            program_skips = re.compile(program_skips)

        edate = program.get("start_date") or datetime.today().date()

        while True:
            formatted_edate = edate.strftime("%Y-%m-%d")
            print(
                f"Getting {program['name']} on {formatted_edate}",
                file=sys.stderr,
            )
            n = 0
            episode = get_episode(
                program["widget"],
                program["program_id"],
                program["playlist_id"],
                formatted_edate,
            )
            playlist_name = f"{program['name']}"
            tracks = []
            for song in episode.get("playlist", []):
                track = song.get("trackName")
                artist = song.get("artistName")
                album = song.get("collectionName", "")
                if (track is None) or (artist is None):
                    print(f"** Skipping: {json.dumps(song)}", file=sys.stderr)
                    continue
                if program_skips is not None:
                    track = song.get("trackName")
                    skip = False
                    if program_skips.search(track) is not None:
                        skip = True
                    elif program_skips.search(artist) is not None:
                        skip = True
                    if skip is True:
                        print(
                            f"** Skipping: {json.dumps(song)}", file=sys.stderr
                        )
                        continue
                query = f"track: {clean_search_term(track)} album: {clean_search_term(album)} artist: {clean_search_term(artist)}"
                rsp = api.search(query)
                logging.info(f"Looking for {track} by {artist} on {album}.")
                # Use the first track found.
                track = rsp["tracks"]["items"][0]
                if (track is None) or (track.get("id") is None):
                    logging.info(f"*** can't find track for {query}")
                else:
                    tracks.append(f"spotify:track:{track['id']}")
                    n += 1
            # Update the playlist tracks.
            if len(tracks) > 0:
                description = (
                    program.get("description", "")
                    .strip()
                    .replace("--updated--", formatted_edate)
                    .replace("--name--", program["name"])
                    .replace("\n", " ")
                )
                playlist_id, created = api.get_or_create_playlist(
                    config["SPOTIFY_USER_ID"],
                    playlist_name,
                    description,
                )
                if (created is False) and (args.dry_run is False):
                    # update the details
                    _ = api.update_playlist_details(
                        playlist_id,
                        {
                            "name": playlist_name,
                            "description": description,
                            "public": True,
                        },
                    )
                if args.dry_run is True:
                    print(
                        f"** Dry run: {edate} would add {len(tracks)} tracks."
                    )
                else:
                    logging.info(f"{edate} adding {len(tracks)} tracks.")
                    _ = api.update_playlist_tracks(playlist_id, tracks)
                    logging.info(f"Episode {edate}. {n} songs added.")
                break
            else:
                edate = edate - timedelta(days=1)
                if edate < DATE_CUTOFF:
                    logging.info(f"Reached {edate}. Breaking")
                    break


if __name__ == "__main__":
    logger = logging.basicConfig(level=logging.INFO)
    main()
