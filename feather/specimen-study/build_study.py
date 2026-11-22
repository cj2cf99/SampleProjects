"""Scan-guided folded wing with photographed feather cards and a relighting study."""

import argparse
from dataclasses import dataclass
from math import cos, exp, pi, sin
from pathlib import Path
from random import Random
import sys

import bpy
from mathutils import Vector
import numpy as np


ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]
sys.dont_write_bytecode = True
import build_wing as common
from photo_maps import atlas_coordinate, build_photographic_atlases


UP = Vector((0, 0, 1))

# Narrow vane outlines with the wider web on the opposite side of the rachis.
# Values are artist measurements and estimates from the viewed specimen plate.
STATIONS = (0, .075, .16, .29, .46, .64, .80, .90, .968, 1.)
PROFILES = {
    'primary': ((.025, .13, .44, .71, .83, .78, .61, .41, .22, .008),
                (.028, .17, .53, .87, 1., .96, .81, .61, .30, .008), .368),
    'secondary': ((.023, .19, .48, .76, .93, .89, .79, .57, .28, .008),
                  (.024, .26, .67, .95, 1., .93, .82, .60, .32, .008), .432),
    'cover': ((.022, .20, .50, .83, .98, .99, .87, .66, .35, .008),
              (.020, .23, .56, .88, 1., .95, .79, .64, .34, .008), .475),
    'short': ((.032, .23, .53, .82, 1., .96, .77, .52, .24, .008),
              (.031, .28, .66, .91, 1., .95, .75, .52, .26, .008), .48),
}


@dataclass
class Vane:
    name: str
    root: tuple
    tip: tuple
    width: float
    family: str
    variant: int
    bend: float
    roll: float
    shade: float
    white_tip: float = 0.
    layer: float = 0.


def smooth(low, high, value):
    return common.smooth(low, high, value)


def shell_height(x, y):
    return .53 * exp(-(((x - .83) / 2.43) ** 2 + ((y - .06) / 1.25) ** 2)) - .039 * x


