"""
Export liked songs from Spotify.
"""

import json
from pathlib import Path

from spotify.client import Spotify
from spotify.utils import get_auth_file

auth_file = get_auth_file()

def main():
    api = Spotify(auth_file=auth_file)
    
    print("Fetching your liked songs...")
    liked_songs = api.get_all_saved_tracks()
    
    print(f"Found {len(liked_songs)} liked songs")
    
    # Extract track information
    tracks_info = []
    for track in liked_songs:
        track_info = {
            "id": track["id"],
            "name": track["name"],
            "artists": [artist["name"] for artist in track["artists"]],
            "album": track["album"]["name"],
            "release_date": track["album"]["release_date"],
            "popularity": track["popularity"],
            "uri": track["uri"]
        }
        tracks_info.append(track_info)
    
    # Save to JSON file
    output_file = Path("data/liked_songs.json")
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(tracks_info, f, indent=2)
    
    print(f"Liked songs exported to {output_file}")
    
    # Print first 5 tracks as example
    print("\nFirst 5 liked songs:")
    for i, track in enumerate(tracks_info[:5]):
        artists = ", ".join(track["artists"])
        print(f"{i+1}. {track['name']} by {artists}")

if __name__ == "__main__":
    main()