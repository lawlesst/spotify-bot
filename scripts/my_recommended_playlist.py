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

config = dotenv_values()

cwd = Path(__file__).parent
parent_cwd = cwd.parent
sys.path.append(str(parent_cwd))
from harvest_public_radio_playlist import handlers

# Add client to path.
from spotify.client import Spotify

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
    parser = argparse.ArgumentParser(description="Create recommendations.")
    parser.add_argument(
        "--username",
        required=True,
        help="Spotify username to create recommendations for.",
    )
    parser.add_argument(
        "--seed-from",
        required=True,
        help="Playlist ID to seed recommendations from. Defaults to On Repeat",
    )
    parser.add_argument(
        "--recommended-playlist-name",
        required=False,
        default="My Recommended Playlist",
        help="Name for the recommended playlist.",
    )
    parser.add_argument(
        "--num-recommendations",
        required=False,
        default=50,
        type=int,
        help="Number of recommendations to generate.",
    )
    parser.add_argument(
        "--dry-run",
        required=False,
        help="Dry run. Will harvest playlist but not upload to Spotify.",
        action="store_true",
    )
    parser.add_argument(
        "--max-artist-popularity",
        default=50,
        type=int,
        help="Maximum popularity for seed artists from top artists.",
    )
    parser.add_argument(
        "--max-popularity",
        default=75,
        type=int,
        help="Maximum popularity for recommendations.",
    )
    args = parser.parse_args()

    api = Spotify(auth_file=auth_file)

    logger.info(
        f"Seeding recommendations for {args.username} from playlist {args.seed_from}."
    )
    # Get tracks from the seed playlist
    tracks = api.get_playlist_tracks(args.seed_from)
    track_ids = [track.replace("spotify:track:", "") for track in tracks]

    # Get saved tracks - we will only use tracks that are saved.
    saved_tracks = api.get_saved_tracks(track_ids)
    for_recommendations = []
    for track, is_saved in saved_tracks.items():
        if is_saved is True:
            for_recommendations.append(track)

    # Recent top tracks
    logger.info(f"Getting recent top tracks for {args.username}.")
    recent_top_tracks = api.get_top_tracks(max=300)
    logger.info(f"Recent top tracks: {len(recent_top_tracks)}")
    # Recently played tracks
    logger.info(f"Getting recently played tracks for {args.username}.")
    recently_played = api.get_recently_played()
    logger.info(f"Recently played tracks: {len(recently_played)}")

    # Top artists with lower popularity
    top_artists = []
    top = api.get_top_items("artists", time_range="long_term", limit=5)
    for artist in top["items"]:
        if artist["popularity"] < args.max_artist_popularity:
            top_artists.append(artist["id"])
            logger.info(
                f"Adding {artist['name']} to seed artists with popularity {artist['popularity']}."
            )

    # Cut off since only 5 can be used for recommendations
    for_recommendations = for_recommendations[:3]
    top_artists = for_recommendations[:2]

    logger.info(
        f"Using {len(for_recommendations)} tracks and {len(top_artists)} artists to generate {args.num_recommendations} recommendations."
    )
    rsp = api.get_recommendations(
        seed_tracks=for_recommendations,
        limit=100,  # request more to filter out songs in top tracks or recently played
        max_popularity=args.max_popularity,
        seed_artists=top_artists,
    )
    to_add = []
    for rec_track in rsp["tracks"]:
        t_id = rec_track["id"]
        t_uri = rec_track["uri"]
        if t_uri in recently_played:
            logger.info(f"Skipping {t_uri} as it is in recently played.")
        elif t_uri in recent_top_tracks:
            logger.info(f"Skipping {t_uri} as it is in recent top tracks.")
        elif saved_tracks.get(t_id, False) is True:
            logger.info(f"Skipping {t_uri} as it is a saved track.")
        else:
            to_add.append(t_uri)

        if len(to_add) >= args.num_recommendations:
            break

    recommended_playlist_name = args.recommended_playlist_name

    recommended_playlist_id, created = api.get_or_create_playlist(
        args.username, recommended_playlist_name, "Custom recommendations."
    )
    if created is True:
        logger.info(f"Created playlist {recommended_playlist_id}.")
    else:
        logger.info(f"Found playlist {recommended_playlist_id}.")

    existing_tracks = api.get_playlist_tracks(recommended_playlist_id)

    already_in_playlist = set(to_add) & set(existing_tracks)
    logger.info(f"Already in playlist: {len(already_in_playlist)}")

    to_remove = set(existing_tracks) - set(to_add)
    # Cap at 50
    to_add = set(to_add) - set(existing_tracks)

    if args.dry_run:
        logger.info("Dry run. Exiting.")
        logger.info(
            f"Tracks to remove: {len(to_remove)}. Tracks to add: {len(to_add)}."
        )
        return
    else:
        if len(to_remove) > 0:
            logger.info(f"Removing {len(to_remove)} tracks from combined playlist.")
            _ = api.remove_tracks_from_playlist(recommended_playlist_id, to_remove)

        if len(to_add) > 0:
            logger.info(f"Adding {len(to_add)} tracks to combined playlist.")
            _ = api.add_tracks_to_playlist(recommended_playlist_id, to_add)

        if (len(to_remove) > 0) or (len(to_add) > 0):
            formatted_date = date.today().strftime("%Y-%m-%d")
            details = {
                "description": f"Custom recommendations via API. Last updated {formatted_date}.",
                "name": recommended_playlist_name,
            }
            _ = api.update_playlist_details(recommended_playlist_id, details)


if __name__ == "__main__":
    logger = logging.getLogger()
    main()
# -
