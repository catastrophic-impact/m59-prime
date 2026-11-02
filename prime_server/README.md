# prime_server: how our custom server sits on top of the upstream code

Nothing in the upstream source is edited by hand. The server tree is always **rebuilt** from:

1. `UPSTREAM.txt`: the pinned upstream (Server 104 code via the Meridian Shards fork).
2. `patches/*.patch`: small, numbered unified diffs against upstream (build fixes, and later one-line *hooks*).
3. `overlay/`: our own files, copied over the tree (new Blakod classes, spells, skills, monsters, bots; later the class system).
4. `scripts/linux_fixups.py`: Linux-only repairs (case-sensitive `.lkod` includes, an apostrophe in a file name).

Updating upstream = change the commit in `UPSTREAM.txt`, run `scripts/prepare_tree.sh`: a patch that no longer applies shows exactly which hook has to be re-pointed.

Big files live outside the project, in `$PRIME_WORK` (default `~/boxes/m59-box/src/prime_work`): the cloned upstream (`cache/`) and the build output (`build/`).

```
scripts/fetch_upstream.sh      clone/checkout the pinned commit
scripts/prepare_tree.sh        upstream + patches + overlay -> $PRIME_WORK/build/tree
scripts/build.sh [--fresh]     64-bit build (compiler, kod x2, server, rsc) -> $PRIME_WORK/build/server
config/blakserv.cfg            ports 5960/9999, SecretKey prime-secret, a placeholder (the client sends the same; `m59primesetup.sh` makes a random key for every new install)
```

## Rules for our code (the "notepad theme" idea)
- New things (classes, spells, skills, monsters, bots) are **new files** in `overlay/kod/object/prime/...`; they need no patch except one makefile line and one registration hook.
- A change to an existing upstream method is a **hook**: one marked line (`% PRIME-HOOK`) that calls into our overlay code, in a patch file. The logic lives in the overlay, not in the patched file.
- Never edit `$PRIME_WORK/build/tree` as the source of truth: change `patches/` or `overlay/` and rebuild.

## The Shards client against our server (spike, 2026-10-21)
Their client needs the string table of OUR server build: after every `scripts/build.sh`, copy `build/server/rsc0000.rsb` over `assets/rsc0000.rsb` in the assets folder and update `rsbHash` (sha1, first 16 hex chars) and the file's size/hash in `assets/manifest.json` (done by scripts/sync_client_strings.py).
