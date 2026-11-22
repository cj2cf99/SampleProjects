import sys
from pathlib import Path

import bpy


args=sys.argv[sys.argv.index("--")+1:]
path=Path(args[0]).resolve()
path.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
scene.render.resolution_percentage=100
scene.render.filepath=str(path)+"/"
scene.render.image_settings.file_format="PNG"
scene.render.image_settings.color_mode="RGB"
scene.eevee.taa_render_samples=9
if len(args)==3:
    scene.frame_start,scene.frame_end=map(int,args[1:])
bpy.ops.render.render(animation=True)