def make_vane(spec, group, surface, shaft):
    rng = Random(spec.name)
    origin = Vector(spec.root)
    reach = Vector(spec.tip) - origin
    length = reach.length
    axis = reach.normalized()
    across = Vector((-reach.y, reach.x, 0)).normalized()
    left, right, balance = PROFILES[spec.family]
    drape = spec.family in ('cover', 'short')
    root_offset = spec.root[2] - shell_height(*spec.root[:2])
    tip_offset = spec.tip[2] - shell_height(*spec.tip[:2])
    # Measured stations are interpolated once, then smoothed without changing the endpoints.
    spline_t = np.linspace(0, 1, 145)
    lobe = []
    weights = np.array([.05, .15, .25, .25, .15, .10, .05])
    for shape in (left, right):
        linear = np.interp(spline_t, STATIONS, shape)
        smooth_profile = np.convolve(np.pad(linear, 3, mode='edge'), weights, mode='valid')
        smooth_profile[0], smooth_profile[-1] = linear[0], linear[-1]
        lobe.append(smooth_profile)
    phase = rng.uniform(0, 6)

    def centre(t):
        curve = across * (spec.bend * sin(pi * t) * (.70 + .30 * t))
        location = origin + reach * t + curve
        if drape:
            location.z = shell_height(location.x, location.y) + common.mix(root_offset, tip_offset, t)
        arch = {'primary': .024, 'secondary': .029, 'cover': .012, 'short': .017}[spec.family]
        location.z += spec.layer + arch * sin(pi * t) * min(length, 2.5)
        return location

    def colour(t, s):
        marbling = 1 + .12 * sin(t * 20 + s * 7 + phase) + .065 * sin(t * 73 - 5 * s + phase)
        grey = spec.shade * marbling * (.82 + .36 * t)
        near_edge = smooth(.68, .99, abs(s))
        dye = grey + .013 * near_edge * smooth(.26, .93, t)
        white = 0.
        if spec.white_tip:
            border = spec.white_tip + .055 * s + .027 * sin(7.8 * s + phase)
            white = smooth(border - .024, border + .040, t)
        return tuple(dye * m * (1 - white) + white * pale
                     for m, pale in ((1.04, .52), (.98, .50), (.90, .45)))

    mesh = common.FeatherMesh()
    columns = 12 if spec.family in ('primary', 'secondary') else 10
    for j, t in enumerate(spline_t):
        location = centre(t)
        for i in range(columns + 1):
            s = 2 * i / columns - 1
            profile = lobe[0][j] * balance if s < 0 else lobe[1][j] * (1 - balance)
            variation = 1 + .018 * sin(36 * t + phase + s) + .008 * sin(252 * t + phase) * abs(s) ** 3
            span = spec.width * profile * s * variation
            z = spec.width * profile * (.30 * spec.roll * s * sin(pi * t) - .063 * abs(s) ** 1.7)
            tip_skew = min(length, 3.) * (.010 + (.010 if s < 0 else 0)) * abs(s) * smooth(.72, 1., t)
            point = location + across * span + UP * z - axis * tip_skew
            if drape:
                point.z += shell_height(point.x, point.y) - shell_height(location.x, location.y)
            mesh.point(point, s, t, colour(t, s))
    stride = columns + 1
    for j in range(len(spline_t) - 1):
        for i in range(columns):
            a = j * stride + i
            mesh.quad((a, a + stride, a + stride + 1, a + 1), 0)

    if spec.family != 'short':
        ts = np.linspace(.015, .982, 25)
        radius = (.018 if spec.family in ('primary', 'secondary') else .016) * spec.width
        radii = [float(radius * (1 - t) ** 1.25 + .00017) for t in ts]
        positions = [centre(t) + UP * (r * .56 - .024 * (1 - t) ** 4) for t, r in zip(ts, radii)]
        shades = [tuple(c * .82 + .013 * (1 - t) for c in colour(t, 0)) for t in ts]
        mesh.tube(positions, radii, shades, across, .015, .982, 1, 6)
    obj = mesh.create(spec.name, group, (surface, shaft))
    photo_uv = obj.data.uv_layers.new(name='Photo')
    probe = [coord for loop in obj.data.loops for coord in atlas_coordinate(*mesh.uvs[loop.vertex_index], spec.variant)]
    photo_uv.uv.foreach_set('vector', probe)
    obj['Family'] = spec.family
    obj['Illustrated rachis length (mm)'] = round(length * 10, 1)
    return obj


