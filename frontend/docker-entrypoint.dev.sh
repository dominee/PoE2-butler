#!/bin/sh
# Bind mount to /app and a separate volume for /app/node_modules mean rebuilds
# can leave node_modules out of date when package-lock.json changes. Resync
# from the host lock when the lock hash in the volume does not match.
set -e
MARK=node_modules/.poe2b_lock_md5
# Guard against partially-corrupted installs inside the mounted node_modules
# volume. This exact path is required by @babel/types during Vite transforms.
REQUIRED_BABEL_FILE=node_modules/@babel/types/lib/builders/generated/index.js
H=""
O=""
[ -f package-lock.json ] && H=$(md5sum package-lock.json | cut -d" " -f1)
[ -f "$MARK" ] && O=$(tr -d " \t\r\n" < "$MARK")
if [ -n "$H" ] \
  && [ -n "$O" ] \
  && [ "$H" = "$O" ] \
  && [ -d node_modules/.bin ] \
  && [ -f "$REQUIRED_BABEL_FILE" ]; then
  exec "$@"
fi
if [ -f package-lock.json ]; then
  echo "poe2b-frontend: syncing node_modules to package-lock.json (npm ci)..."
  npm ci
else
  echo "poe2b-frontend: no package-lock.json, running npm install..."
  npm install
fi
mkdir -p node_modules
[ -n "$H" ] && echo "$H" > "$MARK"
exec "$@"
