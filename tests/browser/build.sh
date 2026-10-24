#!/bin/sh
# Build a local copy of the workspace page with the mock capabilities (mock.js), for the browser
# flows in this folder. The page is wrapped in the skeleton the platform adds at publish time.
set -e
H=$(cd "$(dirname "$0")" && pwd)
APP="$H/../../app"
rm -rf "$H/dev" && mkdir -p "$H/dev"
python3 "$H/wrap.py" "$APP/index.html" "$H/dev"
cp "$H/mock.js" "$H/dev/mock.js"
cp -r "$APP/data" "$H/dev/data"
cp -r "$APP/spec" "$H/dev/spec"