def shader_photo(color_map, structure_map, optical):
    label = 'Feather | photographed vanes'
    if optical:
        label += ' and directional scatter approximation'
    material = bpy.data.materials.new(label)
    material.diffuse_color = (.083, .076, .071, 1)
    material.surface_render_method = 'DITHERED'
    tree = material.node_tree
    nodes, link = tree.nodes, tree.links.new
    shader, output = nodes.get('Principled BSDF'), nodes.get('Material Output')
    shader.location = (640, 400)
    output.location = (1140, 400)

    def math(op, *args, location=(0, 0)):
        node = nodes.new('ShaderNodeMath')
        node.operation = op
        node.location = location
        for index, value in enumerate(args):
            if isinstance(value, (float, int)):
                node.inputs[index].default_value = value
            else:
                link(value, node.inputs[index])
        return node.outputs[0]

    uv = nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'Photo'
    uv.location = (-1000, 80)
    rgb = nodes.new('ShaderNodeTexImage')
    rgb.image = color_map
    rgb.label = 'Reprojected photographs · pigment & silhouette'
    rgb.location = (-780, 410)
    data = nodes.new('ShaderNodeTexImage')
    data.image = structure_map
    data.label = 'R fine relief · G thin areas · B gloss variation'
    data.location = (-780, 80)
    for node in (rgb, data):
        node.extension = 'EXTEND'
        link(uv.outputs[0], node.inputs['Vector'])
    split = nodes.new('ShaderNodeSeparateColor')
    split.location = (-490, 80)
    link(data.outputs['Color'], split.inputs[0])
    original = nodes.new('ShaderNodeVertexColor')
    original.layer_name = 'Pigment'
    original.location = (-750, 730)
    combined = nodes.new('ShaderNodeMixRGB')
    combined.blend_type = 'MIX'
    combined.location = (-235, 680)
    combined.inputs[0].default_value = .87
    link(original.outputs['Color'], combined.inputs[1])
    link(rgb.outputs['Color'], combined.inputs[2])
    colour = combined.outputs[0]
    tangent = nodes.new('ShaderNodeTangent')
    tangent.direction_type = 'UV_MAP'
    tangent.uv_map = 'Feather'
    tangent.location = (-490, -190)
    link(tangent.outputs[0], shader.inputs['Tangent'])
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-150, 75)
    bump.inputs['Strength'].default_value = .09
    bump.inputs['Distance'].default_value = .00026
    link(split.outputs['Red'], bump.inputs['Height'])
    link(bump.outputs[0], shader.inputs['Normal'])
    link(colour, shader.inputs['Base Color'])
    link(math('MULTIPLY_ADD', split.outputs['Blue'], -.105, .55, location=(-120, 345)), shader.inputs['Roughness'])
    shader.inputs['Specular IOR Level'].default_value = .21
    shader.inputs['Anisotropic'].default_value = .33
    shader.inputs['Sheen Weight'].default_value = .038
    alpha = rgb.outputs['Alpha']
    if not optical:
        link(alpha, shader.inputs['Alpha'])
        return material

    # Compact approximation of projected ellipse coverage. It retains true holes
    # and changes the partial coverage of a vane at grazing viewpoints.
    geo = nodes.new('ShaderNodeNewGeometry')
    geo.location = (-1200, -360)
    angle = nodes.new('ShaderNodeVectorMath')
    angle.operation = 'DOT_PRODUCT'
    angle.location = (-1010, -355)
    link(geo.outputs['Incoming'], angle.inputs[0])
    link(geo.outputs['Normal'], angle.inputs[1])
    mu = math('ABSOLUTE', angle.outputs['Value'], location=(-825, -400))
    mu_sq = math('MULTIPLY', mu, mu, location=(-655, -400))
    ellipse_sq = math('MULTIPLY_ADD', mu_sq, 1 - .30 ** 2, .30 ** 2, location=(-490, -420))
    ellipse = math('SQRT', ellipse_sq, location=(-305, -420))
    foreshortening = math('MAXIMUM', mu, .105, location=(-310, -600))
    ratio = math('DIVIDE', ellipse, foreshortening, location=(-130, -420))
    exponent = math('MAXIMUM', ratio, 1, location=(25, -420))
    holes = math('SUBTRACT', 1, alpha, location=(-140, -220))
    reduced = math('POWER', holes, exponent, location=(205, -420))
    covered = math('SUBTRACT', 1, reduced, location=(385, -420))

    cross_fibers = nodes.new('ShaderNodeBsdfPrincipled')
    cross_fibers.label = 'Barbule sheen · broader lobe'
    cross_fibers.location = (615, -175)
    cross_fibers.inputs['Roughness'].default_value = .47
    cross_fibers.inputs['Specular IOR Level'].default_value = .22
    cross_fibers.inputs['Anisotropic'].default_value = .69
    cross_fibers.inputs['Anisotropic Rotation'].default_value = .141
    cross_fibers.inputs['Sheen Weight'].default_value = .16
    link(colour, cross_fibers.inputs['Base Color'])
    link(tangent.outputs[0], cross_fibers.inputs['Tangent'])
    gloss = nodes.new('ShaderNodeMixShader')
    gloss.location = (910, 390)
    link(math('MULTIPLY_ADD', mu, -.34, .42, location=(355, -214)), gloss.inputs[0])
    link(shader.outputs[0], gloss.inputs[1])
    link(cross_fibers.outputs[0], gloss.inputs[2])

    thin = nodes.new('ShaderNodeBsdfTranslucent')
    thin.location = (634, -725)
    link(colour, thin.inputs['Color'])
    scatter = nodes.new('ShaderNodeMixShader')
    scatter.location = (1100, 180)
    link(math('MULTIPLY_ADD', split.outputs['Green'], .58, .115, location=(385, -168)), scatter.inputs[0])
    link(gloss.outputs[0], scatter.inputs[1])
    link(thin.outputs[0], scatter.inputs[2])
    clear = nodes.new('ShaderNodeBsdfTransparent')
    clear.location = (920, -115)
    cutout = nodes.new('ShaderNodeMixShader')
    cutout.location = (1280, 160)
    link(covered, cutout.inputs[0])
    link(clear.outputs[0], cutout.inputs[1])
    link(scatter.outputs[0], cutout.inputs[2])
    link(cutout.outputs[0], output.inputs['Surface'])
    output.location = (1490, 160)
    return material


