"""
Spotify API client.
"""

import base64
import json
import logging

import requests
from dotenv import dotenv_values

config = dotenv_values()

auth_base_url = "https://accounts.spotify.com/api"
api_base_url = "https://api.spotify.com/v1"
search_base_url = f"{api_base_url}/search?"


def grouper(lst, n):
    if isinstance(lst, set):
        lst = list(lst)
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class SpotifyAPIConfigException(Exception):
    pass


class Spotify(object):
    def __init__(
        self,
        auth_file=None,
        refresh_token=None,
        client_id=None,
        client_secret=None,
    ):
        if auth_file is not None:
            with open(auth_file) as f:
                credentials = json.load(f)
            for k, v in credentials.items():
                setattr(self, k, v)
        else:
            self.client_id = client_id or config.get("CLIENT_ID")
            self.client_secret = client_secret or config.get("CLIENT_SECRET")
            self.refresh_token = refresh_token or config.get("REFRESH_TOKEN")

        required_config_values = [
            "client_id",
            "client_secret",
            "refresh_token",
        ]
        for attrib in required_config_values:
            v = getattr(self, attrib)
            if v is None:
                raise SpotifyAPIConfigException(
                    f"{attrib} is None. {', '.join(required_config_values)} are required"
                )
        self.access = self._refresh_access_token()
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {self.access['access_token']}"}
        )

    def _refresh_access_token(self):
        url = f"{auth_base_url}/token"
        key = self.client_id + ":" + self.client_secret
        auth = base64.b64encode(key.encode()).decode()
        r = requests.post(
            url,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
        )
        return r.json()

    def search(self, query):
        # Remove punctuation and shorten to 200 characters
        logging.debug(f"Spotify search query: {query}")
        r = self.session.get(
            search_base_url,
            params={"q": query, "type": "track"},
        )
        r.raise_for_status()
        return r.json()

    def get_user_playlist_by_name(self, user, name):
        url = f"{api_base_url}/users/{user}/playlists"

        offset = 0
        page_size = 50
        # To do - iterate when user has more than 50 playlists
        rsp = self.session.get(url, params={"limit": page_size, "offset": offset})
        rsp.raise_for_status()
        data = rsp.json()
        for plist in data["items"]:
            if plist["name"] == name:
                return plist

    def create_user_playlist(self, user, name, public=True):
        payload = {"name": name, "public": public}
        url = f"{api_base_url}/users/{user}/playlists"
        rsp = self.session.post(
            url,
            json=payload,
        )
        rsp.raise_for_status()
        if rsp.status_code == 201:
            data = rsp.json()
            return data["id"]
        else:
            print(rsp.status_code)
            print(rsp.headers)
            raise Exception("Failed creation")

    def get_or_create_playlist(self, user, name, description):
        url = f"{api_base_url}/users/{user}/playlists"

        offset = 0
        page_size = 50
        playlist_id = None
        # To do - iterate when user has more than 50 playlists
        rsp = self.session.get(url, params={"limit": page_size, "offset": offset})
        rsp.raise_for_status()
        data = rsp.json()
        for plist in data["items"]:
            if plist["name"] == name:
                playlist_id = plist["id"]
                return (playlist_id, False)
                break
        offset += page_size
        payload = {"name": name, "description": description, "public": True}
        # create
        if playlist_id is None:
            logging.info(f"Creating playlist {name}.")
            rsp = self.session.post(
                url,
                json=payload,
            )
            rsp.raise_for_status()
            if rsp.status_code == 201:
                data = rsp.json()
                return (data["id"], True)
            else:
                print(rsp.status_code)
                print(rsp.headers)
                raise Exception("Failed creation")
        else:
            raise Exception("Unexpected response.")

    def update_playlist_details(self, playlist_id, details):
        # Update the details
        url = f"{api_base_url}/playlists/{playlist_id}"
        rsp = self.session.put(
            url,
            json=details,
        )
        rsp.raise_for_status()
        if rsp.status_code == 200:
            return True
        else:
            raise Exception(rsp.text)

    def update_playlist_tracks(self, playlist_id, tracks):
        url = f"{api_base_url}/playlists/{playlist_id}/tracks"
        rsp = self.session.put(
            url,
            json={
                "uris": tracks,
            },
        )
        rsp.raise_for_status()
        return rsp.json()

    def get_playlist_tracks(self, playlist_id, limit=50):
        url = f"{api_base_url}/playlists/{playlist_id}/tracks"
        offset = 0
        out = []
        while True:
            params = dict(offset=offset, limit=limit, fields="items(track(id)")
            rsp = self.session.get(url, params=params)
            rsp.raise_for_status()
            items = rsp.json()
            if len(items["items"]) == 0:
                break
            for e in items["items"]:
                out.append(f"spotify:track:{e['track']['id']}")
            offset += limit
        return out

    def clear_playlist_tracks(self, playlist_id, batch_size=75):
        url = f"{api_base_url}/playlists/{playlist_id}/tracks"
        tracks = self.get_playlist_tracks(playlist_id)

        for batch in grouper(tracks, batch_size):
            rsp = self.session.delete(
                url,
                json={
                    "tracks": [{"uri": t} for t in batch],
                },
            )
            rsp.raise_for_status()
        return True

    def add_tracks_to_playlist(self, playlist_id, tracks, batch_size=75):
        url = f"{api_base_url}/playlists/{playlist_id}/tracks"
        for batch in grouper(tracks, batch_size):
            rsp = self.session.post(
                url,
                json={
                    "uris": batch,
                },
            )
            rsp.raise_for_status()
        return True

    def get_show(self, show_id):
        url = f"{api_base_url}/shows/{show_id}"
        rsp = self.session.get(url)
        rsp.raise_for_status()
        return rsp.json()

    def get_state(self):
        url = f"{api_base_url}/me/player"
        rsp = self.session.get(url)
        rsp.raise_for_status()
        if rsp.status_code == 204:
            return False
        else:
            return rsp.json()

    # def get_recently_played(self, type="episode", limit=10):
    #     # Currently doesn't support podcasts
    #     url = f"{api_base_url}/me/player/recently-played"
    #     rsp = self.session.get(url, params={"type": type, "limit": limit})
    #     print(rsp.headers)
    #     rsp.raise_for_status()
    #     return rsp.json()

    def get_queue(self):
        url = f"{api_base_url}/me/player/queue"
        rsp = self.session.get(url)
        rsp.raise_for_status()
        return rsp.json()

    def add_to_queue(self, track_uri, device_id=None):
        url = f"{api_base_url}/me/player/queue"
        d = {"uri": track_uri}
        if device_id is not None:
            d["device_id"] = device_id
        rsp = self.session.post(url, params=d)
        rsp.raise_for_status()
        return True
