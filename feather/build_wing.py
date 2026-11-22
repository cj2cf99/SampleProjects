"""Generate the original feather experiment in Blender 5.2.

Run headless with -- --pass field --render draft (or stills / motion).
The work is in wing units (one unit = 15 mm). +Z is dorsal, +X is distal.
"""

import argparse
from dataclasses import dataclass
from math import cos, pi, radians, sin, sqrt
from pathlib import Path
from random import Random
import sys

import bpy
from mathutils import Quaternion, Vector


ROOT = Path(__file__).resolve().parent
Z_AXIS = Vector((0, 0, 1))
X_AXIS = Vector((1, 0, 0))
ELBOW = Vector((1.06, -.38, .05))
WRIST = Vector((2.63, .21, .065))
TAU = 2 * pi


def smooth(low, high, value):
    f = min(1., max(0., (value - low) / (high - low)))
    return f * f * (3 - 2 * f)


def mix(a, b, t):
    return a + (b - a) * t


def collection(name):
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def new_object(name, data, group):
    obj = bpy.data.objects.new(name, data)
    group.objects.link(obj)
    return obj


def attach(obj, parent, position):
    bpy.context.view_layer.update()
    obj.parent = parent
    obj.location = parent.matrix_world.inverted() @ Vector(position)


def basic_material(name, color, roughness):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*color, 1)
    material.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = roughness
    return material


def feather_material(name, fibers, translucent):
    material = basic_material(name, (.085, .077, .065), .5)
    tree = material.node_tree
    nodes, link = tree.nodes, tree.links.new
    shader = nodes.get('Principled BSDF')
    shader.inputs['Specular IOR Level'].default_value = .19
    shader.inputs['Anisotropic'].default_value = .33
    shader.inputs['Sheen Weight'].default_value = .065
    shader.inputs['Sheen Roughness'].default_value = .57
    attr = nodes.new('ShaderNodeVertexColor')
    attr.layer_name = 'Pigment'
    uv = nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'Feather'
    tangent = nodes.new('ShaderNodeTangent')
    tangent.direction_type = 'UV_MAP'
    tangent.uv_map = 'Feather'
    link(tangent.outputs['Tangent'], shader.inputs['Tangent'])

    def math_node(operation, *values):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        for index, value in enumerate(values):
            if isinstance(value, (float, int)):
                node.inputs[index].default_value = value
            else:
                link(value, node.inputs[index])
        return node.outputs[0]

    color = attr.outputs['Color']
    if fibers:
        separate = nodes.new('ShaderNodeSeparateXYZ')
        link(uv.outputs[0], separate.inputs[0])
        u, v = separate.outputs[0], separate.outputs[1]
        side = math_node('ABSOLUTE', math_node('MULTIPLY_ADD', u, 2, -1))
        # Each barb sweeps towards the tip and curls further at its outer end.
        sweep = math_node('MULTIPLY_ADD', math_node('MULTIPLY', side, side), .054,
                          math_node('MULTIPLY', side, .077))
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 20
        noise.inputs['Detail'].default_value = 3
        link(uv.outputs[0], noise.inputs['Vector'])
        phase = math_node('ADD', math_node('SUBTRACT', v, sweep),
                          math_node('MULTIPLY', noise.outputs['Fac'], .009))
        ridges = math_node('SINE', math_node('MULTIPLY', phase, TAU * fibers))
        bundles = math_node('SINE', math_node('MULTIPLY', phase, TAU * (fibers / 4.71)))
        micro = math_node('SINE', math_node('MULTIPLY', phase, TAU * (fibers * 2.12)))
        relief = math_node('MULTIPLY_ADD', bundles, .30, ridges)
        relief = math_node('MULTIPLY_ADD', micro, .14, relief)
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .46
        bump.inputs['Distance'].default_value = .006
        link(relief, bump.inputs['Height'])
        link(bump.outputs[0], shader.inputs['Normal'])
        variation = math_node('MULTIPLY_ADD', noise.outputs['Fac'], .34,
                              math_node('MULTIPLY_ADD', relief, .14, .68))
        scale = nodes.new('ShaderNodeMixRGB')
        scale.blend_type = 'MULTIPLY'
        scale.inputs[0].default_value = 1.
        link(color, scale.inputs[1])
        link(variation, scale.inputs[2])
        color = scale.outputs[0]
        link(math_node('MULTIPLY_ADD', noise.outputs['Fac'], .30, .43), shader.inputs['Roughness'])

    link(color, shader.inputs['Base Color'])
    if translucent:
        thin = nodes.new('ShaderNodeBsdfTranslucent')
        link(color, thin.inputs['Color'])
        blend = nodes.new('ShaderNodeMixShader')
        blend.inputs[0].default_value = translucent
        link(shader.outputs[0], blend.inputs[1])
        link(thin.outputs[0], blend.inputs[2])
        link(blend.outputs[0], nodes.get('Material Output').inputs['Surface'])
    return material