def place_feathers():
    """Visible resting wing ordered from the flight stack up to the mantle."""
    rng = Random(68105)
    final = []
    tip_x = (5.04, 5.44, 5.78, 6.13, 6.42, 6.66, 6.75, 6.67, 6.40)
    for i, x in enumerate(tip_x):
        u = i / 8
        root = (.56 + .12 * u, -.71 + 1.43 * u, -.048 + .034 * i)
        tip = (x, -.65 + 1.13 * u, -.26 + .043 * i)
        final.append(Vane(f'P{i + 1:02} · primary', root, tip, .68 + .132 * sin(pi * u + .3),
                          'primary', i % 2, .09 + .15 * u, -.045 + .085 * u, rng.uniform(.026, .047)))
    for i in range(9):
        u = i / 8
        root = (.14 + .36 * u, -.04 - 1.31 * u, .039 + .184 * (1 - u))
        tip = (3.27 + 2.12 * u, -1.24 - .19 * sin(pi * u) + .17 * u, -.049 + .142 * (1 - u))
        final.append(Vane(f'S{9 - i:02} · secondary', root, tip, .77 + .11 * sin(pi * u),
                          'secondary', i % 2, -.07 + .14 * u, .08 + .16 * u, rng.uniform(.028, .053)))

    def height(x, y, pad):
        return shell_height(x, y) + pad

    # Narrow transitional feathers carry the overlap through the primary-secondary seam.
    for i in range(4):
        y = -.87 + .182 * i
        x = 2.72 + .143 * i
        end_x, end_y = 4.76 + .115 * i, y + .074 + .026 * i
        root = (x, y, height(x, y, .060))
        tip = (end_x, end_y, height(end_x, end_y, .052))
        final.append(Vane(f'TC{i + 1:02} · transition covert', root, tip, .47, 'cover', i % 2,
                          .048 + .012 * i, .045, .026 + .004 * i, layer=.028 * i))

    # Tip positions are individually staggered. Both bands lie across the wing, at an angle.
    for row, count in enumerate((12, 14)):
        for i in range(count):
            u = i / (count - 1)
            y = 1.00 - 2.18 * u + rng.uniform(-.062, .067)
            x = (1.40 if row == 0 else .84) + .67 * u + rng.uniform(-.090, .073)
            tip_x = (3.49 if row == 0 else 2.36) + .73 * u + rng.uniform(-.085, .103)
            tip_y = y - (.145 if row == 0 else .118) + .19 * u + rng.uniform(-.059, .062)
            root = (x, y, height(x, y, .119 + .107 * row))
            tip = (tip_x, tip_y, height(tip_x, tip_y, .098 + .164 * row))
            final.append(Vane(f'{"GC" if row == 0 else "MC"}{i + 1:02} · covert with wing-bar tip', root, tip,
                              rng.uniform(.42, .59) if row == 0 else rng.uniform(.35, .49),
                              'cover', 2 + (i + row * 2) % 4, rng.uniform(-.092, .082),
                              rng.uniform(-.15, .22), rng.uniform(.023, .055), rng.uniform(.82, .91),
                              .021 * (i - (count - 1) / 2)))

    for row, count in enumerate((14, 15, 16, 13)):
        for i in range(count):
            u = i / (count - 1)
            y = 1.06 - 2.31 * u + rng.uniform(-.08, .06)
            x = .57 - .228 * row + .44 * u + .29 * sin(pi * u) + rng.uniform(-.071, .091)
            tip_x = x + (1.19 - .119 * row) * rng.uniform(.79, 1.15)
            tip_y = y + .24 * sin(4.4 * u + .53 * row) - .084 + rng.uniform(-.093, .082)
            root = (x, y, height(x, y, .25 + .040 * row))
            tip = (tip_x, tip_y, height(tip_x, tip_y, .16 + .041 * row))
            final.append(Vane(f'LC{row + 1}.{i + 1:02} · lesser covert', root, tip, rng.uniform(.284, .465),
                              'short', 7 if rng.random() < .19 else 6, rng.uniform(-.08, .069),
                              rng.uniform(-.22, .23), rng.uniform(.021, .059), .91 if i % 7 == 0 else 0,
                              .014 * (i - (count - 1) / 2)))

    # Wrap the proximal edge in short overlapping coverts. Offset the anchors to
    # avoid a straight cut silhouette at the shoulder attachment.
    for row, count in enumerate((14, 13, 12)):
        for i in range(count):
            u = i / (count - 1)
            y = .95 - 1.94 * u + rng.uniform(-.041, .037)
            x = -.48 + .231 * row + .29 * abs(2 * u - 1) ** 1.53 + rng.uniform(-.041, .054)
            end_x = x + rng.uniform(.52, .78)
            end_y = y * .91 + rng.uniform(-.092, .085)
            pad = .040 + .018 * row
            root = (x, y, height(x, y, pad + .10))
            end = (end_x, end_y, height(end_x, end_y, pad + .175))
            final.append(Vane(f'RC{row + 1}.{i + 1:02} · shoulder cap', root, end,
                              rng.uniform(.228, .338), 'short', 7 if rng.random() < .19 else 6,
                              rng.uniform(-.06, .056), rng.uniform(-.17, .23), rng.uniform(.025, .071),
                              layer=.013 * (i - (count - 1) / 2)))

    # The narrow leading edge curls around the shoulder and sits above the two rows.
    for side in (-1, 1):
        for i in range(26):
            u = i / 25
            x = -.32 + 3.65 * u + rng.uniform(-.07, .075)
            y = side * (1.17 - .16 * (1 - u) - .17 * u * u) + rng.uniform(-.064, .062)
            end_x = x + rng.uniform(.35, .83) * (1 + .17 * u)
            end_y = y + side * rng.uniform(-.05, .19) - rng.uniform(.027, .101)
            base = (x, y, height(x, y, .13 + .16 * (1 - u)))
            end = (end_x, end_y, height(end_x, end_y, .063 + .071 * (1 - u)))
            label = 'DL' if side < 0 else 'DR'
            final.append(Vane(f'{label}{i + 1:02} · short margin feather', base, end,
                              rng.uniform(.16, .285), 'short', 7 if i in (3, 8, 13) else 6,
                              rng.uniform(-.032, .048), rng.uniform(-.25, .23), rng.uniform(.035, .082)))
    return final


