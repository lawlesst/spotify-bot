import base64
import json
import logging

import requests
from dotenv import dotenv_values

config = dotenv_values()

auth_base_url = "https://accounts.spotify.com/api"
api_base_url = "https://api.spotify.com/v1"
search_base_url = f"{api_base_url}/search?"


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
                # self.__dict__[k] = v
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
        rsp = self.session.get(
            url, params={"limit": page_size, "offset": offset}
        )
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
        rsp = self.session.get(
            url, params={"limit": page_size, "offset": offset}
        )
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
