from pathlib import Path

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parent


def validate_model():
    scene = bpy.context.scene
    wings = [obj for obj in scene.objects if 'Family' in obj]
    assert len(wings) == 197
    assert all(obj.type == 'MESH' and obj.data.uv_layers.get('Photo') for obj in wings)
    for family, target in (('primary', 61.0), ('secondary', 49.0)):
        lengths = [obj['Illustrated rachis length (mm)'] for obj in wings if obj['Family'] == family]
        assert len(lengths) == 9 and max(lengths) == target, (family, lengths)
    curves = scene.objects['Sheltered shoulder down'].data
    assert len(curves.curves) == 3750
    assert scene.unit_settings.system == 'METRIC' and abs(scene.unit_settings.scale_length - .01) < 1e-6

    atlas = bpy.data.images['Photographic feather colors and edges']
    relief = bpy.data.images['Feather relief and thin areas']
    for image in (atlas, relief):
        assert image.packed_file and tuple(image.size) == (1408, 1248), image.name
    pixels = np.empty(len(atlas.pixels), dtype=np.float32)
    atlas.pixels.foreach_get(pixels)
    alpha = pixels[3::4]
    assert (alpha.min() < .02 and alpha.max() > .98 and .01 < alpha.mean() < .99)

    materials = [mat for mat in bpy.data.materials if 'scatter approximation' in mat.name]
    assert len(materials) == 1 and materials[0].users == len(wings)
    nodes = materials[0].node_tree.nodes
    assert any(node.bl_idname == 'ShaderNodeBsdfTranslucent' for node in nodes)
    print('Reopened: 197 meshes, 3,750 down curves, Pmax 61.0 mm, Smax 49.0 mm, two packed 1408 × 1248 atlases.', flush=True)


def validate_renders():
    renders = ROOT / 'renders'
    dimensions = {'shape-studio': (1320, 950), 'shape-whole': (1480, 1010)}
    for method in ('photo', 'optics'):
        dimensions[f'{method}-whole'] = (2080, 1380)
        dimensions.update((f'{method}-{light}', (1320, 950)) for light in ('studio', 'side', 'back'))
        dimensions.update((f'coupon-{method}-{light}', (1200, 630)) for light in ('side', 'back'))

    coupons = {}
    for file, size in dimensions.items():
        image = bpy.data.images.load(str(renders / f'{file}.png'), check_existing=False)
        assert tuple(image.size) == size, (file, tuple(image.size))
        if file.startswith('coupon-'):
            pixels = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(pixels)
            rgb = pixels.reshape(size[1], size[0], 4)[..., :3]
            coupons[file] = rgb
        bpy.data.images.remove(image)

    print(f'Decoded {len(dimensions)} comparison renders at their expected resolutions.', flush=True)
    for light in ('side', 'back'):
        control = coupons[f'coupon-photo-{light}']
        approximation = coupons[f'coupon-optics-{light}']
        delta = np.abs(approximation - control)
        changed = np.mean(np.max(delta, axis=2) > 3 / 255)
        assert changed > .003, (light, changed)
        print(f'Coupon {light}: {changed:.1%} of full frame exceeds a 3/255 RGB difference.', flush=True)


if __name__ == '__main__':
    validate_model()
    validate_renders()