@dataclass
class Feather:
    base: tuple
    tip: tuple
    width: float
    kind: str
    bend: float = 0.
    asymmetry: float = .49
    roll: float = 0.
    bar: float = 0.
    gray: float = .060
    curl: float = .05
    reverse: bool = False


class FeatherMesh:
    def __init__(self):
        self.vertices = []
        self.uvs = []
        self.colors = []
        self.faces = []
        self.slots = []

    def point(self, xyz, s, t, rgb):
        index = len(self.vertices)
        self.vertices.append(xyz)
        self.uvs.append(((s + 1) / 2, t))
        self.colors.extend((*rgb, 1))
        return index

    def quad(self, indices, material, reverse=False):
        self.faces.append(tuple(reversed(indices)) if reverse else indices)
        self.slots.append(material)

    def tube(self, points, rates, shades, side, start_t, end_t, slot, sides):
        start = len(self.vertices)
        for j, (position, radius, color) in enumerate(zip(points, rates, shades)):
            direction = (points[min(j + 1, len(points) - 1)] - points[max(0, j - 1)]).normalized()
            axis = side.cross(direction).normalized()
            cross = direction.cross(axis).normalized()
            for i in range(sides):
                angle = TAU * i / sides
                vertex = position + radius * (axis * cos(angle) + cross * sin(angle))
                self.point(vertex, 0, mix(start_t, end_t, j / (len(points) - 1)), color)
        for j in range(len(points) - 1):
            for i in range(sides):
                a = start + j * sides + i
                b = start + j * sides + (i + 1) % sides
                self.quad((a, b, b + sides, a + sides), slot)

    def create(self, name, group, materials):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        for material in materials:
            mesh.materials.append(material)
        for face, index in zip(mesh.polygons, self.slots):
            face.material_index = index
            face.use_smooth = True
        pigment = mesh.color_attributes.new(name='Pigment', type='FLOAT_COLOR', domain='POINT')
        pigment.data.foreach_set('color', self.colors)
        mesh.color_attributes.active_color_name = 'Pigment'
        uv = mesh.uv_layers.new(name='Feather')
        uv.uv.foreach_set('vector', [value for loop in mesh.loops for value in self.uvs[loop.vertex_index]])
        return new_object(name, mesh, group)


