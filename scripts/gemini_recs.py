#!/usr/bin/env python3
"""
Generate a curated playlist using Gemini based on top tracks.
"""

import argparse
import json
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import Optional

from google import genai
from pydantic import BaseModel, Field

from spotify.client import Spotify
from spotify.utils import get_auth_file
from dotenv import dotenv_values

config = dotenv_values()


auth_file = get_auth_file()
data_dir = Path(__file__).parent.joinpath("data")
data_dir.mkdir(exist_ok=True, parents=True)


def clean_search_term(term: str) -> str:
    return re.sub(r"[^\w\s]", "", term)[:200]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


class Track(BaseModel):
    name: str = Field(description="The name of the track.")
    artist: str = Field(description="A string of artists who performed the track.")
    album: Optional[str] = Field(description="The album the track belongs to.")
    year: int = Field(description="The release year of the track.")


class SpotifyClient:
    def __init__(self) -> None:
        self.api = Spotify(auth_file=auth_file)

    def get_playlist_by_name(self, user: str, name: str):
        """Fetch playlist by name; returns None if not found."""
        return self.api.get_user_playlist_by_name(user, name)

    def get_top_tracks(
        self, term="long_term", cache_for_days=1, max=25, artists_only=False
    ):
        if artists_only is True:
            top_type = "artists"
        else:
            top_type = "tracks"

        top_tracks_file = data_dir.joinpath(f"top_{top_type}_{term}.json")

        if top_tracks_file.exists():
            last_modified_time = datetime.fromtimestamp(top_tracks_file.stat().st_mtime)
            if datetime.now() - last_modified_time < timedelta(days=cache_for_days):
                with top_tracks_file.open("r") as file:
                    return json.load(file)

        if artists_only is True:
            top = self.api.get_top_artists(term=term, max=max)
        else:
            top = self.api.get_top_tracks(term=term, max=max)
        with top_tracks_file.open("w") as file:
            json.dump(top, file)
        return top


class GeminiRecommender:
    def __init__(self, api_key: str) -> None:
        self.client = genai.Client(api_key=api_key)

    def generate_tracks(self, prompt: str) -> list[Track]:
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": list[Track],
                "temperature": 0,
            },
        )
        return json.loads(response.text)


def select_valid_tracks(
    candidates,
    favorite_pairs,
    min_year=2010,
    used_pairs=None,
    used_artists=None,
):
    if used_pairs is None:
        used_pairs = set()
    if used_artists is None:
        used_artists = set()

    selected = []
    for item in candidates:
        name = item.get("name")
        artist = item.get("artist")
        year = item.get("year")

        if not name or not artist or not isinstance(year, int):
            continue
        if year < min_year:
            continue

        pair = (normalize_text(name), normalize_text(artist))
        artist_key = normalize_text(artist)

        if pair in favorite_pairs:
            continue
        if pair in used_pairs:
            continue
        if artist_key in used_artists:
            continue

        selected.append(item)
        used_pairs.add(pair)
        used_artists.add(artist_key)

    return selected, used_pairs, used_artists


def build_recommendation_prompt(
    target_count,
    favorite_tracks,
    exclude_pairs,
    exclude_artists,
    min_year=2010,
):
    exclude_lines = []
    if exclude_pairs:
        exclude_lines.append("Do not include any of these tracks:")
        exclude_lines.extend(
            [f"- {name} by {artist}" for name, artist in sorted(exclude_pairs)]
        )
    if exclude_artists:
        exclude_lines.append("Do not include any tracks by these artists:")
        exclude_lines.extend([f"- {artist}" for artist in sorted(exclude_artists)])

    return dedent(
        f"""
You are very experienced music DJ and playlist curator. You have deep knowledge of music across all genres and eras. You understand musical trends, popular artists, and underground gems.

Create a Spotify playlist of {target_count} songs that are similar but different to my current favorite tracks. Use the list of my favorite tracks below to inform your selections. Surprise me with new music. Focus on creating a similar vibe but don't be afraid to stretch the mood to expose the user to new music.

Requirements:
 - don't include tracks from the favorite tracks list
 - don't include multiple tracks from the same artist
 - avoid popular mainstream songs; focus on lesser-known tracks and artists
 - don't include any grammy winners
 - all tracks year>={min_year}. This is a strict requirement
 - year must be an integer

Favorite tracks:
{chr(10).join([f'- {track}' for track in favorite_tracks])}

{chr(10).join(exclude_lines)}
"""
    ).format()


