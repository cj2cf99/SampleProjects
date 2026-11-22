"""Reopen the experiment with Blender and check the renderable deliverables.

Usage: blender -b --factory-startup warbler-wing.blend --python-exit-code 7 -P iterations/verify_delivery.py
"""

from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


root = Path(__file__).resolve().parents[1]
scene = bpy.context.scene
assert Path(bpy.data.filepath).resolve() == root / 'warbler-wing.blend'
subjects = [obj for obj in scene.objects if obj.type == 'MESH']
feathers = [obj for obj in subjects if obj.data.color_attributes.get('Pigment')]
assert len(feathers) == 299
assert len([obj for obj in feathers if obj.data.shape_keys]) == 18
assert all(obj.parent and obj.data.uv_layers.get('Feather') for obj in feathers)
assert not bpy.data.libraries
assert (scene.frame_start, scene.frame_end, scene.render.fps) == (1, 90, 24)
assert scene.frame_current == 25
print('REOPENED', len(feathers), 'editable feathers,',
      sum(len(obj.data.polygons) for obj in subjects), 'base mesh faces', flush=True)

motion = bpy.data.objects['Motion · three-quarter']
scene.render.resolution_x, scene.render.resolution_y = 1200, 768
depsgraph = bpy.context.evaluated_depsgraph_get()
margin = 1.
for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)
    for subject in subjects:
        evaluated = subject.evaluated_get(depsgraph)
        for corner in evaluated.bound_box:
            world = evaluated.matrix_world @ Vector(corner)
            projected = world_to_camera_view(scene, motion, world)
            margin = min(margin, projected.x, projected.y, 1 - projected.x, 1 - projected.y)
assert margin > .035, f'Animation has insufficient frame margin: {margin:.3%}'
print(f'FRAMING All 90 frames, minimum projected bounding-box margin = {margin:.2%}', flush=True)

for name, size in {'dorsal': (2240, 1440), 'macro': (1920, 1440),
                   'ventral': (1760, 1120), 'folded': (1600, 1200)}.items():
    image = bpy.data.images.load(str(root / 'renders' / f'{name}.png'))
    assert tuple(image.size) == size
    bpy.data.images.remove(image)
    print('STILL', name, size, flush=True)

if '--stills-only' not in sys.argv:
    playback = bpy.data.scenes.new('Playback check')
    playback.frame_start, playback.frame_end = 1, 90
    video = playback.sequence_editor_create().strips.new_movie(
        'Review', str(root / 'renders' / 'motion.mp4'), channel=1, frame_start=1)
    assert video.frame_final_duration == 90
    video_size = video.elements[0].orig_width, video.elements[0].orig_height
    assert video_size == (1200, 768)
    print('MOVIE', video_size, video.frame_final_duration, 'readable frames', flush=True)
    playback.render.resolution_x, playback.render.resolution_y = video_size
    playback.render.resolution_percentage = 100
    playback.view_settings.view_transform = 'Standard'
    bpy.context.window.scene = playback
    decoded = []
    for frame in (25, 55):
        playback.frame_set(frame)
        destination = root / 'iterations' / f'encoded-frame-{frame}.png'
        playback.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        decoded.append(destination.read_bytes())
    assert decoded[0] != decoded[1], 'Preview samples show an identical picture'
    print('DECODED distinct MP4 frames 25 and 55', flush=True)