def make_feather(name, spec, group, joint, materials, rng, detail):
    mesh = FeatherMesh()
    delta = Vector(spec.tip) - Vector(spec.base)
    length = delta.length
    sideways = Vector((delta.y, -delta.x, 0)).normalized()
    sign = -1 if spec.reverse else 1
    phase = rng.uniform(0, TAU)
    primary = spec.kind == 'primary'
    long = spec.kind in {'primary', 'secondary', 'tertial'}
    tip_length = .20 if primary else (.24 if long else .32)
    tip_length *= rng.uniform(.73, 1.24)
    cuts = [(rng.uniform(.43, .95), rng.uniform(.014, .074), rng.choice([-1, 1]))
            for _ in range(4 if detail and long else 0)]

    def center(t):
        return delta * t + sideways * (spec.bend * sin(pi * t)) + sign * Z_AXIS * (spec.curl * sin(pi * t))

    def position(t, s):
        expansion = .07 + .93 * smooth(.015, .33, t)
        taper = sqrt(max(.000013, 1 - max(0, (t - (1 - tip_length)) / tip_length) ** 2))
        bias = spec.asymmetry if s > 0 else 1 - spec.asymmetry
        w = spec.width * bias * expansion * taper
        w *= 1 + .044 * sin(t * 19 + phase) + .025 * sin(t * 43 - phase)
        if detail:
            w *= 1 + (.017 * sin(t * 496 + 3 * phase) + .009 * sin(t * 817)) * abs(s) ** 8
            for notch, depth, side in cuts:
                if side * s > 0:
                    w *= 1 - depth * max(0., 1. - abs(t - notch) / .017) * abs(s) ** 5
            if primary and s > 0 and spec.asymmetry < .43:
                w *= 1 - .23 * smooth(.55, .67, t)
        tip_skew = (.009 + .007 * sin(phase) + .008 * s * cos(phase)) * s * s
        tip_skew *= smooth(.62, .99, t) * min(length, 1.8)
        camber = -.15 * spec.width * s * s + spec.roll * s * sin(pi * t)
        camber *= expansion * taper
        return center(t) + sideways * (w * s) + sign * Z_AXIS * camber - delta.normalized() * tip_skew

    def pigment(t, s):
        fringe = smooth(.71, 1.07, abs(s)) * (1. if s > 0 else .51)
        border = spec.bar + .05 * s + .036 * sin(5 * s + phase) + .024 * sin(17 * s + phase)
        border += .012 * sin(42 * s - 2 * phase)
        light = smooth(border - .024, border + .029, t) if spec.bar > 0 else 0.
        mottling = .17 * sin(t * 91 + 3 * s + phase) + .075 * sin(t * 244 - 15 * s + phase)
        gray = spec.gray * (1 + mottling + .46 * fringe - .12 * s) + .004 * t * t
        if detail:
            dull = smooth(.85, 1.02, t) * (.004 + .015 * abs(s))
            use_worn_margin = .4 + .6 * smooth(-.9, .75, cos(phase))
            weathering = .038 * use_worn_margin * fringe ** 2 * smooth(.20, .75, t)
            gray += dull + weathering + .012 * (sin(t * 166 + s * 5 + phase) ** 6) * fringe
        if not spec.reverse:
            gray *= .52 if long else .46
        warmth = .945 - .066 * s + .084 * sin(phase)
        white = .53 + .13 * cos(phase) + .08 * mottling
        return (mix(gray * 1.055, white * 1.05, light),
                mix(gray * .99, white, light),
                mix(gray * warmth, white * .89, light))

    segments = (112 if long else 60) if detail else (48 if long else 28)
    columns = 12 if long else 8
    for j in range(segments + 1):
        t = j / segments
        for i in range(columns + 1):
            s = 2 * i / columns - 1
            mesh.point(position(t, s), s, t, pigment(t, s))
    stride = columns + 1
    for j in range(segments):
        for i in range(columns):
            a = j * stride + i
            mesh.quad((a, a + 1, a + stride + 1, a + stride), 0, spec.reverse)

    # The rachis is a tapered solid. Its diffuse color changes with the vane.
    t_values = [i * .981 / 27 for i in range(28)]
    radii = [(spec.width * (.032 if long else .019)) * (1 - t) ** 1.11 + .00020 for t in t_values]
    shaft = [center(t) + Z_AXIS * sign * radius * .27 for t, radius in zip(t_values, radii)]
    shaft_colors = [tuple(c * (.75 + .40 * (1 - t)) + (.011 if long else .003) * (1 - t)
                          for c in pigment(t, .02)) for t in t_values]
    mesh.tube(shaft, radii, shaft_colors, sideways, 0, .981, 1, 7)

    if detail:
        # A few actual barb tips break the contour; densely packed barbs stay in the shader.
        for _ in range(82 if long else (35 if spec.kind == 'down' else 20)):
            t = rng.uniform(.18 if long else .28, .971)
            s = rng.choice([-1, 1])
            separation = rng.uniform(.007, .051) * (.55 + .45 * t)
            middle = min(.991, t + separation)
            extension = rng.uniform(.004, .066)
            extension *= 1.38 if spec.kind in {'down', 'shoulder'} else .86
            start = position(t, s * .84)
            edge = position(middle, s * .997)
            end = edge + s * sideways * extension + delta.normalized() * extension * rng.uniform(.32, .95)
            end += Z_AXIS * sign * extension * rng.uniform(-.29, .62 if spec.kind == 'down' else .30)
            tint = tuple(c * rng.uniform(.76, 1.20) for c in pigment(middle, s))
            diameter = rng.uniform(.00037, .00134) * min(1.12, .66 + spec.width)
            mesh.tube((start, edge, end), (diameter, diameter * .72, diameter * .055),
                      (tint, tint, tint), sideways, t, middle, 1, 4)

    obj = mesh.create(name, group, materials)
    attach(obj, joint, spec.base)
    if long and detail:
        obj.shape_key_add(name='Basis')
        flex = obj.shape_key_add(name='Vane and shaft flex')
        for point, (_, t) in zip(flex.data, mesh.uvs):
            point.co.z += .091 * length * t ** 2.15
            point.co += sideways * (.024 * length * t ** 2.7)
        flex.slider_min = -1
        flex.slider_max = 1
    return obj


