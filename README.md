# Spotify bot

A personal bot leveraging the [Spotify API](https://developer.spotify.com/documentation/web-api) for creating Spotify playlists and managing a listening queue.

Utilities:

* [Harvest public radio episodes](./scripts/harvest_public_radio_playlist.py) and create Spotify playlists. See this [blog post for an overview](https://lawlesst.github.io/notebook/spotify-playlists.html).
* [Add the NPR hourly news update](./scripts/add_show_to_queue.py) to your listening queue. This can be scheduled to run throughout the day.
* ~~[Create a playlist from custom recommendations](./scripts/my_recommended_playlist.py). This uses the Spotify API recommendations endpoint and custom logic based on top tracks and artists.~~ Spotify deprecated the recommendations endpoint :(.
* Download/archive your liked songs
* Generate [new playlists using the Google Gemini API](./scripts/gemini_recs.py)

More details follow for anyone attempting to reuse this code.

## Install/setup

This project using [uv](https://docs.astral.sh/uv/) to manage dependencies. Run `uv sync` to install dependencies.

For the scripts that use Gemini to generate recommendations, you will want to run `uv sync --group gemini`. 

## Authentication and Authorization

Setting up authentication for the Spotify is tricky, like a lot of APIs. For command line utilities, I recommend following [Ben Wiz's guide](https://benwiz.com/blog/create-spotify-refresh-token/). To assist with this, there is an `authorization.py` script to obtain the necessary credentials and save them to a `.spotify-auth.json` file in the current working directory.

Before running this, set the following environment variables by creating a `.env` file with these contents.

```
SPOTIFY_USER_ID=xx
CLIENT_ID=xxx
CLIENT_SECRET=xxx
GEMINI_API_KEY=xxx # optional
```

Optionally, add `http://lawlesst.github.io/tools/auth-redirect.html` as a redirect URI when configuring your API key. This will make it a little easier to read the code and not require you to create your own redirect page. If you don't want to use this, just update the `redirect_uri` variable in `authorization.py`. 

To obtain credentials, run `python authorization.py code`. This will open a web browser where you can authenticate with Spotify, if not already, and then be redirected to a web page where you can copy the URL parameter CODE. 

Then run `python authorization.py refresh-token --code <value from the code URL parameter above>`. This will obtain the necessary credentials and save them to a file called `.spotify-auth.json` in the current working directory. These can be passed the to included client library for authenticating with the API. 
