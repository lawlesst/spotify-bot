from google import genai
import os
from pathlib import Path
from textwrap import dedent

from pydantic import BaseModel, Field
from typing import Optional
import click
import random
from dotenv import dotenv_values

import re

from spotify.client import Spotify

config = dotenv_values()

parent_cwd = Path(__file__).parent.parent
auth_file = parent_cwd.joinpath(".spotify-auth.json")
data_dir = Path(__file__).parent.joinpath("data")

data_dir.mkdir(exist_ok=True, parents=True)

def clean_search_term(term):
    # Remove punctuation and limit to 200 characters
    return re.sub(r"[^\w\s]", "", term)[:200]

class Track(BaseModel):
    name: str = Field(description="The name of the track.")
    artist: str = Field(description="A string of artists who performed the track.")
    album: Optional[str] = Field(description="The album the track belongs to.")
    year: Optional[int] = Field(description="The release year of the track.")

gemini_api_key = config.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=gemini_api_key)


@click.command()
@click.option("--username", "-u", default=os.getenv("SPOTIFY_USER_ID"), help="Spotify username.")
@click.option("--playlist", "-p", required=True, help="Playlist name.")
@click.option("--limit", "-l", default=25, help="Number of tracks to analyze.")
def main(username, playlist, limit):

    spot = Spotify(auth_file=auth_file)
    if playlist == "liked":
        liked_songs = spot.get_all_saved_tracks(max_tracks=100)
        playlist_track_ids = [track["id"] for track in liked_songs]
    else:
        playlist = spot.get_user_playlist_by_name(user=username, name=playlist)
        if not playlist:
            print(f"Playlist {playlist} not found for user {username}.")
            return
        playlist_id = playlist["id"]
        print(f"Found playlist {playlist['name']} with ID {playlist_id}.")
        playlist_track_ids = spot.get_playlist_tracks(playlist_id)
    
    print(f"Playlist has {len(playlist_track_ids)} tracks.")
    track_details = spot.get_track_info(playlist_track_ids)

    these_tracks = []
    if len(playlist_track_ids) >= limit:
        random.shuffle(track_details)
    for track in track_details:
        #print(track)
        these_tracks.append(f"{track['name']} by {', '.join([artist['name'] for artist in track['artists']])} {track['album']['release_date'][:4]}")
        if len(these_tracks) >= limit:
            break

    prompt = dedent(f"""
Context: You are a musicologist and cultural analysis. 
Task: Write a summary of the mood and themes present in this collection of songs. Make it terse but insightful. Clarity is paramount.
Songs:
{chr(10).join([f'- {track}' for track in these_tracks])}
""")
    print(f"Prompt:\n{prompt}")
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
    )

    print("\n" + "="*60)
    print("Mood Analysis:")
    print("="*60)
    print(response.text)
    print("="*60)


if __name__ == "__main__":
    main()