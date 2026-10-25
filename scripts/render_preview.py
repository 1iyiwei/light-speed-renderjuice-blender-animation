"""Render a preview or the final video of light_speed.blend.

Run headless from the project root (does not save the .blend):

    blender -b light_speed.blend --python scripts/render_preview.py

Writes previews/preview.mp4 at reduced resolution and samples; pass options
after "--" to change them. The final render:

    blender -b light_speed.blend --python scripts/render_preview.py -- --percent 100 --samples 64 --out final --sequence

With --sequence, frames are written as PNGs to previews/<out>_frames/ first,
skipping frames already there, so a long render can be stopped and resumed by
running the same command again; then ffmpeg encodes them to previews/<out>.mp4.
"""

import argparse
import os
import shutil
import subprocess
import sys

import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--percent", type=int, default=50, help="resolution percentage")
    parser.add_argument("--samples", type=int, default=16, help="EEVEE render samples")
    parser.add_argument("--out", default="preview", help="file name under previews/")
    parser.add_argument("--sequence", action="store_true", help="render resumable PNG frames, then encode them")
    parser.add_argument("--frames", help="only these frames, e.g. 300-310 (with --sequence)")
    return parser.parse_args(argv)


def encode(frames_dir, fps, output):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print(f"ffmpeg not found; frames are in {frames_dir}")
        return
    subprocess.run([ffmpeg, "-y", "-v", "error", "-framerate", str(fps), "-i", os.path.join(frames_dir, "%04d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", output], check=True)
    print(f"Encoded {output}")


def main():
    args = parse_args()
    scene = bpy.context.scene
    render = scene.render
    render.resolution_percentage = args.percent
    scene.eevee.taa_render_samples = args.samples
    if args.sequence:
        frames_dir = bpy.path.abspath(f"//previews/{args.out}_frames")
        os.makedirs(frames_dir, exist_ok=True)
        render.image_settings.file_format = "PNG"
        render.image_settings.color_depth = "8"
        render.filepath = os.path.join(frames_dir, "")
        render.use_file_extension = True
        # Resumable: skip frames already written (a placeholder marks one in progress).
        render.use_overwrite = False
        render.use_placeholder = True
        if args.frames:
            first, _, last = args.frames.partition("-")
            scene.frame_start, scene.frame_end = int(first), int(last or first)
    else:
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
    if args.sequence and not args.frames:
        encode(frames_dir, scene.render.fps, bpy.path.abspath(f"//previews/{args.out}.mp4"))


main()
