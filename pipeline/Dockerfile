# tvh-pipeline: Comskip + ffmpeg + the Python application. Build: docker build -t tvh-pipeline pipeline/
FROM ubuntu:24.04
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq comskip ffmpeg python3 >/dev/null \
    && rm -rf /var/lib/apt/lists/*
COPY comskip.ini /etc/tvh-pipeline/comskip.ini
COPY tvhpipeline /opt/tvh-pipeline/tvhpipeline
COPY tests /opt/tvh-pipeline/tests
ENV PYTHONPATH=/opt/tvh-pipeline PYTHONUNBUFFERED=1
# uid 1000 is the user the recordings are owned by in the usual Tvheadend container setup
RUN mkdir -p /var/lib/tvh-pipeline && chown 1000:1000 /var/lib/tvh-pipeline
VOLUME /var/lib/tvh-pipeline
USER 1000:1000
HEALTHCHECK --interval=2m --timeout=10s --start-period=3m \
  CMD python3 -c "import os,sys,time; p='/var/lib/tvh-pipeline/heartbeat'; sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p) < 900 else 1)"
ENTRYPOINT ["python3", "-m", "tvhpipeline"]
CMD ["run"]
