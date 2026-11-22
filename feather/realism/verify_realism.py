"""Verify the saved feather scene, sampled motion images and framing."""

from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
import numpy as np


root = Path(__file__).resolve().parent
assert Path(bpy.data.filepath).resolve() == root / 'warbler-wing-realism.blend'
scene = bpy.context.scene
cards = [obj for obj in scene.objects if obj.type == 'MESH' and obj.data.uv_layers.get('Card')]
hair = [obj for obj in scene.objects if obj.type == 'CURVES']
fibers = sum(len(obj.data.curves) for obj in hair)
assert (len(cards), fibers) == (342, 23098)
assert all(obj.parent in cards for obj in hair)
assert len([obj for obj in cards if obj.data.shape_keys]) == 18
assert (scene.frame_current, scene.frame_start, scene.frame_end, scene.render.fps) == (25, 1, 90, 24)
assert not bpy.data.libraries
maps = bpy.data.images['Wing | original fiber maps RGBA']
assert maps.packed_file and tuple(maps.size) == (1792, 1472)
pixels = np.empty(len(maps.pixels), dtype=np.float32)
maps.pixels.foreach_get(pixels)
assert pixels[3::4].min() < .01 and pixels[3::4].max() > .99
print(f'SCENE {len(cards)} editable feather cards, {fibers} hair curves, packed RGBA atlas', flush=True)

for file, size in {
    '01-baseline': (1320, 1040), '02-cards': (1320, 1040), '03-groom': (1320, 1040),
    'shoulder': (1320, 1040), 'dorsal': (2240, 1440), 'macro': (1760, 1320),
    'folded': (1600, 1200), 'ventral': (1760, 1120),
}.items():
    image = bpy.data.images.load(str(root / f'{file}.png'), check_existing=False)
    assert tuple(image.size) == size, file
    bpy.data.images.remove(image)
print('STILLS matched dimensions for all eight PNGs', flush=True)

scene.render.resolution_x, scene.render.resolution_y = 960, 614
camera = bpy.data.objects['Motion · three-quarter']
graph = bpy.context.evaluated_depsgraph_get()
subjects = [obj for obj in scene.objects if obj.type in {'MESH', 'CURVES'}]
margin = 1.
for frame in range(1, 91):
    scene.frame_set(frame)
    for subject in subjects:
        evaluated = subject.evaluated_get(graph)
        for corner in evaluated.bound_box:
            view = world_to_camera_view(scene, camera, evaluated.matrix_world @ Vector(corner))
            margin = min(margin, view.x, view.y, 1 - view.x, 1 - view.y)
assert margin > .05
print(f'FRAMING 90 frames, minimum safe margin {margin:.2%}', flush=True)

playback = bpy.data.scenes.new('Verify encoded motion')
strip = playback.sequence_editor_create().strips.new_movie(
    'Feather motion', str(root / 'motion.mp4'), channel=1, frame_start=1)
assert strip.frame_final_duration == 90
size = strip.elements[0].orig_width, strip.elements[0].orig_height
assert size == (960, 614)
playback.render.resolution_x, playback.render.resolution_y = size
playback.render.resolution_percentage = 100
playback.view_settings.view_transform = 'Standard'
bpy.context.window.scene = playback
samples = []
for frame in (25, 55):
    playback.frame_set(frame)
    file = root / f'proof-frame-{frame}.png'
    playback.render.filepath = str(file)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(file), check_existing=False)
    array = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(array)
    samples.append(array)
    bpy.data.images.remove(image)
assert np.abs(samples[0] - samples[1]).mean() > .005
print('MOVIE 960x614, 90 frames; visually distinct frames 25 and 55 decoded', flush=True)