def skin(name, sections, joint, group, material):
    vertices, faces = [], []
    sides = 36
    for x, y, z, width, height in sections:
        for i in range(sides):
            p = TAU * i / sides
            vertices.append((x, y + width * cos(p), z + height * sin(p)))
    faces.append(tuple(reversed(range(sides))))
    for section in range(len(sections) - 1):
        for i in range(sides):
            a = section * sides + i
            b = section * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple(range(len(vertices) - sides, len(vertices))))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(material)
    for face in mesh.polygons:
        face.use_smooth = True
    obj = new_object(name, mesh, group)
    attach(obj, joint, (0, 0, 0))
    subdiv = obj.modifiers.new('Smooth airfoil', 'SUBSURF')
    subdiv.levels = 2
    return obj


def make_wing(mode):
    detail = mode == 'field'
    rng = Random(512921)
    # Reserve separate random streams for geometry and layout so material tests are comparable.
    geometry_rng = Random(54019)
    rig_group = collection('01 · Wing articulation')
    flights = collection('02 · Remiges and alula')
    upper = collection('03 · Dorsal coverts')
    lower = collection('04 · Ventral coverts')
    studio = collection('05 · Cameras and lights')
    shoulder = new_object('Shoulder · flap and pitch', None, rig_group)
    elbow = new_object('Elbow · forearm', None, rig_group)
    wrist = new_object('Wrist · hand wing', None, rig_group)
    attach(elbow, shoulder, ELBOW)
    attach(wrist, elbow, WRIST)
    for control in (shoulder, elbow, wrist):
        control.empty_display_type = 'CIRCLE'
        control.empty_display_size = .17

    vane = feather_material('Feather | striated keratin vanes', 142 if detail else 0, .105)
    fine_vane = feather_material('Feather | fine covert vanes', 96 if detail else 0, .073)
    shaft = feather_material('Feather | rachis and free barb tips', 0, .033)
    skin_mat = basic_material('Subsurface | charcoal downbed', (.034, .029, .024), .89)
    skin('Shoulder airfoil', [(-.28, -.035, .135, .045, .05), (-.14, -.1, .115, .40, .229),
                            (.17, -.11, .095, .59, .228), (.65, -.11, .06, .49, .175),
                            (1.12, -.08, .048, .34, .12), (1.44, -.075, .035, .024, .032)],
         shoulder, rig_group, skin_mat)
    skin('Forearm airfoil', [(.66, -.12, .062, .08, .034), (.93, -.095, .052, .24, .128),
                           (1.47, -.03, .06, .269, .126), (2.01, .10, .07, .248, .111),
                           (2.62, .26, .071, .223, .088), (2.91, .295, .056, .04, .028)],
         elbow, rig_group, skin_mat)
    skin('Hand airfoil', [(2.48, .23, .07, .075, .034), (2.70, .28, .07, .181, .091),
                         (3.04, .345, .069, .157, .072), (3.37, .38, .049, .13, .051),
                         (3.66, .41, .032, .018, .015)], wrist, rig_group, skin_mat)

    def add(name, spec, group, joint):
        material = vane if spec.kind in {'primary', 'secondary', 'tertial'} else fine_vane
        return make_feather(name, spec, group, joint, (material, shaft), geometry_rng, detail)

    animated = []
    primary_tips = [(2.98, -2.19), (3.43, -2.13), (3.88, -1.99), (4.34, -1.78),
                    (4.80, -1.52), (5.24, -1.23), (5.63, -.88), (5.89, -.48), (5.70, -.04)]
    for i, (x, y) in enumerate(primary_tips):
        u = i / 8
        b = (2.55 + .82 * u, .08 + .30 * u, -.045 + .018 * i)
        spec = Feather(b, (x, y, -.27 + .042 * i),
                       .54 - .17 * u + rng.uniform(-.018, .018), 'primary',
                       .031 + .12 * u, .48 - .145 * u, .021 - .011 * u,
                       gray=rng.uniform(.040, .072), curl=.091 + .031 * u)
        obj = add(f'P{i + 1:02} · primary', spec, flights, wrist)
        animated.append((obj, 'primary', u))
        for layer in range(2):
            reach = (.51 if layer == 0 else .275) + rng.uniform(-.042, .031)
            base = (b[0] + .032, b[1] + .074 + layer * .087, b[2] + .118 + .042 * layer)
            endpoint = (mix(base[0], x, reach), mix(base[1], y, reach), b[2] + .062 + layer * .063)
            covert = add(f'PC{layer + 1}.{i + 1:02} · hand covert',
                         Feather(base, endpoint, .324 - .049 * layer - .064 * u, 'covert',
                                 .065, .42, .019, gray=rng.uniform(.040, .095)), upper, wrist)
            animated.append((covert, 'primary covert', u))

    for i in range(9):
        u = i / 8
        x = .27 + 2.17 * u
        y = -.35 + .43 * u ** 1.65
        tip = (x + .12 + .076 * u, -1.15 - 1.04 * sin(1.55 * u) ** .82, -.19 + .095 * u)
        b = (x, y, -.072 + .029 * u)
        joint = shoulder if i < 3 else elbow
        obj = add(f'S{i + 1:02} · {"tertial" if i < 3 else "secondary"}',
                  Feather(b, tip, .47 + .044 * u, 'tertial' if i < 3 else 'secondary',
                          -.035 + .084 * u, .53, -.023, gray=rng.uniform(.050, .089)), flights, joint)
        animated.append((obj, 'secondary', u))

    for row, count in enumerate((12, 14, 16, 18, 17)):
        for i in range(count):
            u = i / (count - 1)
            x = -.13 + (2.63 + .34 * (row / 4)) * u + rng.uniform(-.061, .061)
            baseline = (-.40, -.22, -.052, .092, .18)[row]
            y = baseline + .45 * u ** 1.68 + rng.uniform(-.057, .052)
            height = (.089, .194, .255, .271, .248)[row] + .074 * (1 - u)
            height += rng.uniform(-.019, .023)
            length = (.91, .665, .446, .353, .267)[row] * rng.uniform(.85, 1.14)
            dx = (.10 + .31 * u) * (1. + .10 * row) + rng.uniform(-.07, .10)
            pale = 0.
            if row < 2:
                pale = (.716 if row == 0 else .689) + rng.uniform(-.072, .15) + .22 * smooth(.75, 1.04, u)
            if row >= 2 and rng.random() < .11 + .31 * (1 - u):
                pale = rng.uniform(.69, .96)
            kind = 'shoulder' if row > 1 and u < .50 else 'covert'
            joint = shoulder if x < 1.01 else (elbow if x < 2.60 else wrist)
            add(f'C{row + 1}.{i + 1:02} · {("greater", "median", "lesser", "marginal", "leading")[row]}',
                Feather((x, y, height), (x + dx, y - length, height - (.14 - .021 * row)),
                        (.377, .318, .262, .218, .22)[row] * rng.uniform(.81, 1.20), kind,
                        rng.uniform(-.053, .058), rng.uniform(.41, .59), rng.uniform(-.049, .044),
                        pale, rng.uniform(.038, .106), rng.uniform(.021, .060)), upper, joint)

    for row, count in enumerate((32, 29, 22, 15)):
        for i in range(count):
            u = i / (count - 1)
            x = -.252 + (2.64 - .35 * row) * u + rng.uniform(-.036, .036)
            leading_edge = .410 + .16 * u - .144 * sin(pi * u) ** 1.25
            leading_edge -= .23 * (1 - smooth(.005, .13, u))
            y = leading_edge - .080 * row + rng.uniform(-.037, .033)
            z = (.18, .25, .318, .354)[row] + .052 * (1 - u) + rng.uniform(-.018, .016)
            length = rng.uniform(.134, .259) + .045 * row
            draw = .12 + .08 * u + rng.uniform(-.08, .065)
            width = rng.uniform(.078, .139) + .015 * row
            pale = rng.uniform(.57, .96) if rng.random() < .32 - .07 * u else 0.
            joint = shoulder if x < .96 else elbow
            add(f'D{row + 1}.{i + 1:02} · marginal plumage',
                Feather((x, y, z), (x + draw, y - length, z - (.015 + .012 * row)),
                        width, 'down', rng.uniform(-.035, .035), .50, rng.uniform(-.02, .021),
                        pale, rng.uniform(.030, .110), .019), upper, joint)

    for i in range(4):
        x = 2.66 + i * .10
        add(f'A{i + 1:02} · alula', Feather((x, .43 - .023 * i, .217 - .014 * i),
                                            (x + .73 - .066 * i, .56 - .102 * i, .127 - .006 * i),
                                            .196, 'covert', .039, .54, .033, gray=.055 + .013 * i), upper, wrist)

    for row, count in enumerate((13, 16, 17)):
        for i in range(count):
            u = i / (count - 1)
            x = -.14 + (3.32 + .25 * (1 - row / 2)) * u + rng.uniform(-.05, .053)
            y = (-.35, -.10, .13)[row] + .46 * u ** 1.31 + rng.uniform(-.049, .052)
            z = (-.124, -.173, -.109)[row] + .061 * u + rng.uniform(-.012, .01)
            length = (.75, .54, .39)[row] * rng.uniform(.80, 1.17)
            dx = .068 + .65 * u ** 2 + rng.uniform(-.06, .08)
            joint = shoulder if x < 1.01 else (elbow if x < 2.60 else wrist)
            add(f'U{row + 1}.{i + 1:02} · underwing covert',
                Feather((x, y, z), (x + dx, y - length, z + .042),
                        (.30, .243, .218)[row] * rng.uniform(.88, 1.17), 'covert',
                        rng.uniform(-.042, .03), .52, .028, rng.uniform(.72, .96),
                        rng.uniform(.13, .28) * (1 - .68 * u ** 2), .041, True), lower, joint)

    for row, count in enumerate((15, 13, 10)):
        for i in range(count):
            u = i / (count - 1)
            x = -.18 + (.94 + .08 * row) * u + rng.uniform(-.027, .027)
            y = (.446, .366, .274)[row] - .09 * u
            y -= .23 * (1 - smooth(0, .31, u))
            y += rng.uniform(-.025, .022)
            height = (-.048, -.105, -.145)[row] + rng.uniform(-.012, .008)
            tip = (x + rng.uniform(.058, .123), y - rng.uniform(.155, .224), height - .037)
            pale = rng.uniform(.61, .95) if rng.random() < .53 else 0.
            add(f'R{row + 1}.{i + 1:02} · ventral root plumage',
                Feather((x, y, height), tip, rng.uniform(.092, .148), 'down',
                        rng.uniform(-.03, .027), .49, .017, pale,
                        rng.uniform(.09, .175), .019, True), lower, shoulder)

    animate(shoulder, elbow, wrist, animated)
    return studio


