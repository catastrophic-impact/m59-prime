#!/usr/bin/env python3
"""Give the Shards (web) client the string table of OUR server build: copies build/server/rsc0000.rsb into the client's assets folder and updates manifest.json.
Run after every scripts/build.sh. Then hard-reload the browser page (Ctrl+Shift+R)."""
import hashlib, json, os, shutil
work = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
src = os.path.join(work, "build/server/rsc0000.rsb"); assets = os.path.join(work, "assets")
orig = os.path.join(assets, "rsc0000.rsb.shards-original")
if not os.path.exists(orig): shutil.copy(os.path.join(assets, "rsc0000.rsb"), orig)
shutil.copy(src, os.path.join(assets, "rsc0000.rsb"))
b = open(src, "rb").read(); h = hashlib.sha1(b).hexdigest()[:16]
mp = os.path.join(assets, "manifest.json"); m = json.load(open(mp))
m["rsbHash"] = h; m["files"]["rsc0000.rsb"].update(size=len(b), hash=h); json.dump(m, open(mp, "w"))
print("client strings synced, rsbHash", h)
