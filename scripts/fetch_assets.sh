#!/usr/bin/env bash
# Download the assets that light_speed.blend links from assets/.
#
# Run from anywhere:
#
#     scripts/fetch_assets.sh
#
# Files that are already present with the right size are skipped.
set -euo pipefail

ASSETS="$(cd "$(dirname "$0")/.." && pwd)/assets"
mkdir -p "$ASSETS"

# name  size_in_bytes  url
FILES=(
  "milkyway_2020_8k.exr 137307727 https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/milkyway_2020_8k.exr"
  "hygdata_v41.csv 33932548 https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/CURRENT/hygdata_v41.csv"
  "world.200412.3x5400x2700.jpg 1878742 https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74218/world.200412.3x5400x2700.jpg"
  "lroc_color_poles_4k.tif 13095388 https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_4k.tif"
  "PIA07782.jpg 441285 https://assets.science.nasa.gov/content/dam/science/psd/photojournal/pia/pia07/pia07782/PIA07782.jpg"
)

for entry in "${FILES[@]}"; do
  read -r name size url <<<"$entry"
  path="$ASSETS/$name"
  if [[ -f "$path" && "$(wc -c <"$path" | tr -d ' ')" == "$size" ]]; then
    echo "ok       $name"
    continue
  fi
  echo "fetching $name"
  curl -fL --progress-bar -o "$path.part" "$url"
  actual="$(wc -c <"$path.part" | tr -d ' ')"
  if [[ "$actual" != "$size" ]]; then
    echo "error: $name is $actual bytes, expected $size (did the source change?)" >&2
    rm -f "$path.part"
    exit 1
  fi
  mv "$path.part" "$path"
done

F15="$ASSETS/f-15a-eagle-usaf-76-0020-duxford"
if [[ -d "$F15" ]]; then
  echo "ok       f-15a-eagle-usaf-76-0020-duxford/"
else
  cat <<EOF

The F-15 model needs a (free) Sketchfab login, so download it by hand:
  https://sketchfab.com/3d-models/f-15a-eagle-usaf-76-0020-duxford-524f9394057e46ec8424d4a356f794b7
and unzip it to:
  $F15
(Only needed to rebuild the scene from scratch: light_speed.blend already packs
the plane and its textures.)
EOF
fi
