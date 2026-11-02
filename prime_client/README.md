# prime_client: our client = the Meridian Shards web client + our patches

Same idea as prime_server: nothing upstream is edited by hand. The tree is rebuilt from
1. `UPSTREAM.txt`  the pinned upstream (jboullion/meridian-shards, GPL v2);
2. `patches/*.patch`  small numbered diffs against upstream (hooks);
3. `overlay/`  our own new files (copied over the tree);
4. `../prime_server/config/blakserv.cfg`  (the client reads the SecretKey from it) and links to the game assets.

Big files live outside the project in `$PRIME_WORK` (default `~/boxes/m59-box/src/prime_work`): `node/` (portable Node 24), `client_cache/`, `client_build/`, `assets/` (the 104 game files, extracted from the Shards release).

```
scripts/fetch_upstream.sh [path-or-url]   clone/checkout the pinned commit
scripts/prepare_tree.sh                   upstream + patches + overlay -> $PRIME_WORK/client_build/tree (npm install)
scripts/run_dev.sh                        syncs the server's string table, starts gateway (ws 8059 -> server 5960) + vite: http://127.0.0.1:5173
scripts/stop_dev.sh
```
After every server build run `run_dev.sh` again (it syncs the string table: the client must use OUR server's rsc0000.rsb).

## Our changes so far
- 0001-npc-name-tags: the wandering townsfolk (client-only crowd) get a name tag in a teal colour no real player/monster uses (overlay: primeNpcTags.ts).
