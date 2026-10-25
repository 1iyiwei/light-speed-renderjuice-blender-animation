#!/usr/bin/env bash
# Add the background music to a rendered video.
#
#     scripts/add_music.sh previews/final.mp4 previews/final_music.mp4
#
# The track ("Space Galaxy Universe" by Dmitrii Spis, Pixabay) has a quiet,
# pulsing intro and a full-energy drop at 20.2 s. Starting it at OFFSET_S
# lands the drop at 11.0 s into the video: top speed, when the whole sky has
# collapsed into a single point. It fades in at the start and out under the
# end card. The video stream is copied, not re-encoded.
set -euo pipefail

INPUT="${1:?usage: add_music.sh input.mp4 output.mp4}"
OUTPUT="${2:?usage: add_music.sh input.mp4 output.mp4}"
MUSIC="$(cd "$(dirname "$0")/.." && pwd)/assets/nastelbom-space-galaxy-universe-music-357376.mp3"

DROP_IN_TRACK_S=20.2
DROP_IN_VIDEO_S=11.0
OFFSET_S=$(echo "$DROP_IN_TRACK_S - $DROP_IN_VIDEO_S" | bc)
FADE_IN_S=1.0
FADE_OUT_S=2.5

duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT")
fade_out_start=$(echo "$duration - $FADE_OUT_S" | bc)

ffmpeg -y -v error -i "$INPUT" -ss "$OFFSET_S" -i "$MUSIC" \
  -filter_complex "[1:a]atrim=duration=${duration},afade=t=in:st=0:d=${FADE_IN_S},afade=t=out:st=${fade_out_start}:d=${FADE_OUT_S}[music]" \
  -map 0:v -map "[music]" -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart "$OUTPUT"
echo "Wrote $OUTPUT (music from ${OFFSET_S} s into the track, drop at ${DROP_IN_VIDEO_S} s)"
