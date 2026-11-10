# tvhgo (the web interface)

[tvhgo](https://github.com/davidborzek/tvhgo) is a small web interface for Tvheadend, written in Go with a React UI. This
stack uses a fork, [davewins/tvhgo-player](https://github.com/davewins/tvhgo-player), that adds playback and a number of
features aimed at a UK Freeview setup. The fork's own README covers building it; this page covers how it fits in.

## What the fork adds
- **Live TV in the browser**, including iPhone/iPad (HLS for Apple's WebKit, fragmented MP4 elsewhere), a quality
  choice, and radio with a proper player.
- **Recordings** shown as a grid of shows (latest episode as the picture) or as a list, sortable, with download as MP4,
  play straight from the thumbnail, and a Delete/Download choice on selection.
- **Series recording**: "Record series" on a programme, a Series rules page, and rules that match the broadcaster's
  "New:" / "Final:" tagged titles. A series rule is for one title on one channel and skips repeats.
- **Artwork** from TMDb (optional key) for programmes, search results and recordings that have no picture of their own.
- **Guide**: UK dates and 12-hour times, the time of day carried when you change day, a "Now" button, related
  programmes as cards, and quick channel groups (HD, +1, News, Kids, Shopping, Radio) worked out from channel numbers
  and names.
- **Skip ad break** button in the player, using the advert chapters the pipeline writes into the MP4.
- **Tuner warnings** (optional): a header badge showing how many tuners are in use, a banner and a clear message when
  every tuner is busy and a channel is on another multiplex, and warnings about scheduled recordings that need more
  multiplexes than there are tuners (on the Upcoming list and on a programme's page before you record it).
- **Background progress** (optional): what the pipeline is converting, as a badge, as a chip on each recording, and in
  the player. See [pipeline.md](pipeline.md#progress-and-status).

## GPU live encoding
Live TV is transcoded for the browser. On the CPU that costs roughly 0.25 of a core per SD stream and 0.7 per HD stream;
on an Intel iGPU (VAAPI) three simultaneous 720p streams took about 0.9 of a core in total instead of 4.8, with similar
quality. Set `TVHGO_LIVE_ENCODER=vaapi` in `.env`, uncomment the `devices:` and `group_add:` lines for tvhgo in
`docker-compose.yml` (the group id is `getent group render`), and rebuild the tvhgo image so it includes the Intel media
driver. tvhgo tests the GPU on first use and falls back to the CPU by itself if it does not work. Recording
conversion in the pipeline stays on the CPU on purpose (better quality per megabyte for the files you keep). Details:
the [fork's player docs](https://github.com/davewins/tvhgo-player/blob/main/docs/player.md#gpu-live-encoding-optional).

## How recordings are played
tvhgo plays the MP4 the pipeline made in `recordings/_jellyfin/` when there is one. If there is not (a recording just
finished, or you have no pipeline), it converts on demand into its own cache (`TVHGO_PLAYBACK_CACHE_DIR`, capped by
`TVHGO_PLAYBACK_CACHE_MAX_GB`), one at a time (`TVHGO_PLAYBACK_MAX_JOBS`). If the pipeline is already converting that
recording, tvhgo shows its progress instead of starting a second conversion.

## Settings that matter (compose environment)
| Variable | Meaning |
| --- | --- |
| `TVHGO_TVHEADEND_*` | Where Tvheadend is and the (non-admin) account tvhgo uses |
| `TVHGO_TVHEADEND_STATUS_USERNAME` / `_PASSWORD` | Optional admin-level account used only for the tuner features; empty switches them off ([tvheadend.md](tvheadend.md)) |
| `TVHGO_PLAYBACK_SOURCE_DIR` | The pipeline's library, `/recordings/_jellyfin` |
| `TVHGO_PLAYBACK_PIPELINE_STATUS` | Path of the pipeline's `status.json` (the state volume mounted read-only) |
| `TVHGO_PLAYBACK_TMDB_API_KEY`, `_TMDB_LANGUAGE` | Artwork from TMDb; empty key = no artwork lookup |
| `TVHGO_PLAYBACK_LIVE_*` | Live transcoding: on/off, quality list, maximum simultaneous streams, and `LIVE_ENCODER` (`cpu` or `vaapi`) |

## Security notes
- tvhgo has its own users (created in its Settings) and its own sessions; give Tvheadend's `tvhgo` account only the
  permissions in [tvheadend.md](tvheadend.md).
- Listen on your LAN address, or put a reverse proxy with TLS in front before exposing it to the internet.
- The tuner account is admin-level in Tvheadend because Tvheadend offers no read-only admin. tvhgo only makes read calls
  with it, but treat its password as an admin password.
