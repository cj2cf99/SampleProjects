import sys
from pathlib import Path

import bpy


args = sys.argv[sys.argv.index("--") + 1:]
out = Path(args[0])
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.resolution_x = 1120
scene.render.resolution_y = 560
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.compression = 15
scene.render.filepath = str(out.resolve()) + "/"
scene.eevee.taa_render_samples = 12
if len(args) == 3:
    scene.frame_start, scene.frame_end = map(int, args[1:])
bpy.ops.render.render(animation=True)
