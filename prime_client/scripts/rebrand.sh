#!/bin/bash
# Rename the user-visible "Meridian Shards" to "Meridian 59 Prime" in a prepared tree (run by prepare_tree.sh after the patches, so upstream
# merges stay clean). Code comments are left alone; the About box keeps the credit to the Shards client.
TREE="$1"; cd "$TREE" || exit 1
FILES=$(grep -rIl "Meridian Shards\|Meridian 59: Shards" apps --include=*.ts --include=*.tsx --include=*.html --include=package.json | grep -v "node_modules\|/test/\|\.test\.\|/dist/")
for f in $FILES; do sed -i '/^ *\/\/\|^ *\*\|^\/\*/! s/Meridian 59: Shards/Meridian 59 Prime/g; /^ *\/\/\|^ *\*\|^\/\*/! s/Meridian Shards/Meridian 59 Prime/g' "$f"; done
sed -i 's|<p>Meridian 59 Prime client (version {__APP_VERSION__})</p>|<p>Meridian 59 Prime client (version {__APP_VERSION__}), built on Meridian Shards</p>|' apps/client/src/game/ui/AboutDialog.tsx
echo "rebranded $(echo "$FILES" | wc -w) files"