def soft_fluff(flock, group):
    rng = Random(77344)
    positions, sizes, radii, tints = [], [], [], []
    for spec in flock:
        if spec.family != 'short' or spec.root[0] > 1.64:
            continue
        start = Vector(spec.root)
        axis = Vector(spec.tip) - start
        sideways = Vector((-axis.y, axis.x, 0)).normalized()
        base_gap = spec.root[2] - shell_height(*spec.root[:2])
        tip_gap = spec.tip[2] - shell_height(*spec.tip[:2])
        for _ in range(30):
            portion = rng.uniform(.29, .85)
            wobble = rng.uniform(-.50, .5) * spec.width
            base = start + axis * portion + sideways * wobble
            base.z = shell_height(base.x, base.y) + common.mix(base_gap, tip_gap, portion)
            base.z += spec.layer + rng.uniform(-.061, -.018)
            step = axis.normalized() * rng.uniform(.055, .194) + sideways * rng.uniform(-.073, .077)
            lift = UP * rng.uniform(.022, .113)
            begin = rng.uniform(.00039, .00069)
            shade = rng.uniform(.024, .094)
            sizes.append(5)
            for q in (0., .22, .50, .75, 1.):
                positions.extend(base + step * q + lift * sin(pi * q * .83))
                radii.append(begin * (.13 + .87 * (1 - q) ** .63))
                tints.extend((1.05 * shade, shade, .91 * shade, 1))
    curves = bpy.data.hair_curves.new('Curves · sheltered shoulder down')
    curves.add_curves(sizes)
    curves.attributes['position'].data.foreach_set('vector', positions)
    radius = curves.attributes.get('radius') or curves.attributes.new('radius', 'FLOAT', 'POINT')
    radius.data.foreach_set('value', radii)
    curves.color_attributes.new('FiberTint', 'FLOAT_COLOR', 'POINT').data.foreach_set('color', tints)
    mat = bpy.data.materials.new('Down | soft hair scatter')
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    hair = nodes.new('ShaderNodeBsdfHairPrincipled')
    hair.parametrization = 'COLOR'
    hair.inputs['Roughness'].default_value = .55
    attr = nodes.new('ShaderNodeAttribute')
    attr.attribute_name = 'FiberTint'
    links.new(attr.outputs['Color'], hair.inputs['Color'])
    links.new(hair.outputs[0], nodes.get('Material Output').inputs['Surface'])
    curves.materials.append(mat)
    common.new_object('Sheltered shoulder down', curves, group)
    return len(sizes)


