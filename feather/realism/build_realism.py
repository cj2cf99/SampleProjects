"""Feather-card and curve-groom comparison against the saved single-wing baseline."""

import argparse
from pathlib import Path
from random import Random
import sys
from zlib import crc32

import bpy
from mathutils import Vector
import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_wing as baseline


TILE_X, TILE_Y = 448, 736
TILES_X, TILES_Y = 4, 2
ATLAS_X, ATLAS_Y = TILE_X * TILES_X, TILE_Y * TILES_Y
PAD = 4


def ease(a, b, value):
    f = np.clip((value - a) / (b - a), 0, 1)
    return f * f * (3 - 2 * f)


def feather_tile(seed, loose, flight):
    """Encode pigment, fiber relief, worn luminance and opacity in R, G, B and A."""
    rng = np.random.default_rng(seed)
    u = np.linspace(-1, 1, TILE_X - 2 * PAD, dtype=np.float32)[None, :]
    v = np.linspace(0, 1, TILE_Y - 2 * PAD, dtype=np.float32)[:, None]
    s = abs(u)
    phase = rng.uniform(0, 6)
    pigment = np.empty((v.size, u.size), dtype=np.float32)
    relief = np.empty_like(pigment)
    worn = np.empty_like(pigment)
    coverage = np.empty_like(pigment)
    for columns, sign in ((slice(0, u.size // 2), -1), (slice(u.size // 2, None), 1)):
        x = s[:, columns]
        # Barbs branch from a shaft at uneven intervals. Each vane has its own direction field.
        number = 110 if loose else 170
        gaps = rng.lognormal(0, .37, number)
        centers = (np.cumsum(gaps) / sum(gaps)) * 1.33 - .28
        half_gap = np.r_[gaps[1:], gaps[-1]] * (1.33 / sum(gaps))
        sweep = rng.uniform(.041, .096) + .077 * (1 - v) + .010 * sign
        warp = .0062 * np.sin(21 * x + 8 * v + phase) * x + .006 * np.sin(39 * v + phase)
        if flight:
            warp *= .40
        q = v - sweep * x - rng.uniform(.03, .067) * x * x + warp
        i = np.clip(np.searchsorted(centers, q), 1, number - 1)
        i -= abs(q - centers[i - 1]) < abs(q - centers[i])
        offset = (q - centers[i]) / half_gap[i]
        width = rng.uniform(.20, .42, number)[i]
        width *= .90 + .16 * np.sin(11 * x + 8 * v + phase)
        ridge = np.exp(-np.square(offset / width))
        barbs = rng.uniform(.55, .99, number)[i]
        bundles = np.interp(centers, np.linspace(-.30, 1.12, 27), rng.uniform(.60, 1.15, 27))[i]
        grain = rng.random((v.size, x.size))
        fine = .5 + .5 * np.cos(2 * np.pi * (x * (13 + 11 * v) + .43 * i + .17 * np.sin(i)))
        cloud = (.077 if flight else .11) * np.sin(19 * v + phase + 7 * x) * np.sin(13 * v - 14 * x - phase)
        light_tips = ease(.58, .99, x) * ease(.33, .80, v)
        pigment[:, columns] = np.clip(.45 + .36 * (ridge - .5) * barbs + .23 * (bundles - .8)
                                      + cloud + .044 * (grain - .5) + .09 * (fine - .5), 0, 1)
        relief[:, columns] = np.clip(.25 + .48 * ridge * barbs + .13 * fine * ridge + .05 * grain, 0, 1)
        worn[:, columns] = light_tips * ridge * rng.uniform(.04, .39, number)[i]

        # Separate irregular nibs near the edge while leaving a continuous closed vane inward.
        lower_edge = .929 if flight else .89
        edge_profile = np.interp(centers, np.linspace(-.28, 1.06, 30), rng.uniform(lower_edge, 1.026, 30))
        edge_profile += rng.uniform(-.026, .024, number) if flight else rng.uniform(-.06, .043, number)
        nicks = 3 if flight else (5 if loose else 4)
        for notch in rng.integers(number // 3, number - 3, nicks):
            deep = rng.uniform(.055, .108) if flight else rng.uniform(.07, .17)
            edge_profile[notch - 1:notch + 2] -= (deep * .48, deep, deep * .57)
        edge = edge_profile[i] - (.035 if loose else 0)
        edge -= (.038 if loose else .016) * np.sin(36 * v + phase)
        alpha = 1 - ease(edge - .016, edge + .017, x)
        free_length = ease(.89 if flight else (.73 if loose else .84), 1.02, x)
        web = 1 - free_length * (1 - ease(.14, .54, ridge))
        root = ease(.015, .19 if loose else .12, v)
        end_break = 1 - .38 * ease(.945, 1.0, v) * (1 - ridge) * ease(.40, .92, x)
        coverage[:, columns] = alpha * web * root * end_break

    rgba = np.dstack((pigment, relief, worn, coverage))
    return np.pad(rgba, ((PAD, PAD), (PAD, PAD), (0, 0)), mode='edge')


def make_atlas():
    pixels = np.empty((ATLAS_Y, ATLAS_X, 4), dtype=np.float32)
    for variant in range(TILES_X * TILES_Y):
        x, y = variant % TILES_X * TILE_X, variant // TILES_X * TILE_Y
        pixels[y:y + TILE_Y, x:x + TILE_X] = feather_tile(23461 + 193 * variant, variant >= 4, variant < 2)
    image = bpy.data.images.new('Wing | original fiber maps RGBA', width=ATLAS_X, height=ATLAS_Y, alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    image.alpha_mode = 'CHANNEL_PACKED'
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    image.pack()
    return image


def card_material(atlas, groomed):
    material = bpy.data.materials.new('Feather cards | irregular fibers and cutout')
    material.diffuse_color = (.069, .066, .061, 1)
    material.surface_render_method = 'DITHERED'
    tree = material.node_tree
    nodes, link = tree.nodes, tree.links.new
    shader = nodes.get('Principled BSDF')
    shader.inputs['Specular IOR Level'].default_value = .24
    shader.inputs['Anisotropic'].default_value = .42
    shader.inputs['Sheen Weight'].default_value = .105
    shader.inputs['Sheen Roughness'].default_value = .60
    attr = nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Pigment'
    attr.location = (-820, 355)
    coords = nodes.new('ShaderNodeUVMap')
    coords.uv_map = 'Card'
    coords.location = (-1060, 40)
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = atlas
    tex.extension = 'EXTEND'
    tex.label = 'R pigment · G height · B fading · A coverage'
    tex.location = (-820, 40)
    link(coords.outputs[0], tex.inputs['Vector'])
    split = nodes.new('ShaderNodeSeparateColor')
    split.location = (-520, 40)
    link(tex.outputs['Color'], split.inputs['Color'])

    def scale_bias(source, scale, bias, position):
        node = nodes.new('ShaderNodeMath')
        node.operation = 'MULTIPLY_ADD'
        node.inputs[1].default_value, node.inputs[2].default_value = scale, bias
        link(source, node.inputs[0])
        node.location = position
        return node.outputs[0]

    color_gain = scale_bias(split.outputs['Red'], 1.14 if groomed else .83, .42 if groomed else .57, (-310, 365))
    mul = nodes.new('ShaderNodeMixRGB')
    mul.blend_type = 'MULTIPLY'
    mul.inputs[0].default_value = 1
    mul.location = (-100, 440)
    link(attr.outputs['Color'], mul.inputs[1])
    link(color_gain, mul.inputs[2])
    faded = nodes.new('ShaderNodeMixRGB')
    faded.blend_type = 'MIX'
    faded.inputs[2].default_value = (.210, .177, .137, 1)
    faded.location = (120, 465)
    link(mul.outputs[0], faded.inputs[1])
    link(scale_bias(split.outputs['Blue'], .51 if groomed else .37, 0, (-310, 120)), faded.inputs[0])
    link(faded.outputs[0], shader.inputs['Base Color'])
    link(tex.outputs['Alpha'], shader.inputs['Alpha'])
    link(scale_bias(split.outputs['Red'], -.16, .64, (-310, -65)), shader.inputs['Roughness'])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .29 if groomed else .35
    bump.inputs['Distance'].default_value = .00185 if groomed else .0024
    bump.location = (30, -120)
    link(split.outputs['Green'], bump.inputs['Height'])
    link(bump.outputs[0], shader.inputs['Normal'])
    tangent = nodes.new('ShaderNodeTangent')
    tangent.direction_type = 'UV_MAP'
    tangent.uv_map = 'Feather'
    tangent.location = (35, -390)
    link(tangent.outputs[0], shader.inputs['Tangent'])
    shader.location = (370, 360)
    nodes.get('Material Output').location = (700, 360)
    return material


def surface_grid(obj):
    large = obj.data.shape_keys is not None
    return (113, 13) if large else (61, 9)


def loose_feather(obj):
    return obj.name[0] in {'D', 'R', 'N'}


def adjust_coverts(obj, rows, columns):
    name = obj.name.split()[0]
    if obj.name[0] not in {'C', 'D', 'N', 'U', 'R'}:
        return
    data = obj.data.color_attributes['Pigment'].data
    pigment = np.empty((len(data), 4), dtype=np.float32)
    data.foreach_get('color', pigment.ravel())
    plane = pigment[:rows * columns, :3].reshape(rows, columns, 3)
    rng = np.random.default_rng(crc32(name.encode()))
    u = np.linspace(-1, 1, columns)[None, :]
    v = np.linspace(0, 1, rows)[:, None]
    side = float(rng.choice((-1, 1)))
    original = plane.copy()
    base = np.median(original[:int(rows * .42)], axis=0)[None, :, :]
    tip_delta = original[-1:, :, 0] - base[:, :, 0]
    if tip_delta[0, columns // 2] > .14 and original[-1, columns // 2, 0] > .25:
        # Reference each shaft's own grey base on the underside. Absolute white thresholds
        # mistakenly interpret some naturally pale down and covert bases as white tips.
        threshold = base[:, :, 0] + np.maximum(.45 * tip_delta, .075) if name[0] in {'U', 'R'} else .19
        starts = np.argmax(original[:, :, 0] > threshold, axis=0)[None, :] / (rows - 1)
        shift = rng.uniform(-.044, .095) + u * side * rng.uniform(.013, .083)
        shift += .030 * np.sin(u * 9 + rng.uniform(0, 6.28))
        fade = ease(starts + shift - .042, starts + shift + .035, v)
        if rng.random() < .48 or loose_feather(obj):
            streak = ease(.12, .94, u * side) * ease(.63, .94, v)
            fade *= 1 - rng.uniform(.33, .73) * streak
        white = original[-1:, :, :] * rng.uniform(.66, .94)
        plane[:] = (1 - fade[:, :, None]) * base + fade[:, :, None] * white
    tint = 1 + .23 * np.sin(17 * v + 3.2 * u + rng.uniform(0, 6.28))
    tint *= 1 + .15 * np.sin(33 * v - 6.1 * u + rng.uniform(0, 6.28))
    plane *= tint[:, :, None]
    pigment[:rows * columns, :3] = np.clip(plane.reshape(rows * columns, 3), .001, .85)
    data.foreach_set('color', pigment.ravel())


def to_card(obj, material, groomed):
    mesh = obj.data
    rows, columns = surface_grid(obj)
    count = rows * columns
    name = obj.name.split()[0]
    is_down = loose_feather(obj)
    seed = crc32(name.encode())
    variant = 4 + seed % 4 if is_down else ((0 if mesh.shape_keys else 2) + seed % 2)
    original_uv = mesh.uv_layers['Feather'].uv
    uv = np.empty((len(mesh.loops), 2), dtype=np.float32)
    original_uv.foreach_get('vector', uv.ravel())
    tile_origin = np.array((variant % TILES_X * TILE_X, variant // TILES_X * TILE_Y))
    uv *= (TILE_X - 2 * PAD - 1, TILE_Y - 2 * PAD - 1)
    uv += tile_origin + PAD + .5
    uv /= (ATLAS_X, ATLAS_Y)
    mesh.uv_layers.new(name='Card').uv.foreach_set('vector', uv.ravel())
    mesh.materials[0] = material
    if groomed:
        adjust_coverts(obj, rows, columns)

    # A gently expanded sheet gives the opacity map room for broken fibers at its edges.
    spread = .162 if is_down else .132
    weight = (1 + spread * np.square(np.linspace(-1, 1, columns)))[None, :, None]

    def pad_coordinates(points):
        coords = np.empty((len(points), 3), dtype=np.float32)
        points.foreach_get('co', coords.ravel())
        grid = coords[:count].reshape(rows, columns, 3)
        centers = grid[:, columns // 2:columns // 2 + 1, :].copy()
        grid[:, :, :2] = centers[:, :, :2] + (grid[:, :, :2] - centers[:, :, :2]) * weight
        if groomed and (is_down or name[:2] in {'C3', 'C4', 'C5'}):
            root_shaft = coords[count:count + 9 * 7].reshape(9, 7, 3)
            sign = -1 if name[0] == 'R' else 1
            root_shaft[:, :, 2] -= sign * np.linspace(.023, 0, 9)[:, None]
        points.foreach_set('co', coords.ravel())

    if mesh.shape_keys:
        for key in mesh.shape_keys.key_blocks:
            pad_coordinates(key.data)
    else:
        pad_coordinates(mesh.vertices)
    mesh.update()


def fiber_material():
    material = bpy.data.materials.new('Down and loose barbs | hair scattering')
    tree = material.node_tree
    shader = tree.nodes.new('ShaderNodeBsdfHairPrincipled')
    shader.parametrization = 'COLOR'
    shader.inputs['Roughness'].default_value = .51
    shader.inputs['Radial Roughness'].default_value = .56
    shader.inputs['IOR'].default_value = 1.52
    color = tree.nodes.new('ShaderNodeAttribute')
    color.attribute_name = 'FiberTint'
    tree.links.new(color.outputs['Color'], shader.inputs['Color'])
    tree.links.new(shader.outputs[0], tree.nodes.get('Material Output').inputs['Surface'])
    return material


def add_groom(feather, group, material, subtle):
    """Clumps of curved, tapered down branching from nearby points on feather surfaces."""
    rng = Random(crc32(feather.name.encode()))
    mesh = feather.data
    color = mesh.color_attributes['Pigment'].data
    rows, columns = surface_grid(feather)
    reverse = feather.name[0] == 'R'
    is_down = loose_feather(feather)
    up = Vector((0, 0, -1 if reverse else 1))
    positions, radii, colors, sizes = [], [], [], []

    def strand(points, radius, tint):
        n = len(points)
        sizes.append(n)
        for j, point in enumerate(points):
            fraction = j / (n - 1)
            positions.extend(point)
            radii.append(radius * (.06 + .94 * (1 - fraction) ** .75))
            colors.extend((*(c * (1 + .31 * fraction) for c in tint), 1))

    for _ in range(15 if is_down else (5 if subtle else 8)):
        index = rng.randint(19, 55)
        col = rng.choices(range(1, columns - 1), weights=(4, 4, 2, 1, 2, 4, 4))[0]
        vertex = index * columns + col
        root = mesh.vertices[vertex].co.copy()
        if subtle:
            root -= up * rng.uniform(.013, .047 if is_down else .057)
        elif rng.random() < .62:
            root -= up * rng.uniform(.011, .044)
        heading = (mesh.vertices[vertex + columns].co - mesh.vertices[vertex - columns].co).normalized()
        side = heading.cross(up).normalized()
        length = rng.uniform(.049, .118 if subtle else .139) * (1.13 if is_down else .75)
        drift = rng.uniform(-.38, .33)
        lift = rng.uniform(.21, (.64 if is_down else .47) if subtle else .77) * (.90 if reverse else 1)
        tints = tuple(color[vertex].color[:3])
        tint = tuple(min(.65, (.009 if subtle else .023) + c * rng.uniform(1.09, 1.59 if subtle else 1.91))
                     for c in tints)
        stroke = heading * length + side * drift * length
        crown = up * lift * length
        cap = root + stroke + crown
        strand((root, root + stroke * .32 + crown * .20, root + stroke * .67 + crown * .84, cap),
               rng.uniform(.00043, .00084) if subtle else rng.uniform(.00062, .00114), tint)
        # Soft side branches curl and gather into a small tuft rather than a blanket of hair.
        for _ in range(rng.randint(5, 9)):
            p = rng.uniform(.15, .92)
            base = root + stroke * p + crown * p ** 1.20
            extent = length * rng.uniform(.19, .53) * (1 - .50 * p)
            offset = side * (extent * rng.uniform(-.82, .82))
            travel = heading * extent * rng.uniform(.48, .94)
            plume = up * extent * rng.uniform(.04, .51)
            strand((base, base + travel * .31 + offset * .60 + plume * .20,
                    base + .72 * travel + .90 * offset + plume * .71, base + travel + offset + plume),
                   rng.uniform(.00029, .00054) if subtle else rng.uniform(.00037, .00075), tint)

    data = bpy.data.hair_curves.new(f'{feather.name} | down curves')
    data.add_curves(sizes)
    data.attributes['position'].data.foreach_set('vector', positions)
    radius = data.attributes.get('radius') or data.attributes.new('radius', 'FLOAT', 'POINT')
    radius.data.foreach_set('value', radii)
    data.color_attributes.new('FiberTint', 'FLOAT_COLOR', 'POINT').data.foreach_set('color', colors)
    data.materials.append(material)
    obj = baseline.new_object(f'{feather.name} | down groom', data, group)
    obj.parent = feather
    return len(sizes)


def cover_shoulder(material, fill_gaps):
    shoulder = bpy.data.objects['Shoulder · flap and pitch']
    upper = bpy.data.collections['03 · Dorsal coverts']
    shaft = bpy.data.materials['Feather | rachis and free barb tips']
    rng = Random(736019)
    added = []
    bound = [(-.24, .166, .255), (-.17, .299, .280), (-.07, .376, .272),
             (.05, .417, .259), (.18, .426, .239), (.30, .415, .216),
             (.41, .390, .201), (.54, .360, .189), (.70, .329, .174)]
    for row in range(4):
        for i, (x, y, z) in enumerate(bound):
            x += (row - 1.5) * .032 + rng.uniform(-.025, .020)
            y -= row * .055 + rng.uniform(-.036, .022)
            z += row * (.039 + .006 * (1 - i / 8)) + rng.uniform(-.014, .017)
            length = rng.uniform(.090, .164) + row * .021
            spread = rng.uniform(-.032, .094) + .036 * row
            tip = (x + spread, y - length, z + .011 - row * .014)
            pale = rng.uniform(.73, .92) if rng.random() < .26 else 0.
            spec = baseline.Feather((x, y, z), tip, rng.uniform(.088, .145), 'down',
                                    rng.uniform(-.018, .026), rng.uniform(.42, .59),
                                    rng.uniform(-.024, .020), pale, rng.uniform(.045, .100), .020)
            feather = baseline.make_feather(f'N{row + 1}.{i + 1:02} · shoulder transition', spec,
                                            upper, shoulder, (material, shaft), rng, detail=True)
            added.append(feather)
    if fill_gaps:
        # Bridge the gaps seen behind the lesser coverts in the fixed-camera test.
        for i, (x, y, z, dy) in enumerate(((-.06, -.164, .249, -.28), (.11, -.129, .272, -.29),
                                           (.25, -.136, .263, -.34), (.43, -.121, .250, -.30),
                                           (.62, -.104, .240, -.32), (.78, -.101, .227, -.31),
                                           (.91, -.085, .216, -.32))):
            tip = (x + rng.uniform(.075, .179), y + dy, z - rng.uniform(.04, .067))
            spec = baseline.Feather((x, y, z), tip, rng.uniform(.190, .245), 'shoulder',
                                    bend=rng.uniform(-.032, .046), roll=rng.uniform(-.031, .025),
                                    gray=rng.uniform(.033, .069), curl=.033)
            added.append(baseline.make_feather(f'N5.{i + 1:02} · between lesser coverts', spec,
                                               upper, shoulder, (material, shaft), rng, detail=True))
    return added


def feather_objects(scene):
    return [obj for obj in scene.objects if obj.type == 'MESH' and obj.data.color_attributes.get('Pigment')]


def wing_card_selection(feather, local):
    return not local or (feather.matrix_world.translation.x < 1.94 and feather.name[0] in {'C', 'D', 'S'})


def groom_selection(feather, local):
    prefix = feather.name.split()[0]
    if prefix[0] in {'D', 'N'}:
        return not local or feather.matrix_world.translation.x < 1.75
    if prefix[0] == 'R':
        return not local
    return prefix[:2] in {'C3', 'C4', 'C5'} and feather.matrix_world.translation.x < 2.15


def lower_underwing_tip(feather):
    prefix = feather.name.split()[0]
    if prefix[0] != 'U':
        return
    # The back row lies farther from the flight vane towards its tip.
    # Move every vertex at a given UV length together, including the shaft.
    mesh = feather.data
    vertex_t = np.zeros(len(mesh.vertices), dtype=np.float32)
    corners = np.empty((len(mesh.loops), 2), dtype=np.float32)
    mesh.uv_layers['Feather'].uv.foreach_get('vector', corners.ravel())
    vertex_index = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', vertex_index)
    vertex_t[vertex_index] = corners[:, 1]
    depth = {'1': .105, '2': .050, '3': .018}[prefix[1]]
    coords = np.empty((len(mesh.vertices), 3), dtype=np.float32)
    mesh.vertices.foreach_get('co', coords.ravel())
    coords[:, 2] -= depth * ease(.16, .88, vertex_t)
    mesh.vertices.foreach_set('co', coords.ravel())
    mesh.update()


def render_motion(scene, camera):
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 960, 614
    scene.render.use_persistent_data = True
    scene.cycles.samples = 14
    scene.cycles.adaptive_threshold = .060
    scene.cycles.adaptive_min_samples = 5
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    scene.render.filepath = str(HERE / 'motion-render-')
    bpy.ops.render.render(animation=True)
    (HERE / 'motion-render-0001-0090.mp4').replace(HERE / 'motion.mp4')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['cards', 'groom', 'wing', 'motion'], required=True)
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    studio_file = HERE / 'warbler-wing-realism.blend' if args.stage == 'motion' else HERE.parent / 'warbler-wing.blend'
    bpy.ops.wm.open_mainfile(filepath=str(studio_file), load_ui=False)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.frame_set(25)
    scene.cycles.transparent_max_bounces = 16
    if not args.cpu:
        baseline.select_device(scene)
    if args.stage == 'motion':
        render_motion(scene, bpy.data.objects['Motion · three-quarter'])
        return

    studio = bpy.data.collections['05 · Cameras and lights']
    patch = baseline.camera('Compare · shoulder and white bars', studio,
                            (.88, -.43, .19), (.27, -.40, 1), 2.45, -13)
    if args.stage == 'cards':
        baseline.still(patch, 25, (1320, 1040), 54, HERE / '01-baseline.png')
    local = args.stage != 'wing'
    groomed = args.stage != 'cards'
    material = card_material(make_atlas(), groomed)
    feathers = feather_objects(scene)
    cards = [obj for obj in feathers if wing_card_selection(obj, local)]
    if groomed:
        new_feathers = cover_shoulder(material, fill_gaps=not local)
        cards.extend(new_feathers)
        feathers.extend(new_feathers)
    for feather in cards:
        to_card(feather, material, groomed)
        if not local:
            lower_underwing_tip(feather)
    count = 0
    if groomed:
        group = baseline.collection('06 · Fine down and barb curves')
        hair = fiber_material()
        for feather in feathers:
            if groom_selection(feather, local):
                count += add_groom(feather, group, hair, subtle=not local)
    print(f'{len(cards)} feather cards and {count} hair curves', flush=True)
    if local:
        name = '02-cards.png' if args.stage == 'cards' else '03-groom.png'
        baseline.still(patch, 25, (1320, 1040), 58, HERE / name)
        return

    subjects = [obj for obj in scene.objects if obj.type in {'MESH', 'CURVES'}]
    baseline.fit_camera(bpy.data.objects['Motion · three-quarter'], subjects, range(1, 91), 960 / 614, 1.14)
    baseline.fit_camera(bpy.data.objects['Folded · study'], subjects, (1,), 1600 / 1200, 1.19)
    for name, camera_name, frame, size, samples in (
        ('shoulder', patch.name, 25, (1320, 1040), 74),
        ('dorsal', 'Dorsal · full wing', 25, (2240, 1440), 70),
        ('macro', 'Macro · greater coverts and barbs', 25, (1760, 1320), 72),
        ('folded', 'Folded · study', 1, (1600, 1200), 65),
        ('ventral', 'Ventral · full wing', 25, (1760, 1120), 60),
    ):
        baseline.still(bpy.data.objects[camera_name], frame, size, samples, HERE / f'{name}.png')
    scene.frame_set(25)
    scene.camera = bpy.data.objects['Dorsal · full wing']
    scene.render.resolution_x, scene.render.resolution_y = 2240, 1440
    scene.cycles.samples = 70
    scene.cycles.device = 'CPU'
    scene.render.filepath = '//dorsal.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'warbler-wing-realism.blend'), compress=True)


if __name__ == '__main__':
    main()
