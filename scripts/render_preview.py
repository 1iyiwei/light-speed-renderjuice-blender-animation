"""Render a quick preview video of light_speed.blend.

Run headless from the project root (does not save the .blend):

    blender -b light_speed.blend --python scripts/render_preview.py

Writes previews/preview.mp4 at reduced resolution and samples; pass options
after "--" to change them, e.g. `-- --percent 100 --samples 64 --out final`.
"""

import argparse
import sys

import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--percent", type=int, default=50, help="resolution percentage")
    parser.add_argument("--samples", type=int, default=16, help="EEVEE render samples")
    parser.add_argument("--out", default="preview", help="file name under previews/")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    scene = bpy.context.scene
    render = scene.render
    render.resolution_percentage = args.percent
    scene.eevee.taa_render_samples = args.samples
    render.image_settings.file_format = "FFMPEG"
    render.ffmpeg.format = "MPEG4"
    render.ffmpeg.codec = "H264"
    render.ffmpeg.constant_rate_factor = "HIGH"
    render.ffmpeg.audio_codec = "NONE"
    render.filepath = f"//previews/{args.out}.mp4"
    render.use_file_extension = False
    print(f"Rendering frames {scene.frame_start}-{scene.frame_end} at {args.percent}%, "
          f"{args.samples} samples -> {render.filepath}")
    bpy.ops.render.render(animation=True)


main()
