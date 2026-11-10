# Install

## What you need
- A Linux machine with Docker and Docker Compose, a DVB tuner (e.g. a Hauppauge dualHD) visible as `/dev/dvb`, and disk
  space for recordings (about 1 GB for 30 minutes of HD, plus about the same again for the MP4 copy).
- Optional: Jellyfin (separate install), a free TMDb API key (artwork in tvhgo).

## Steps
1. `cp .env.example .env` and edit it: folders for the Tvheadend config, the recordings and tvhgo's data, the machine's LAN
   address, and passwords for the two Tvheadend users below. Create those folders and make them owned by uid 1000
   (`sudo chown -R 1000:1000 /srv/tvheadend /srv/recordings /srv/tvhgo`).
2. Build the tvhgo image from <https://github.com/davewins/tvhgo-player> (`docker build -f Dockerfile.player -t tvhgo-player:latest .`).
3. `docker compose up -d tvheadend`, open `http://<LAN address>:9981`, and follow Tvheadend's first-run wizard: create an
   admin user, scan your transmitter's muxes, map the services to channels, and set up the EPG grabber. This is the
   part that is specific to your location and tuner; Tvheadend's own documentation covers it.
4. Create the two users and the DVR profile described in [tvheadend.md](tvheadend.md).
5. `docker compose up -d` to start tvhgo, then open `http://<LAN address>:8097` and log in with a tvhgo user (created in
   tvhgo's Settings, not the Tvheadend one).
6. Set up the pipeline: [pipeline.md](pipeline.md). Until you do, recordings are still made and tvhgo plays them (it
   converts on demand), but Jellyfin gets nothing.
7. Point a Jellyfin "Shows" library at `<recordings>/_jellyfin` ([jellyfin.md](jellyfin.md)).

## Updating
`docker compose pull tvheadend && docker compose up -d tvheadend`. For tvhgo and the pipeline, rebuild the image and
`docker compose up -d`. Back up `TVH_CONFIG_DIR` first ([recovery.md](recovery.md)).
