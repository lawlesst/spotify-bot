#!/usr/bin/env python3
"""
Create yearly playlists from liked songs based on when they were added.
"""

import argparse
from collections import defaultdict
from datetime import datetime

from dotenv import dotenv_values

from spotify.client import Spotify
from spotify.utils import get_auth_file

config = dotenv_values()

auth_file = get_auth_file()


def parse_added_year(added_at: str) -> int:
    return datetime.fromisoformat(added_at.replace("Z", "+00:00")).year


def get_season_and_year(added_at: str) -> tuple[str, int]:
    """Get (season, season_year) from timestamp.
    Winter spans years: Dec 2024 is labeled Winter 2025."""
    dt = datetime.fromisoformat(added_at.replace("Z", "+00:00"))
    month = dt.month
    year = dt.year

    if month in [12, 1, 2]:
        season = "Winter"
        season_year = year + 1 if month == 12 else year
    elif month in [3, 4, 5]:
        season = "Spring"
        season_year = year
    elif month in [6, 7, 8]:
        season = "Summer"
        season_year = year
    else:  # 9, 10, 11
        season = "Fall"
        season_year = year

    return season, season_year


def format_track_label(track) -> str:
    artists = ", ".join([a["name"] for a in track["artists"]])
    return f"{track['name']} — {artists}"


def main():
    parser = argparse.ArgumentParser(
        description="Create yearly playlists from your liked songs."
    )
    parser.add_argument(
        "--user",
        dest="user_id",
        default=config.get("SPOTIFY_USER_ID"),
        help="Spotify user id (required).",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create playlists as public (default is private).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tracks grouped by year without creating playlists.",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        help="Only include liked songs added on or after this year.",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        help="Only include liked songs added on or before this year.",
    )
    parser.add_argument(
        "--skip-full-albums",
        action="store_true",
        help="Skip albums that appear to be added in full.",
    )
    parser.add_argument(
        "--album-threshold",
        type=int,
        default=8,
        help="Minimum tracks from same album to consider it a full album add (default: 8).",
    )
    parser.add_argument(
        "--seasonal",
        action="store_true",
        help="Group playlists by season instead of year (Winter, Spring, Summer, Fall).",
    )
    args = parser.parse_args()

    if not args.user_id:
        raise ValueError("Provide --user or set SPOTIFY_USER_ID in your environment.")

    api = Spotify(auth_file=auth_file)

    print("Fetching saved tracks with added dates...")
    items = api.get_all_saved_tracks_with_added_at(max_tracks=None)

    if not items:
        print("No liked songs found.")
        return

    tracks_by_year = defaultdict(list)
    track_labels_by_year = defaultdict(list)
    albums_by_year = defaultdict(lambda: defaultdict(int))

    for item in items:
        added_at = item.get("added_at")
        track = item.get("track")
        if not added_at or not track:
            continue

        if args.seasonal:
            season, season_year = get_season_and_year(added_at)
            if args.min_year is not None and season_year < args.min_year:
                continue
            if args.max_year is not None and season_year > args.max_year:
                continue
            grouping_key = (season, season_year)
        else:
            year = parse_added_year(added_at)
            if args.min_year is not None and year < args.min_year:
                continue
            if args.max_year is not None and year > args.max_year:
                continue
            grouping_key = year

        album_id = track.get("album", {}).get("id")
        if album_id:
            albums_by_year[grouping_key][album_id] += 1
        tracks_by_year[grouping_key].append(track["uri"])
        track_labels_by_year[grouping_key].append(format_track_label(track))

    if args.skip_full_albums:
        full_album_ids = set()
        for year, albums in albums_by_year.items():
            for album_id, count in albums.items():
                if count >= args.album_threshold:
                    full_album_ids.add(album_id)
        
        filtered_tracks_by_year = defaultdict(list)
        filtered_labels_by_year = defaultdict(list)
        
        for item in items:
            added_at = item.get("added_at")
            track = item.get("track")
            if not added_at or not track:
                continue

            if args.seasonal:
                season, season_year = get_season_and_year(added_at)
                if args.min_year is not None and season_year < args.min_year:
                    continue
                if args.max_year is not None and season_year > args.max_year:
                    continue
                grouping_key = (season, season_year)
            else:
                year = parse_added_year(added_at)
                if args.min_year is not None and year < args.min_year:
                    continue
                if args.max_year is not None and year > args.max_year:
                    continue
                grouping_key = year

            album_id = track.get("album", {}).get("id")
            if album_id in full_album_ids:
                continue
            filtered_tracks_by_year[grouping_key].append(track["uri"])
            filtered_labels_by_year[grouping_key].append(format_track_label(track))
        
        tracks_by_year = filtered_tracks_by_year
        track_labels_by_year = filtered_labels_by_year

    for year in sorted(tracks_by_year.keys()):
        print(f"{year}: {len(tracks_by_year[year])} tracks")

    if args.dry_run:
        print("\nDry run enabled. Listing tracks by grouping:\n")
        for grouping_key in sorted(track_labels_by_year.keys()):
            if args.seasonal:
                season, season_year = grouping_key
                playlist_name = f"Liked Songs {season} {season_year}"
            else:
                playlist_name = f"Liked Songs {grouping_key}"
            print(f"{playlist_name}")
            for label in track_labels_by_year[grouping_key]:
                print(f"  - {label}")
            print("")
        return

    for grouping_key in sorted(tracks_by_year.keys()):
        if args.seasonal:
            season, season_year = grouping_key
            playlist_name = f"Liked Songs {season} {season_year}"
            description = f"Songs added to your liked songs in {season} {season_year}."
        else:
            playlist_name = f"Liked Songs {grouping_key}"
            description = f"Songs added to your liked songs in {grouping_key}."
        print(f"Creating/updating playlist: {playlist_name}")
        playlist_id, created = api.get_or_create_playlist(
            user=args.user_id,
            name=playlist_name,
            public=args.public,
            description=description,
        )

        if not created:
            api.clear_playlist_tracks(playlist_id)

        api.add_tracks_to_playlist(playlist_id, tracks_by_year[grouping_key])
        print(f"Added {len(tracks_by_year[grouping_key])} tracks to {playlist_name}.")


if __name__ == "__main__":
    main()
