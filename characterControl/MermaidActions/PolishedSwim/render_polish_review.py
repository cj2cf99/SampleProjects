"""Render selected review stills or the finished animation."""

from pathlib import Path
import sys

import bpy


folder, *frames = sys.argv[sys.argv.index("--") + 1:]
folder = Path(folder).resolve()
folder.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
if frames:
    scene.render.resolution_percentage = 60
    scene.eevee.taa_render_samples = 9
    for frame in map(int, frames):
        scene.frame_set(frame)
        scene.render.filepath = str(folder / f"{frame:04}.png")
        bpy.ops.render.render(write_still=True)
else:
    scene.render.resolution_percentage = 100
    scene.render.filepath = folder.as_posix() + "/"
    bpy.ops.render.render(animation=True)
