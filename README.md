# Spotify playlist

Utility for creating Spotify playlists via the [Spotify API](https://developer.spotify.com/documentation/web-api).

## Install/setup

This project using [poetry](https://python-poetry.org/) to manage dependencies. Run `poetry install` to install dependencies.

If you aren't a poetry user, the only dependencies are `requests` and `python-dotenv`.

## Authentication and Authorization

Setting up authentication for the Spotify is tricky, like a lot of APIs. For command line utilities, I recommend following [Ben Wiz's guide](https://benwiz.com/blog/create-spotify-refresh-token/). To assist with this, there is an `authorization.py` script to obtain the necessary credentials and save them to a `.spotify-auth.json` file in the current working directory.

Before running this, set the following environment variables by creating a `.env` file with these contents.

```
SPOTIFY_USER_ID=xx
CLIENT_ID=xxx
CLIENT_SECRET=xxx
```

Optionally, add `http://lawlesst.github.io/tools/auth-redirect.html` as a redirect URI when configuring your API key. This will make it a little easier to read the code and not require you to create your own redirect page. If you don't want to use this, just update the `redirect_uri` variable in `authorization.py`. 

To obtain credentials, run `python authorization.py code`. This will open a web browser where you can authenticate with Spotify, if not already, and then be redirected to a web page where you can copy the URL parameter CODE. 

Then run `python authorization.py refresh-token --code <value from the code URL parameter above>`. This will obtain the necessary credentials and save them to a file called `.spotify-auth.json` in the current working directory. These can be passed the to included client library for authenticating with the API. 


## Example usage

In `scripts/harvest_public_radio_playist.py`, playlists from several public radio music programs are harvested and Spotify playlists created or updated from the program tracks. Each new episode overwrites the existing playlist.