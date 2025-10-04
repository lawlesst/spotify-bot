"""
Harvest public radio playlists.
"""

import argparse
import json
import logging
import logging.handlers
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import dotenv_values

config = dotenv_values()

cwd = Path(__file__).parent
parent_cwd = cwd.parent
sys.path.append(str(parent_cwd))
from scrapers.bbc import BBCScraper  # noqa
from scrapers.npr import get_episode  # noqa
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

PROGRAMS = {
    "rmp": {
        "widget": "5187f12ae1c8fae1350fa49f",
        "program_id": "5187f133e1c8fae1350fa4c7",
        "name": "WEMU Roots Music Project",
        "description": """
WEMU - The Roots Music Project with Jeremy Baldwin: https://www.wemu.org/show/the-roots-music-project-with-jeremy-baldwin. Last episode --updated--. Donate to WEMU: https://donate.nprstations.org/wemu/
            """,
    },
    "memphis": {
        "widget": "5187f12ae1c8fae1350fa49f",
        "program_id": "5187f130e1c8fae1350fa4a7",
        "name": "WEMU Memphis to Motown",
        "description": """
WEMU - From Memphis to Motown with Wendy Wright: https://www.wemu.org/show/from-memphis-to-motown. Last episode --updated--. Donate to WEMU: https://donate.nprstations.org/wemu/
            """,
    },
    "dead": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5187f5aee1c8c6a808e91ba4",
        "name": "WNCW Dead Air",
        "description": """
WNCW Dead Air: https://www.wncw.org/show/dead-air. Last episode --updated--. Donate to WNCW at: https://support.wncw.org/thankyougifts
""",
    },
    "country-gold": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5245f100ea9e43597100048e",
        "name": "WNCW Country Gold",
        "description": """
WNCW Country Gold: https://www.wncw.org/show/country-gold. Last episode --updated--. Donate to WNCW at https://support.wncw.org/thankyougifts
""",
    },
    "cosmic": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5187f5afe1c8c6a808e91bb4",
        "name": "WNCW Cosmic American Music Show",
        "description": """
WNCW Cosmic American Music Show: https://www.wncw.org/show/cosmic-american-music-show. Last episode --updated--. Donate to WNCW at https://support.wncw.org/thankyougifts
""",
    },
    "thelist": {
        "widget": "57c9be5be1c82c3e03c0777b",
        "program_id": "5ddeb21ac3f8702af1379877",
        "name": "WMOT The List, The Americana Chart Show",
        "skip_tracks_artists": "^LIST|^List",
        "description": """
--name--: https://www.wmot.org/show/the-list-the-americana-chart-show. Last episode --updated--. Donate to WMOT at https://donate.nprstations.org/wmot/2021-main-membership-form
""",
    },
    "highplains": {
        "widget": "51827282e1c82a388d82b12d",
        "program_id": "5182729ce1c82a388d82b1af",
        "name": "HPPR: High Plains Morning",
        "description": "--name--: https://www.hppr.org/show/high-plains-morning. Last episode: --updated--.",
        "skip_tracks_artists": "^In-Studio Performance",
    },
    "mel": {
        "widget": "51929bfde1c8886d5ccfb1d9",
        "program_id": "5e066050d638004d6fe76dee",
        "name": "WFPK: Mel's Diner",
        "description": "--name--: https://www.lpm.org/music. Last episode: --updated--",
    },
    "roland": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "60ec6586de940e741d46eef1",
        "name": "WNCW's Music Mix with Roland Dierauf",
        "description": """
WNCW's Music Mix with Roland Dierauf. Last episode --updated--. Donate to WNCW at https://support.wncw.org/thankyougifts
""",
    },
    # 5187f5b1e1c8c6a808e91bc9
    "martin": {
        "widget": "5187f56de1c8c6a808e91b8d",
        "program_id": "5187f5b1e1c8c6a808e91bc9",
        "name": "WNCW's Music Mix with Martin Anderson",
        "description": """
WNCW's Music Mix with Martin Anderson. Last episode --updated--. Donate to WNCW at https://support.wncw.org/thankyougifts
""",
    },
    "cerys": {
        "source": "bbc",
        "url": "https://www.bbc.co.uk/programmes/b00llg30/episodes/player",
        "name": "Cerys Matthews Show BBC Radio 6",
        "description": """
Cerys Matthews Show BBC Radio 6: https://www.bbc.co.uk/programmes/b00llg30. Last episode --updated--.
""",
    },
    "ricky": {
        "source": "bbc",
        "url": "https://www.bbc.co.uk/programmes/b00hh26l/episodes/player",
        "name": "Another Country with Ricky Ross BBC Radio Scotland",
        "description": """Another Country with Ricky Ross BBC Radio Scotland: https://www.bbc.co.uk/programmes/b00hh26l. Last episode --updated--."""
    }
}
UNDISCOVERED_DAILY_PLAYLIST_ID = "6DkqWyHXFG7721R277gsjt"
UNDISCOVERED_WEEKLY_PLAYLIST_ID = "4ElKWUbqpHT16i1QQsPMZs"

LAST_UPDATE_RE = re.compile(
    "(?:Last episode|Date)\:?\s([0-9]{4})-([0-9]{2})-([0-9]{2})"
)


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


def get_episode_orig(widget, program_id, episode_date):
    url = f"https://api.composer.nprstations.org/v1/widget/{widget}/playlist?prog_id={program_id}&datestamp={episode_date}"
    r = requests.get(url)
    logging.debug(f"Episode track URL: {url}")
    r.raise_for_status()
    data = r.json()
    try:
        return data["playlist"][0]
    except IndexError:
        logging.debug(f"No episode found for {program_id} on {episode_date}")
        return {}

