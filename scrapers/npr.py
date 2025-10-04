import logging
from datetime import datetime

import requests

from .models import Episode, Track


def get_episode(widget, program_id) -> Episode:
    url = f"https://api.composer.nprstations.org/v1/widget/{widget}/playlist?prog_id={program_id}"
    r = requests.get(url)
    logging.debug(f"Episode track URL: {url}")
    r.raise_for_status()
    data = r.json()
    date_position = []
    for n, episode in enumerate(data["playlist"]):
        episode["date"] = datetime.strptime(episode["date"], "%Y-%m-%d").date()
        date_position.append((episode["date"], n))
    # Get the date and position of the most recent episode
    most_recent_date, most_recent_position = max(date_position, key=lambda x: x[0])
    # Tracks
    tracks = []
    for item in data["playlist"][most_recent_position]["playlist"]:
        t = Track(
            name=item["trackName"],
            artist=item["artistName"],
            album=item.get("collectionName", None),
        )
        tracks.append(t)
    return Episode(
        id=data["playlist"][0]["episode_id"],
        date=most_recent_date,
        tracks=tracks,
    )
# -
