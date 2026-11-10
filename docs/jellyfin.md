# Jellyfin

Jellyfin is installed separately (it is not in `docker-compose.yml`).

## Library
Add a library of type **Shows**, folder `<recordings>/_jellyfin` (inside the Jellyfin container this is wherever you
mounted it). The pipeline's `.nfo` files give each programme folder a show and each recording an episode (the season is
the year, episodes are numbered per year), so no scraper is needed. Turn on *Prefer embedded titles* / use the NFO
metadata reader; online metadata fetchers add TMDb artwork where the title matches.

## Skipping adverts and intros (Intro Skipper plugin)
The pipeline writes chapters named **Commercial** into each MP4. The [Intro Skipper](https://github.com/intro-skipper/intro-skipper)
plugin (version 12.x was used) turns chapters named Commercial, Ad, Advert or Intermission into Jellyfin *media
segments*, which clients show as a Skip button. Things that matter:

1. **Maximum commercial duration.** Plugin settings (Dashboard → Plugins → Intro Skipper) → raise *maximum commercial
   duration* from the default **120 seconds** to **600**. UK ad breaks are 2 to 5 minutes; breaks longer than the
   maximum are ignored, which looks like "chapters but no Skip button".
2. **Re-analysis.** After changing a file's chapters or the plugin's settings, Jellyfin only re-checks items it
   considers changed. Updating the file's modified time (`touch file.mp4`, as the user that owns it) makes the plugin
   analyse it within about ten minutes. The daily scheduled task "Detect and Analyze Media Segments" does the rest.
3. **Player setting.** Each user/app has a playback option for what to do with each segment type. If Commercial is
   "Skip automatically" the app may silently do nothing; set it to **Ask to skip**.
4. **Intros** are found by comparing the audio of two or more episodes in the same season folder (the year here), so a
   programme needs a few recordings first, and the intro must be at least the plugin's *minimum intro duration*
   (15 s by default).
5. **Client support varies** (tested): the Android Jellyfin app shows the Skip popup; Wholphin (Android TV) shows it
   sometimes and is reachable with a Down press; the iPhone app and the web client did not show a Skip button for
   commercials but do show the chapters. tvhgo's own player has its own **Skip ad break** button that works everywhere
   because it reads the chapters itself.

The plugin's data lives under Jellyfin's `config/data/data/` (note the doubled `data`); the plugin itself under
`config/data/plugins/`.

## Series images (optional)
With `series_images = true` the pipeline gives a programme with no picture one of its own episode thumbnails (after it
has waited an hour for the online fetchers). It needs a Jellyfin API key (Dashboard → API Keys) in
`JELLYFIN_API_KEY`, and `url`, `library_id` and `user_id` in the `[jellyfin]` section of `config.toml`.
