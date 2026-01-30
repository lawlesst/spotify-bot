"""
Clear a Spotify playlist by id or name.
"""

import argparse
from datetime import datetime, timedelta

from dotenv import dotenv_values

from spotify.client import Spotify
from spotify.utils import get_auth_file

config = dotenv_values()

auth_file = get_auth_file()


def resolve_playlist_id(api, playlist_id, playlist_name, user_id):
    if playlist_id:
        return playlist_id

    if not playlist_name:
        raise ValueError("Provide --id or --name to select a playlist.")

    if not user_id:
        raise ValueError(
            "Provide --user or set SPOTIFY_USER_ID in your environment to resolve playlist by name."
        )

    details = api.get_user_playlist_by_name(user_id, playlist_name)
    if details is None:
        raise ValueError(f"No playlist named '{playlist_name}' found for user {user_id}.")
    return details["id"]


def main():
    parser = argparse.ArgumentParser(description="Clear a Spotify playlist by id or name.")
    parser.add_argument("--id", dest="playlist_id", help="Playlist id to clear")
    parser.add_argument("--name", dest="playlist_name", help="Playlist name to clear")
    parser.add_argument(
        "--user",
        dest="user_id",
        default=config.get("SPOTIFY_USER_ID"),
        help="Spotify user id (required for --name).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many tracks would be removed without modifying the playlist.",
    )
    parser.add_argument(
        "--remove-recent",
        action="store_true",
        help="Remove tracks played within the last N days instead of clearing the whole playlist.",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=7,
        help="Number of days to look back when using --remove-recent (default: 7).",
    )
    args = parser.parse_args()

    api = Spotify(auth_file=auth_file)

    playlist_id = resolve_playlist_id(
        api, args.playlist_id, args.playlist_name, args.user_id
    )

    tracks = api.get_playlist_tracks(playlist_id)
    track_count = len(tracks)
    print(f"Playlist {playlist_id} has {track_count} tracks.")

    if track_count == 0:
        print("Playlist is already empty.")
        return

    if args.remove_recent:
        since = datetime.now() - timedelta(days=args.recent_days)
        recent_tracks = api.get_recently_played_since(since)
        recent_set = set(recent_tracks)
        playlist_set = set(tracks)
        to_remove = playlist_set.intersection(recent_set)

        print(
            f"Found {len(to_remove)} tracks in the playlist played within the last {args.recent_days} days."
        )

        if len(to_remove) == 0:
            print("No matching tracks to remove.")
            return

        if args.dry_run:
            print("Dry run enabled. No tracks removed.")
            return

        api.remove_tracks_from_playlist(playlist_id, to_remove)
        print(
            f"Removed {len(to_remove)} recently played tracks from playlist {playlist_id}."
        )
        return

    if args.dry_run:
        print("Dry run enabled. No tracks removed.")
        return

    api.clear_playlist_tracks(playlist_id)
    print(f"Cleared {track_count} tracks from playlist {playlist_id}.")


if __name__ == "__main__":
    main()
