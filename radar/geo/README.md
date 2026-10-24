# Outlines for the overview's globe

`land.json` holds land and country outlines for the workspace overview's globe, thinned to about
half a degree, with coordinates in tenths of a degree (longitude, latitude). They come from
Natural Earth 1:110m, version 4.1.0, by way of the world-atlas package (2.0.2, ISC licence);
Natural Earth is in the public domain (https://www.naturalearthdata.com/). The countries kept
are the corridors on the scan, the UK and Russia.

`scripts/build_app_data.py` copies the file to `app/spec/land.json`, and the manifest lists it
with its SHA-256. The globe places nothing from this file: marks sit on capitals (app/src/page.js,
PLACES), and every figure comes from the run's data.