def animate(shoulder, elbow, wrist, feathers):
    # One deliberate slow-motion cycle for judging visible feather mechanics.
    # Rotation triples are local XYZ in degrees.
    poses = [
        (1,  'Folded',        (8, 0, -12), (7, -5, -12), (-10, -12, -38),  .35,  -.06),
        (14, 'Unfold',      (-7, -18, -5), (4, -9, -5),  (-7, -12, -17),  .14,   .17),
        (25, 'Dorsal / glide', (0, 0, 0),     (0, 0, 0),      (0, 0, 0),     0,    0),
        (37, 'Upstroke',    (-12, -26, 8), (1, -12, -5), (-9, -16, -7),   .09,  -.28),
        (45, 'Top recovery', (-9, -37, 7), (4, -6, -6),   (5, -3, 1),    .03,  -.03),
        (55, 'Downstroke',  (12, 27, -6),  (-2, 14, -3),  (8, 12, -2),   .025,  .46),
        (67, 'Glide',        (2, -2, 0),   (1, 2, -1),    (1, 2, 1),     .01,  -.12),
        (77, 'Retract',      (6, 6, -7),    (5, -3, -7),   (-6, -6, -19), .19,   .16),
        (91, '',             (8, 0, -12), (7, -5, -12), (-10, -12, -38),  .35,  -.06),
    ]
    for frame, label, humerus, forearm, hand, fold, flex in poses:
        if label:
            bpy.context.scene.timeline_markers.new(label, frame=frame)
        for joint, angles in zip((shoulder, elbow, wrist), (humerus, forearm, hand)):
            joint.rotation_euler = tuple(radians(v) for v in angles)
            joint.keyframe_insert(data_path='rotation_euler', frame=frame)
        for obj, kind, u in feathers:
            flight = kind == 'primary'
            sweep = fold * (u - .54) * (-39 if flight else -21)
            if kind == 'secondary':
                sweep = -fold * (5 + 10 * u)
            obj.rotation_euler = (radians(1.8 * flex * (u + .3)),
                                  radians((5.5 if flight else 2.5) * flex * (u + .3)), radians(sweep))
            obj.keyframe_insert(data_path='rotation_euler', frame=frame)
            if obj.data.shape_keys:
                blade = obj.data.shape_keys.key_blocks['Vane and shaft flex']
                blade.value = flex * (.48 + u * .50)
                blade.keyframe_insert(data_path='value', frame=frame)


