# Config snapshot

`dvr-config.json` is the DVR profile this stack runs with, as a worked example (file name format, padding, retention,
the empty post-processor command once the pipeline container is in use).

`export-config.sh` writes more files into this folder (channels, series rules, access entries with their allowed
networks). They describe *your* setup, so they are git-ignored: review them, keep them somewhere private, and do not
commit them to a public repository.
