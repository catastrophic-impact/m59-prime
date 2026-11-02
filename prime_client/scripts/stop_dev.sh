#!/bin/bash
# Stop the dev gateway and vite started by run_dev.sh. They are found by command line (not by working directory: a process started from another
# session shows an empty cwd inside the box, which is why Stop used to leave the web client running).
for p in $(pgrep -f "node.*(tools/gateway/gateway.ts|client_build/tree/node_modules/.bin/vite|shards-client.*vite)"); do
  kill $p && echo "stopped $p"
done