def camera(name, group, target, direction, scale, roll):
    data = bpy.data.cameras.new(name)
    data.type = 'ORTHO'
    data.ortho_scale = scale
    obj = new_object(name, data, group)
    obj.location = Vector(target) + Vector(direction).normalized() * 14
    obj.rotation_euler = ((Vector(target) - obj.location).to_track_quat('-Z', 'Y') @
                          Quaternion(Z_AXIS, radians(roll))).to_euler()
    return obj


def fit_camera(obj, subjects, frames, aspect, padding):
    """Fit one orthographic framing to projected, evaluated bounds across poses."""
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    rotation = obj.rotation_euler.to_matrix()
    to_view = rotation.transposed()
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for frame in frames:
        scene.frame_set(frame)
        for subject in subjects:
            evaluated = subject.evaluated_get(depsgraph)
            into_view = to_view @ evaluated.matrix_world.to_3x3()
            origin = to_view @ (evaluated.matrix_world.translation - obj.location)
            for corner in evaluated.bound_box:
                point = into_view @ Vector(corner) + origin
                min_x, max_x = min(min_x, point.x), max(max_x, point.x)
                min_y, max_y = min(min_y, point.y), max(max_y, point.y)
    obj.location += rotation @ Vector(((min_x + max_x) / 2, (min_y + max_y) / 2, 0))
    obj.data.ortho_scale = padding * max(max_x - min_x, aspect * (max_y - min_y))
    print(f'{obj.name}: margins fit over {len(frames)} frames, scale {obj.data.ortho_scale:.2f}', flush=True)