def format_track_lines(items):
    return [f"{item['name']} by {item['artist']} {item.get('year', '')}" for item in items]


def print_tracks_table(tracks):
    """Print tracks in a formatted table."""
    if not tracks:
        return
    
    print("\n" + "=" * 100)
    print(f"{'Track':<50} {'Artist':<30} {'Year':<8}")
    print("=" * 100)
    for track in tracks:
        name = track.get("name", "")[:49]
        artist = track.get("artist", "")[:29]
        year = str(track.get("year", ""))
        print(f"{name:<50} {artist:<30} {year:<8}")
    print("=" * 100 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a curated playlist using Gemini based on your top tracks."
    )
    parser.add_argument(
        "--term",
        choices=["short_term", "medium_term", "long_term"],
        default="long_term",
        help="Time range for top tracks.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=15,
        help="Number of recommended tracks to generate.",
    )
    parser.add_argument(
        "--top-count",
        type=int,
        default=40,
        help="Number of top tracks to analyze.",
    )
    parser.add_argument(
        "--playlist-name",
        default="Gemini Generated Playlist",
        help="Target playlist name to create/update.",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=2010,
        help="Minimum release year for recommendations.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate recommendations without modifying a playlist.",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Use the 'Liked Songs {year}' playlist as favorites. If not provided, selects a random year.",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("SPOTIFY_USER_ID"),
        help="Spotify user ID for playlist lookups.",
    )
    args = parser.parse_args()

    gemini_api_key = config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    if not auth_file.exists():
        raise Exception(
            f"Authentication file not found at {auth_file}. Run authentication.py as described in the README."
        )

    spot = SpotifyClient()
    recommender = GeminiRecommender(api_key=gemini_api_key)

    if args.year:
        playlist_name = f"Liked Songs {args.year}"
        playlist = spot.get_playlist_by_name(args.user, playlist_name)
        if not playlist:
            raise ValueError(f"Playlist '{playlist_name}' not found for user {args.user}.")
        track_uris = spot.api.get_playlist_tracks(playlist["id"])
        print(f"Using playlist: {playlist_name}")
    else:
        current_year = datetime.now().year
        possible_years = list(range(2015, current_year + 1))
        random.shuffle(possible_years)
        
        selected_year = None
        for year in possible_years:
            playlist_name = f"Liked Songs {year}"
            playlist = spot.get_playlist_by_name(args.user, playlist_name)
            if playlist:
                selected_year = year
                track_uris = spot.api.get_playlist_tracks(playlist["id"])
                print(f"Randomly selected: {playlist_name}")
                break
        
        if not selected_year:
            print("No 'Liked Songs' playlists found. Falling back to top tracks.")
            track_uris = spot.get_top_tracks(term=args.term, max=args.top_count)
    
    tracks = spot.api.get_track_info(track_uris)

    top_tracks = []
    seen_artists = []
    for track in tracks:
        if any(artist["name"] in seen_artists for artist in track["artists"]):
            continue
        top_tracks.append(
            f"{track['name']} by {', '.join([artist['name'] for artist in track['artists']])} {track['album']['release_date'][:4]}"
        )
        seen_artists.extend([artist["name"] for artist in track["artists"]])
        if len(top_tracks) >= 20:
            break

    remove_outliers_prompt = dedent(
        f"""
You are very experienced music DJ and playlist curator. You have deep knowledge of music across all genres and eras. You understand musical trends, popular artists, and underground gems.

Remove tracks from this lists that are not like the others. Focus on genre, popularity, vibe, and era to determine which tracks do not fit with the rest of the list.

Favorite tracks:
{chr(10).join([f'- {track}' for track in top_tracks])}
"""
    ).format()

    print("Removing outliers...")
    response = recommender.generate_tracks(remove_outliers_prompt)
    filtered_top_tracks_struct = response
    filtered_top_tracks = format_track_lines(filtered_top_tracks_struct)

    print("Final favorite tracks after outlier removal:")
    print_tracks_table(filtered_top_tracks_struct)

    favorite_pairs = {
        (normalize_text(item["name"]), normalize_text(item["artist"]))
        for item in filtered_top_tracks_struct
        if item.get("name") and item.get("artist")
    }

    selected_tracks = []
    used_pairs = set()
    used_artists = set()
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        remaining = args.count - len(selected_tracks)
        if remaining <= 0:
            break

        prompt = build_recommendation_prompt(
            target_count=remaining,
            favorite_tracks=filtered_top_tracks,
            exclude_pairs=used_pairs,
            exclude_artists=used_artists,
            min_year=args.min_year,
        )
        print(prompt)

        candidates = recommender.generate_tracks(prompt)
        valid, used_pairs, used_artists = select_valid_tracks(
            candidates,
            favorite_pairs=favorite_pairs,
            min_year=args.min_year,
            used_pairs=used_pairs,
            used_artists=used_artists,
        )

        if not valid:
            print(f"Attempt {attempt}: no valid tracks returned.")
            continue

        selected_tracks.extend(valid)
        print(f"Attempt {attempt}: accepted {len(valid)} tracks.")

    print("Generated Recommendations:")
    print_tracks_table(selected_tracks)

    if args.dry_run:
        print("Dry run enabled. Not updating playlist.")
        return

    print("Getting or creating playlist...")
    playlist_id, created = spot.api.get_or_create_playlist(
        user=args.user,
        name=args.playlist_name,
        public=False,
        description="Playlist generated by Gemini based on my top tracks.",
    )

    print(
        f"Playlist ID: {playlist_id} Name: {args.playlist_name} Created: {created}"
    )
    print(f"Searching for {len(selected_tracks)} tracks to add...")

    new_track_ids = []
    for item in selected_tracks:
        search_rsp = spot.api.search(
            f"track: {clean_search_term(item['name'])} album: {clean_search_term(item.get('album', ''))} artist: {clean_search_term(item.get('artist', ''))}"
        )
        try:
            track_id = search_rsp["tracks"]["items"][0]["id"]
        except (KeyError, IndexError):
            print(
                "No track found for search:",
                f"track: {clean_search_term(item['name'])} album: {clean_search_term(item.get('album', ''))} artist: {clean_search_term(item.get('artist', ''))}",
            )
            continue
        new_track_ids.append(f"spotify:track:{track_id}")

    new_track_ids = set(new_track_ids)

    print(f"Adding {len(new_track_ids)} tracks to playlist {args.playlist_name}")

    existing_playlist_tracks = spot.api.get_playlist_tracks(playlist_id)
    existing_track_ids = set(
        [
            f"spotify:track:{track['id']}"
            for track in spot.api.get_track_info(existing_playlist_tracks)
        ]
    )

    to_add = new_track_ids - existing_track_ids
    to_remove = existing_track_ids - new_track_ids

    print(f"Adding {len(to_add)} new tracks to playlist...")
    _ = spot.api.add_tracks_to_playlist(playlist_id=playlist_id, tracks=to_add)
    print(f"Removing {len(to_remove)} old tracks from playlist...")
    _ = spot.api.remove_tracks_from_playlist(playlist_id=playlist_id, tracks=to_remove)


if __name__ == "__main__":
    main()
