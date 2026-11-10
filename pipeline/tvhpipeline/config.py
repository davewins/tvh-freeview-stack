"""Configuration: a TOML file with defaults, plus environment variables for credentials and the Tvheadend address."""
import os
import tomllib
from dataclasses import dataclass, field

DEFAULT_PATH = "/etc/tvh-pipeline/config.toml"


@dataclass
class Config:
    tvh_url: str = "http://127.0.0.1:9981"
    tvh_user: str = ""
    tvh_pass: str = ""
    # the folder as Tvheadend names it in its API (its own mount of the recordings), and where this container sees it
    tvheadend_root: str = "/recordings"
    recordings: str = "/recordings"
    library: str = "/recordings/_jellyfin"
    state_dir: str = "/var/lib/tvh-pipeline"
    poll_seconds: int = 60
    settle_seconds: int = 120          # a recording must have been untouched this long before it is processed
    max_attempts: int = 5
    # steps
    strip_audio_description: bool = True
    convert_mp4: bool = True
    thumbnail: bool = True
    nfo: bool = True
    comskip: bool = True
    cleanup: bool = True
    series_images: bool = False
    # comskip
    comskip_skip_channels: str = r"^\s*BBC\b"   # channels without adverts
    comskip_since: float = 0.0                  # only recordings that finished after this time (epoch seconds)
    comskip_ini: str = "/etc/tvh-pipeline/comskip.ini"
    # jellyfin (series_images only)
    jellyfin_url: str = ""
    jellyfin_library_id: str = ""
    jellyfin_user_id: str = ""
    jellyfin_api_key: str = ""
    jellyfin_path_prefix: str = ""      # path prefix Jellyfin uses for the library ...
    host_path_prefix: str = ""          # ... and the same place as this container sees it
    extra: dict = field(default_factory=dict)


def load(path: str | None = None) -> Config:
    path = path or os.environ.get("TVH_PIPELINE_CONFIG", DEFAULT_PATH)
    raw = {}
    if os.path.exists(path):
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    c = Config()
    tvh, paths, run, steps = raw.get("tvheadend", {}), raw.get("paths", {}), raw.get("run", {}), raw.get("steps", {})
    cs, jf = raw.get("comskip", {}), raw.get("jellyfin", {})
    c.tvh_url = os.environ.get("TVH_URL", tvh.get("url", c.tvh_url)).rstrip("/")
    c.tvh_user = os.environ.get("TVH_USER", tvh.get("username", ""))
    c.tvh_pass = os.environ.get("TVH_PASS", tvh.get("password", ""))
    c.tvheadend_root = paths.get("tvheadend_root", c.tvheadend_root).rstrip("/")
    c.recordings = paths.get("recordings", c.recordings).rstrip("/")
    c.library = paths.get("library", c.library).rstrip("/")
    c.state_dir = paths.get("state_dir", c.state_dir)
    c.poll_seconds = int(run.get("poll_seconds", c.poll_seconds))
    c.settle_seconds = int(run.get("settle_seconds", c.settle_seconds))
    c.max_attempts = int(run.get("max_attempts", c.max_attempts))
    for k in ("strip_audio_description", "convert_mp4", "thumbnail", "nfo", "comskip", "cleanup", "series_images"):
        setattr(c, k, bool(steps.get(k, getattr(c, k))))
    c.comskip_skip_channels = cs.get("skip_channels_regex", c.comskip_skip_channels)
    c.comskip_since = float(cs.get("since_epoch", c.comskip_since))
    c.comskip_ini = cs.get("ini", c.comskip_ini)
    c.jellyfin_url = os.environ.get("JELLYFIN_URL", jf.get("url", "")).rstrip("/")
    c.jellyfin_library_id = jf.get("library_id", "")
    c.jellyfin_user_id = jf.get("user_id", "")
    c.jellyfin_api_key = os.environ.get("JELLYFIN_API_KEY", jf.get("api_key", ""))
    c.jellyfin_path_prefix = jf.get("path_prefix", "")
    c.host_path_prefix = jf.get("host_path_prefix", "")
    return c
