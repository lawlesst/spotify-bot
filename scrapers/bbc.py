import logging
from datetime import datetime

import bs4
import requests

from .models import Episode, Track


class BBCScraper:
    def __init__(self, show_url):
        self.show_url = show_url

    def _get_latest_episode_url(self):
        rsp = requests.get(self.show_url)
        rsp.raise_for_status()
        soup = bs4.BeautifulSoup(rsp.text, "html.parser")
        latest_episode = soup.find_all("h2", class_="programme__titles")[0]
        episode_url = latest_episode.find("a")["href"]
        return episode_url

    def get_latest_episode(self) -> Episode:
        episode_url = self._get_latest_episode_url()
        logging.info(f"Latest episode URL: {episode_url}")

        rsp = requests.get(episode_url)
        rsp.raise_for_status()
        soup = bs4.BeautifulSoup(rsp.text, "html.parser")
        # Tracks
        items = soup.find_all("li", class_="segments-list__item--music")
        out = {}
        tracks = []
        for item in items:
            details = item.find("div", class_="segment__track")
            artist = details.find("h3")
            track = details.find("p")
            album = track.find_next("em")
            d = dict(artist=artist.text.strip(),
                    name=track.text.strip(),
                    album=album.text.strip().strip(".") if album else None,
                )
            tracks.append(d)
        broadcast_date = soup.find("div", class_="broadcast-event__time")
        out["tracks"] = tracks
        # format 21 Sep 2025
        bdate = datetime.strptime(broadcast_date.attrs["title"].strip(), "%d %b %Y")
        e = Episode(date=bdate, tracks=[Track(**t) for t in tracks])
        return e




