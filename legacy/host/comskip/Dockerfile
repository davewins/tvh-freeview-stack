# Comskip + ffmpeg: finds the advert breaks in a recording and writes them into the MP4 as "Commercial" chapters.
# Run by scripts/tvh-comskip-sync.py (cron). Build: docker build -t tvh-comskip:1 scripts/comskip
FROM ubuntu:24.04
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq comskip ffmpeg python3 >/dev/null \
    && rm -rf /var/lib/apt/lists/*
COPY comskip.ini /etc/tvh-comskip.ini
COPY chapters.py /usr/local/bin/tvh-comskip-chapters.py
COPY apply.sh /usr/local/bin/tvh-comskip-apply
RUN chmod 755 /usr/local/bin/tvh-comskip-apply