def get_public_radio_tracks(episodes_from_date, program):
    # Program specific tracks to skip. Defined in config.
    program_skips = program.get("skip_tracks_artists")
    if program_skips is not None:
        program_skips = re.compile(program_skips)
    # Page through feed to find latest episode and update playlist.
    queries = []
    formatted_edate = episodes_from_date.strftime("%Y-%m-%d")
    logging.debug(f"Getting {program['name']} since {formatted_edate}")
    episode = get_episode(
        program["widget"],
        program["program_id"],
        formatted_edate,
    )
    for song in episode.get("playlist", []):
        track = song.get("trackName")
        artist = song.get("artistName")
        album = song.get("collectionName", "")
        if (track is None) or (artist is None):
            logging.debug(f"Skipping: {json.dumps(song)}")
            continue
        if program_skips is not None:
            track = song.get("trackName")
            skip = False
            if program_skips.search(track) is not None:
                skip = True
            elif program_skips.search(artist) is not None:
                skip = True
            if skip is True:
                logging.debug(f"Skipping: {json.dumps(song)}")
                continue
        query = f"track: {clean_search_term(track)} album: {clean_search_term(album)} artist: {clean_search_term(artist)}"
        queries.append(query)
        return queries

def main():
    playlist_choices = list(PROGRAMS.keys()) + ["all"]
    parser = argparse.ArgumentParser(
        description="Get a playlist from nprstations.org and upload to spotify."
    )
    parser.add_argument("program", choices=playlist_choices, nargs="+")
    parser.add_argument(
        "--dry-run",
        required=False,
        help="Dry run. Will harvest playlist but not upload to Spotify.",
        action="store_true",
    )
    parser.add_argument(
        "--force",
        required=False,
        help="Will harvest latest episode even if date matches Spotify date..",
        action="store_true",
    )

    args = parser.parse_args()
    program_slugs = args.program
    spotify_user = config["SPOTIFY_USER_ID"]

    if "all" in program_slugs:
        to_harvest = [v for v in PROGRAMS.values()]
    else:
        to_harvest = [PROGRAMS[p] for p in program_slugs]

    logging.info(f"Will harvest {len(to_harvest)} programs.")

    api = Spotify(auth_file=auth_file)

    for program in to_harvest:
        program_name = program["name"]

        spotify_playlist_details = api.get_user_playlist_by_name(
            spotify_user, program["name"]
        )
        if spotify_playlist_details is None:
            playlist_id, created = api.get_or_create_playlist(spotify_user, program["name"], program["description"].replace("--updated--", date.today().strftime("%Y-%m-%d")))
            if created is True:
                logging.info(f"{program_name}: playlist created. Spotify ID: {playlist_id}")
            spotify_playlist_details = api.get_user_playlist_by_name(
                spotify_user, program_name
            )

        if program.get("source") == "bbc":
            b = BBCScraper(program["url"])
            episode = b.get_latest_episode()
        else:
            episode = get_episode(program["widget"], program["program_id"])

        logging.debug(episode.date, len(episode.tracks), episode.tracks[0], episode.tracks[-1])
        # Check if playlist was last updated on the same date as the episode
        spotify_last_updated = None
        description_text = spotify_playlist_details.get("description", "")
        match = LAST_UPDATE_RE.search(description_text)
        if match:
            year, month, day = match.groups()
            spotify_last_updated = date(int(year), int(month), int(day))
        if spotify_last_updated == episode.date.date() and not args.force:
            logging.info(f"{program_name}: skipping {program_name}. Already up to date for {episode.date}")
            continue
        else:
            logging.info(f"{program_name}: updating. Episode date: {episode.date}. Spotify last updated: {spotify_last_updated}")
        # Update the description and playlist tracks.
        if len(episode.tracks) > 0:
            description = (
                program.get("description", "")
                .strip()
                .replace("--updated--", episode.date.strftime("%Y-%m-%d"))
                .replace("--name--", program["name"])
                .replace("\n", " ")
            )
            if args.dry_run is True:
                print(
                    f"** Dry run: {episode.date.strftime('%Y-%m-%d')} would add {len(episode.tracks)} tracks."
                )
                print(f"Description:\n {description}")
            else:

                logging.info(f"{program_name}: Searching spotify for {len(episode.tracks)} tracks.")
                found_tracks = []
                for track in episode.tracks:
                    q = f"track: {clean_search_term(track.name)} artist: {clean_search_term(track.artist)}"
                    try:
                       rsp = api.search(q)
                    except requests.exceptions.HTTPError as e:
                       logging.error(f"Spotify search error: {e}")
                       logging.error(f"Query: {q}")
                    
                    try:
                        track = rsp["tracks"]["items"][0]
                    except IndexError:
                        logging.debug(f"{program_name}: *** can't find track for {q}")
                        continue
                    found_tracks.append(f"spotify:track:{track['id']}")

                current_tracks = api.get_playlist_tracks(spotify_playlist_details["id"])
                new_tracks = list(set(found_tracks) - set(current_tracks))
                remove_tracks = list(set(current_tracks) - set(found_tracks))
                logging.info(f"{program_name}: adding {len(new_tracks)} tracks. Removing {len(remove_tracks)} tracks.")
                _ = api.add_tracks_to_playlist(spotify_playlist_details["id"], new_tracks)
                _ = api.remove_tracks_from_playlist(spotify_playlist_details["id"], remove_tracks)
                logging.info(
                    f"{program_name}: episode {episode.date}. {len(found_tracks)} songs added."
                )
                if len(new_tracks) > 0 or len(remove_tracks) > 0:
                    _ = api.update_playlist_details(
                        spotify_playlist_details["id"],
                        {"description": description},
                    )


if __name__ == "__main__":
    logger = logging.getLogger()
    main()