def area(name, group, location, target, energy, size, color):
    light = bpy.data.lights.new(name, 'AREA')
    light.energy = energy
    light.shape = 'DISK'
    light.size = size
    light.color = color
    obj = new_object(name, light, group)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def light_and_frame(studio):
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = .015
    scene.frame_start, scene.frame_end = 1, 90
    scene.render.fps = 24
    scene.world = bpy.data.worlds.new('Soft ambient sky')
    world_nodes = scene.world.node_tree.nodes
    world_links = scene.world.node_tree.links
    bg = world_nodes.get('Background')
    bg.inputs[0].default_value = (.245, .30, .38, 1)
    bg.inputs[1].default_value = .22
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.engine = 'CYCLES'
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 5
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.cycles.transparent_max_bounces = 4
    # A camera-only studio color prevents the background from tinting the feathers.
    camera_bg = world_nodes.new('ShaderNodeBackground')
    camera_bg.inputs[0].default_value = (.034, .049, .054, 1)
    path = world_nodes.new('ShaderNodeLightPath')
    background = world_nodes.new('ShaderNodeMixShader')
    world_links.new(path.outputs['Is Camera Ray'], background.inputs[0])
    world_links.new(bg.outputs[0], background.inputs[1])
    world_links.new(camera_bg.outputs[0], background.inputs[2])
    world_links.new(background.outputs[0], world_nodes.get('World Output').inputs['Surface'])

    area('Key · warm large softbox', studio, (1.1, -3.9, 5.5), (2, -.4, 0), 680, 5.1, (1, .953, .885))
    area('Rim · cool grazing light', studio, (4.9, 2.5, 2.9), (2.8, -.35, 0), 470, 3.4, (.755, .875, 1))
    area('Fill · shoulder', studio, (-2.6, 1.4, 2.9), (1.2, -.2, 0), 255, 3.8, (.92, .965, 1))
    area('Fill · underside', studio, (2.6, -3.2, -4.1), (2.5, -.3, 0), 570, 4.8, (.83, .91, 1))
    cameras = {
        'dorsal': camera('Dorsal · full wing', studio, (2.78, -.62, .04), (.16, -.40, 1), 7.54, -14),
        'macro': camera('Macro · greater coverts and barbs', studio, (1.76, -.89, .09), (.37, -.48, 1), 2.40, -19),
        'ventral': camera('Ventral · full wing', studio, (2.78, -.61, 0), (.13, -.32, -1), 7.45, -9),
        'motion': camera('Motion · three-quarter', studio, (2.70, -.46, -.08), (.12, -.53, 1), 7.8, -12),
        'folded': camera('Folded · study', studio, (2.4, -1.5, 0), (.27, -.45, 1), 6.5, -20),
    }
    scene.camera = cameras['dorsal']
    for screen in bpy.data.screens:
        for zone in screen.areas:
            if zone.type == 'VIEW_3D':
                zone.spaces.active.region_3d.view_perspective = 'CAMERA'
                zone.spaces.active.shading.color_type = 'VERTEX'
                zone.spaces.active.shading.show_cavity = True
                zone.spaces.active.overlay.show_overlays = False
    return cameras