def studio_setup():
    scene = bpy.context.scene
    scene.frame_start = scene.frame_end = 25
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = .01
    scene.render.engine = 'CYCLES'
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 2
    scene.cycles.transparent_max_bounces = 20
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = .05
    scene.world = bpy.data.worlds.new('Workshop ambience')
    nodes, link = scene.world.node_tree.nodes, scene.world.node_tree.links.new
    ambient = nodes.get('Background')
    ambient.inputs[0].default_value = (.56, .63, .73, 1.)
    ambient.inputs[1].default_value = .21
    backdrop = nodes.new('ShaderNodeBackground')
    backdrop.inputs[0].default_value = (.027, .034, .037, 1.)
    path = nodes.new('ShaderNodeLightPath')
    mix = nodes.new('ShaderNodeMixShader')
    link(path.outputs['Is Camera Ray'], mix.inputs[0])
    link(ambient.outputs[0], mix.inputs[1])
    link(backdrop.outputs[0], mix.inputs[2])
    link(mix.outputs[0], nodes.get('World Output').inputs[0])

    group = common.collection('04 · Study cameras and lighting')
    cameras = {
        'same': common.camera('Folded dorsal | whole wing', group, (3.00, -.22, .07), (.08, -.46, 1), 8.28, -9),
        'close': common.camera('Wing bars | fixed close-up', group, (2.69, -.284, .19), (.25, -.34, 1), 4.56, -9),
        'edge': common.camera('Wing bars | low view', group, (2.79, -.25, .18), (.24, -.79, .65), 5.10, -12),
    }
    common.area('Key', group, (.96, -2.91, 4.33), (2.6, -.14, .13), 590, 3.9, (1, .942, .87))
    common.area('Skim', group, (5.0, 3.1, 2.26), (3.25, -.07, .2), 420, 2.65, (.81, .90, 1))
    common.area('Fill', group, (-2.6, 1.5, 3.9), (.92, -.29, .39), 170, 3.15, (.83, .89, 1))
    common.area('Rear', group, (4.3, 2.1, -2.2), (2.85, .14, .13), 138, 3.5, (1, .86, .73))
    return cameras


def lighting(preset):
    energies = {'studio': (590, 420, 170, 138, .21),
                'side': (108, 720, 58, 95, .13),
                'back': (42, 98, 44, 970, .063)}
    key, skim, fill, rear, ambient = energies[preset]
    for name, energy in zip(('Key', 'Skim', 'Fill', 'Rear'), (key, skim, fill, rear)):
        bpy.data.lights[name].energy = energy
    bpy.context.scene.world.node_tree.nodes.get('Background').inputs[1].default_value = ambient