def select_device(scene):
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA', 'HIP'):
        try:
            prefs.compute_device_type = backend
            prefs.refresh_devices()
            gpu = [device for device in prefs.devices if device.type == backend]
            if gpu:
                for device in prefs.devices:
                    device.use = device in gpu
                scene.cycles.device = 'GPU'
                print('CYCLES DEVICE', backend, [device.name for device in gpu], flush=True)
                return
        except (RuntimeError, TypeError):
            continue
    print('CYCLES DEVICE CPU', flush=True)


def still(camera_obj, frame, resolution, samples, file):
    scene = bpy.context.scene
    scene.camera = camera_obj
    scene.frame_set(frame)
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = str(file)
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pass', dest='mode', choices=['blockout', 'field'], default='field')
    parser.add_argument('--render', choices=['no', 'draft', 'poses', 'stills', 'motion', 'all'], default='no')
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    (ROOT / 'renders').mkdir(exist_ok=True)
    (ROOT / 'iterations').mkdir(exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    studio = make_wing(args.mode)
    cameras = light_and_frame(studio)
    scene = bpy.context.scene
    subjects = [obj for obj in scene.objects if obj.type == 'MESH']
    print(f'{len(subjects) - 3} feather meshes, {sum(len(obj.data.polygons) for obj in subjects):,} mesh faces', flush=True)
    if args.render != 'draft':
        fit_camera(cameras['motion'], subjects, range(1, 91), 1200 / 768, 1.14)
        fit_camera(cameras['folded'], subjects, [1], 1600 / 1200, 1.19)
    scene.frame_set(25)
    scene.cycles.samples = 80
    scene.render.resolution_x, scene.render.resolution_y = 2240, 1440
    scene.render.resolution_percentage = 100
    scene.render.filepath = '//renders/dorsal.png'
    if args.mode == 'field' and args.render in {'no', 'stills', 'all'}:
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'warbler-wing.blend'), compress=True)
    if not args.cpu and args.render != 'no':
        select_device(scene)
    if args.render == 'draft':
        still(cameras['dorsal'], 25, (1120, 720), 19, ROOT / 'iterations' / f'{args.mode}-dorsal.png')
        still(cameras['macro'], 25, (960, 720), 20, ROOT / 'iterations' / f'{args.mode}-macro.png')
    if args.render == 'poses':
        still(cameras['dorsal'], 25, (1120, 720), 25, ROOT / 'iterations' / 'refined-dorsal.png')
        for frame in (1, 37, 55, 76):
            still(cameras['motion'], frame, (1000, 720), 18, ROOT / 'iterations' / f'pose-{frame:02}.png')
    if args.render in {'stills', 'all'}:
        still(cameras['dorsal'], 25, (2240, 1440), 72, ROOT / 'renders' / 'dorsal.png')
        still(cameras['macro'], 25, (1920, 1440), 88, ROOT / 'renders' / 'macro.png')
        still(cameras['ventral'], 25, (1760, 1120), 56, ROOT / 'renders' / 'ventral.png')
        still(cameras['folded'], 1, (1600, 1200), 54, ROOT / 'renders' / 'folded.png')
    if args.render in {'motion', 'all'}:
        scene.camera = cameras['motion']
        scene.render.resolution_x, scene.render.resolution_y = 1200, 768
        scene.cycles.samples = 16
        scene.cycles.adaptive_threshold = .065
        scene.cycles.adaptive_min_samples = 6
        scene.render.use_persistent_data = True
        scene.render.image_settings.media_type = 'VIDEO'
        scene.render.image_settings.file_format = 'FFMPEG'
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'
        scene.render.ffmpeg.constant_rate_factor = 'HIGH'
        scene.render.filepath = str(ROOT / 'renders' / 'motion-render-')
        bpy.ops.render.render(animation=True)
        video = ROOT / 'renders' / f'motion-render-{scene.frame_start:04}-{scene.frame_end:04}.mp4'
        video.replace(ROOT / 'renders' / 'motion.mp4')


if __name__ == '__main__':
    main()