def coupons(maps):
    group = common.collection('Isolated primary for material comparison')
    rig = bpy.data.collections['04 · Study cameras and lighting']
    camera = common.camera('Isolated feather | grazing and backlight test', rig,
                           (3.15, -.06, .01), (.13, -.68, .75), 7.00, -13)
    shaft = common.feather_material('Coupon | rachis', 0, .025)
    primary = Vane('P07 · isolated primary', (.02, -.05, .01), (6.15, .12, -.025),
                   1.035, 'primary', 1, .23, .12, .042)
    material = shader_photo(*maps, optical=False)
    specimen = make_vane(primary, group, material, shaft)
    for name, directional in (('photo', False), ('optics', True)):
        if directional:
            specimen.data.materials[0] = shader_photo(*maps, optical=True)
        for light in ('side', 'back'):
            lighting(light)
            common.still(camera, 25, (1200, 630), 72, ROOT / 'renders' / f'coupon-{name}-{light}.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['shape', 'photo', 'optics', 'coupon'], required=True)
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    cameras = studio_setup()
    renders = ROOT / 'renders'
    renders.mkdir(exist_ok=True)
    if not args.cpu:
        common.select_device(scene)
    if args.stage == 'coupon':
        coupons(build_photographic_atlases())
        return
    group = common.collection('02 · Rebuilt plumes in resting pose')
    carrier_group = common.collection('01 · Folded wing volume')
    support = common.new_object('Shoulder attachment', None, carrier_group)
    skin = common.basic_material('Skin shadow beneath feathering', (.017, .016, .014), .84)
    common.skin('Soft shoulder volume', [(-.28, -.005, .15, .062, .065), (-.09, -.02, .145, .57, .26),
                (.36, -.056, .151, .94, .308), (1.05, -.045, .127, .99, .265),
                (1.94, -.11, .077, .89, .20), (2.68, -.16, .024, .69, .11),
                (3.44, -.225, -.042, .23, .045), (3.84, -.27, -.065, .02, .012)],
                support, carrier_group, skin)
    shaft = common.feather_material('Feather | actual rachis geometry', 0, .025)
    if args.stage == 'shape':
        surface = common.feather_material('Feather | procedural control', 132, .087)
    else:
        albedo, relief = build_photographic_atlases()
        surface = shader_photo(albedo, relief, optical=args.stage == 'optics')
    flock = place_feathers()
    objects = [make_vane(spec, group, surface, shaft) for spec in flock]
    count = soft_fluff(flock, common.collection('03 · Shoulder down curves'))
    p_len = max(obj['Illustrated rachis length (mm)'] for obj in objects if obj['Family'] == 'primary')
    s_len = max(obj['Illustrated rachis length (mm)'] for obj in objects if obj['Family'] == 'secondary')
    print(f'{len(objects)} editable feather sheets, {count} curves; Pmax {p_len:.1f} mm, Smax {s_len:.1f} mm', flush=True)
    plain = (1320, 950)
    common.still(cameras['close'], 25, plain, 62, renders / f'{args.stage}-studio.png')
    if args.stage == 'shape':
        common.still(cameras['same'], 25, (1480, 1010), 62, renders / 'shape-whole.png')
        return
    lighting('side')
    common.still(cameras['close'], 25, plain, 72, renders / f'{args.stage}-side.png')
    lighting('back')
    common.still(cameras['edge'], 25, plain, 76, renders / f'{args.stage}-back.png')
    lighting('studio')
    common.still(cameras['same'], 25, (2080, 1380), 82, renders / f'{args.stage}-whole.png')
    if args.stage == 'optics':
        scene.render.filepath = '//renders/optics-whole.png'
        scene.cycles.device = 'CPU'
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_perspective = 'CAMERA'
                    area.spaces.active.shading.color_type = 'VERTEX'
                    area.spaces.active.overlay.show_overlays = False
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'warbler-resting-study.blend'), compress=True)


if __name__ == '__main__':
    main()
