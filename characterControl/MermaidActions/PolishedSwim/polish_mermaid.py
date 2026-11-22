"""Five cumulative animation and look-development passes for Mermaid Graceful Swim."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(folder) for folder in (HERE, HERE.parent, HERE.parent / "GracefulSwim", HERE.parent / "ColoredSwim")]
from animate_mermaid import BACK, FPS, RIGHT, SECTIONS, TAU, UP, body_rotation, direction, route
from mermaid_glide import GlideSwimmer, arm_pose, ease, solve_arm
from recolor_mermaid import attr, blend, color_surface, field, math_node, ramp, rgb, smooth


def samples():
    frame = 1
    for shot, (_, count) in enumerate(SECTIONS):
        for index in range(count):
            yield shot, index, count, frame
            frame += 1


def pace(shot, t):
    if shot < 2:
        return t - .075 * math.sin(TAU * t) / TAU
    return t


def swim_orientation(shot, t, phase):
    if shot == 0:
        roll = -.96 + .29 * math.sin(TAU * t + .22) - .09 * math.sin(2 * TAU * t - .15)
        return body_rotation(direction(shot, pace(shot, t)), roll)
    if shot == 1:
        turns = t - .29 * math.sin(TAU * t) / TAU
        return body_rotation(direction(shot, pace(shot, t)), -1.04 + TAU * turns)
    return (Quaternion((0, 0, 1), .23 + .075 * math.sin(TAU * t))
            @ Quaternion((1, 0, 0), .019 * math.sin(phase - .38))
            @ Quaternion((0, 1, 0), .017 * math.cos(phase - .58)))


class PolishSwimmer(GlideSwimmer):
    def __init__(self):
        super().__init__()
        self.pivot = Vector((0, .017, 1.062))
        self.tail = ("tail", "tail.001", "tail.002", "tail.003", "tail.004")
        points = [self.bones[name].bone.head_local.copy() for name in self.tail]
        points.append(self.bones[self.tail[-1]].bone.tail_local.copy())
        self.segments = [end - start for start, end in zip(points, points[1:])]
        total_length = sum(segment.length for segment in self.segments)
        self.stations = [0.]
        for segment in self.segments:
            self.stations.append(self.stations[-1] + segment.length / total_length)
        keys = bpy.data.objects["mermaid"].data.shape_keys.key_blocks
        self.fin = keys["Fin membrane flex"]
        self.fan = keys["Fin spread and unload"]

    def paddle(self, shot, t, speed, phase, frame):
        # Curvature grows along the tail with a quieter hinge at the waist.
        amplitude = (.292 + .045 * speed, .315, .25)[shot]
        amplitude *= 1 + .115 * math.sin(TAU * t + .22)
        bank = (.084, .072, .017)[shot] * math.sin(TAU * t + .28)
        bias = (.078, .058, .155)[shot]
        lateral = (.42, .50, .62)[shot]
        travel = 4.03 if shot < 2 else 3.78
        offsets = []
        for station in self.stations:
            wave = phase - travel * station
            envelope = amplitude * (.09 * station + .91 * station**2.02)
            lateral_offset = lateral * envelope * math.sin(wave + .65) + bank * station**2
            bend = bias * station**2 + envelope * (math.sin(wave) + .075 * math.sin(2 * wave - .6))
            offsets.append(Vector((lateral_offset, bend, 0)))

        parent = self.bones[self.tail[0]].parent.matrix.to_quaternion()
        for index, (name, segment) in enumerate(zip(self.tail, self.segments)):
            forward = (segment + offsets[index + 1] - offsets[index]).normalized()
            neutral = parent @ self.rest[self.bones[name].parent.name].inverted() @ self.rest[name]
            twist = .049 * self.stations[index + 1] * math.cos(phase - 3.0)
            absolute = Quaternion(forward, twist) @ segment.rotation_difference(forward) @ self.rest[name]
            self.bone_key(name, neutral.inverted() @ absolute, frame)
            parent = absolute

        delayed = phase - travel - .56
        self.fin.value = .53 * math.sin(delayed) + .08 * math.sin(2 * delayed - .38)
        self.fan.value = .21 + .38 * math.cos(delayed - .22) - .08 * math.cos(TAU * t)
        for shape in (self.fin, self.fan):
            shape.keyframe_insert(data_path="value", frame=frame, group="Fin membrane")


def refine_swimming(scene, swimmer):
    previous = None
    for shot, index, count, frame in samples():
        scene.frame_set(frame)
        t = index / (count - 1)
        u = pace(shot, t)
        speed = (route(shot, pace(shot, t + .002)) - route(shot, pace(shot, t - .002))).length / (.004 * (count - 1) / FPS)
        if index == 0:
            phase = (.57, 1.45, 1.88)[shot]
        else:
            rates = (.73 + .34 * speed, .74 + .29 * speed, .72 + .071 * math.sin(TAU * t + .25))
            phase += TAU * rates[shot] / FPS
        orientation = swim_orientation(shot, t, phase)
        if previous is not None:
            orientation.make_compatible(previous)
        previous = orientation.copy()
        rig = swimmer.rig
        rig.rotation_quaternion = orientation
        rig.location = route(shot, u) - orientation @ swimmer.pivot
        rig.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="Swim trajectory")
        rig.keyframe_insert(data_path="location", frame=frame, group="Swim trajectory")
        swimmer.paddle(shot, t, speed, phase, frame)


def pulse(seconds, start, peak, finish):
    return ease((seconds - start) / (peak - start)) * (1 - ease((seconds - peak) / (finish - peak)))


def upper_pose(swimmer, shot, t, seconds, frame):
    if shot == 0:
        dive = pulse(seconds, 0, .94, 2.52)
        rise = pulse(seconds, 2.48, 3.67, 5.40)
        swivel = .070 * dive - .074 * rise
        swimmer.bend("chest", frame, .033 * dive - .045 * rise, .021 * (dive + rise), swivel)
        swimmer.bend("head", frame, -.181 - .042 * dive + .069 * rise, -.30 * swivel, -.64 * swivel)
    elif shot == 1:
        lead = pulse(t, .06, .38, .89)
        bank = .034 * math.sin(TAU * t)
        swimmer.bend("chest", frame, -.025 * lead, .026 * lead, bank)
        swimmer.bend("head", frame, -.171 - .047 * lead, -.018 * lead, -.52 * bank + .025 * lead)
    else:
        drift = TAU * .23 * seconds
        swimmer.bend("chest", frame, .011 * math.cos(drift), .013 * math.sin(drift + .4), .013 * math.cos(drift + .7))
        swimmer.bend("head", frame, -.027 + .018 * math.sin(drift + .38), .017 * math.cos(drift + .3), .051 * math.sin(drift))


def finger_pose(swimmer, side, openness, frame):
    for finger, rest_curl in (("f_index", .10), ("f_middle", .15), ("f_ring", .20), ("f_pinky", .25)):
        for joint, weight in (("01", 1.), ("02", .69)):
            name = f"{finger}.{joint}.{side}"
            rest = swimmer.rest[name]
            axis = rest.inverted() @ (rest @ BACK).cross(-UP).normalized()
            curl = rest_curl * weight * (1.13 - .49 * openness)
            swimmer.bone_key(name, Quaternion(axis, curl), frame)


def refine_gestures(scene, swimmer):
    for shot, index, count, frame in samples():
        scene.frame_set(frame)
        t, seconds = index / (count - 1), index / FPS
        upper_pose(swimmer, shot, t, seconds, frame)
        bpy.context.view_layer.update()

        arm_time = seconds - .22 * pulse(seconds, 0, .8, 2.4) if shot == 0 else seconds
        forearms = []
        for sign, side in ((1, "L"), (-1, "R")):
            wrist, elbow, pitch, roll = arm_pose(shot, t, arm_time, sign)
            # Use a stable lateral pole through the reach so the elbow does not
            # twist rapidly as the current wrist direction approaches the guide.
            stable_pole = Vector((.80 * sign, .49, -.21))
            elbow = elbow.normalized().lerp(stable_pole, .50 if shot < 2 else .25)
            reach = ease((wrist.z + .27) / .50)
            wrist.x += sign * .015 * (1 - reach)
            wrist.y -= .010
            upper, lower = f"upper_arm_fk.{side}", f"forearm_fk.{side}"
            upper_vector, lower_vector = solve_arm(wrist, elbow, swimmer.bones[upper].length, swimmer.bones[lower].length)
            swimmer.aim(upper, upper_vector, frame)
            forearms.append((side, lower, lower_vector, pitch, roll, reach))

        bpy.context.view_layer.update()
        for side, lower, vector, pitch, roll, reach in forearms:
            swimmer.aim(lower, vector, frame)
            wrist_rotation = Quaternion(BACK, roll * .83) @ Quaternion(RIGHT, pitch + .052 * (1 - reach))
            swimmer.bone_key(f"hand_fk.{side}", wrist_rotation, frame)
            if index % 3 == 0 or index == count - 1:
                finger_pose(swimmer, side, reach, frame)


def restore_iris():
    material = bpy.data.materials.new("Pearl teal iris")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    surface = nodes.get("Principled BSDF")
    surface.inputs["Roughness"].default_value = .34
    surface.inputs["Specular IOR Level"].default_value = .22
    surface.inputs["Emission Strength"].default_value = .12
    generated = nodes.new("ShaderNodeTexCoord").outputs["Generated"]
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(generated, axes.inputs[0])
    planar = nodes.new("ShaderNodeCombineXYZ")
    links.new(axes.outputs["X"], planar.inputs["X"])
    links.new(axes.outputs["Z"], planar.inputs["Y"])

    def distance(x, y):
        node = nodes.new("ShaderNodeVectorMath")
        node.operation = "DISTANCE"
        links.new(planar.outputs[0], node.inputs[0])
        node.inputs[1].default_value = (x, y, 0)
        return node.outputs["Value"]

    iris = ramp(nodes, links, distance(.50, .53), (
        (.14, "102333"), (.55, "173644"), (.21, "143346"),
        (.30, "318875"), (.40, "78D2BE"), (.48, "28546A"),
    ))
    gleam = ramp(nodes, links, distance(.36, .68), (
        (.026, (1., 1., 1., 1.)), (.095, (0., 0., 0., 1.)),
    ))
    color_surface(links, surface, blend(nodes, links, iris, rgb("DDF4EB"), gleam))
    for side in "LR":
        bpy.data.objects[f"eye.{side}"].data.materials[0] = material


def eye_pose(swimmer, shot, seconds, frame):
    gaze = Vector((.008 * math.sin(TAU * .25 * seconds + .62 * shot), 0.,
                   .004 * math.sin(TAU * .23 * seconds - .4)))
    eyes = swimmer.bones["eye_common"]
    eyes.location = swimmer.rest[eyes.name].inverted() @ gaze
    eyes.keyframe_insert(data_path="location", frame=frame, group="Eyes")
    blink = max(pulse(frame, peak - 3, peak, peak + 5) for peak in (78, 310, 408, 481))
    for sign, side in ((1, "L"), (-1, "R")):
        center = Vector((.033112 * sign, -.018319, 1.593897))
        for lid, amount in (("T", .65), ("B", -.16)):
            for suffix, weight in (("", .11), (".001", .75), (".002", 1.), (".003", .72)):
                name = f"lid.{lid}.{side}{suffix}"
                bone = swimmer.bones[name]
                radial = bone.bone.head_local - center
                rotation = Quaternion(RIGHT, blink * amount * weight)
                bone.location = swimmer.rest[name].inverted() @ (rotation @ radial - radial)
                bone.keyframe_insert(data_path="location", frame=frame, group="Eyelids")


def refine_follow_through(scene, swimmer):
    restore_iris()
    delayed = None
    for shot, index, _, frame in samples():
        scene.frame_set(frame)
        seconds = index / FPS
        head = swimmer.bones["head"].matrix.to_quaternion() @ swimmer.rest["head"].inverted()
        orientation = swimmer.rig.rotation_quaternion @ head
        delayed = orientation.copy() if index == 0 else delayed.slerp(orientation, .112)
        lag = orientation.inverted() @ delayed
        lag_vertical = lag @ UP - UP
        lag_turn = lag @ BACK - BACK
        for sign, side in ((1, "L"), (-1, "R")):
            names = (f"tail.{side}", *(f"tail.{index:03d}.{side}" for index in range(9, 16)))
            for segment, name in enumerate(names):
                distance = segment / (len(names) - 1)
                ripple = TAU * (.28 * seconds + .13 * sign) - 2.8 * distance
                weight = .30 + .70 * distance
                sway = weight * (.018 * math.sin(ripple) + .079 * lag_vertical.y)
                drift = weight * (.021 * math.cos(ripple + .5) + .066 * lag_vertical.x)
                twist = weight * (.014 * math.sin(ripple - .8) + .053 * lag_turn.x)
                opening = sign * (.009 + .027 * distance) * (1. if shot < 2 else .45)
                swimmer.bend(name, frame, sway + .022, drift + opening, twist)
        eye_pose(swimmer, shot, seconds, frame)


def repalette(nodes, source, colors):
    palette = next(
        node.color_ramp for node in nodes
        if node.type == "VALTORGB" and node.inputs["Fac"].is_linked
        and getattr(node.inputs["Fac"].links[0].from_node, "attribute_name", None) == source
    )
    for element, color in zip(palette.elements, colors, strict=True):
        element.color = rgb(color)


def surface_tree(name):
    tree = bpy.data.materials[name].node_tree
    surface = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    return tree.nodes, tree.links, surface


def refine_scales():
    mesh = bpy.data.objects["mermaid"].data
    # These fields are bound to the neutral mesh so they follow the moving fin.
    attr(mesh, "Fin rays", (math.atan2(abs(v.co.x), max(.095, .120 - v.co.z)) for v in mesh.vertices))
    attr(mesh, "Warm cheeks", (
        math.exp(-((abs(v.co.x) - .041) / .022)**2 - ((v.co.z - 1.564) / .017)**2)
        * smooth((-v.co.y - .023) / .034) for v in mesh.vertices
    ))

    nodes, links, surface = surface_tree("base skin")
    repalette(nodes, "Tail gradient", ("3B9F88", "168879", "166C85", "3B58A0", "6BAEBD", "B69BD9"))
    repalette(nodes, "Ear fin edge", ("72C4AD", "7FB5CC", "B38DC4"))
    current = surface.inputs["Base Color"].links[0].from_socket
    math_op = lambda operation, a, b=None: math_node(nodes, links, operation, a, b)
    cheek = math_op("MULTIPLY", field(nodes, "Warm cheeks"), .14)
    color = blend(nodes, links, current, rgb("E6998C"), cheek)
    membrane = field(nodes, "Fin membrane")
    phase = math_op("MULTIPLY", field(nodes, "Fin rays"), 61.)
    wave = math_op("SINE", phase)
    threads = math_op("POWER", math_op("MAXIMUM", wave, 0.), 5.)
    threads = math_op("MULTIPLY", threads, membrane)
    variation = math_op("MULTIPLY", threads, .26)
    color = blend(nodes, links, color, rgb("78AABC"), variation, "MULTIPLY")
    color_surface(links, surface, color)

    edge = next(
        node.outputs["Color"] for node in nodes
        if node.type == "VALTORGB" and node.inputs["Fac"].is_linked
        and getattr(node.inputs["Fac"].links[0].from_node, "operation", None) == "ABSOLUTE"
    )
    outline = math_op("MULTIPLY", edge, field(nodes, "Scale area"))
    relief = math_op("SUBTRACT", math_op("MULTIPLY", threads, .16), outline)
    bump = nodes.new("ShaderNodeBump")
    bump.label = "Shallow scale edges and fin rays"
    bump.inputs["Strength"].default_value = .27
    bump.inputs["Distance"].default_value = .005
    links.new(relief, bump.inputs["Height"])
    links.new(bump.outputs["Normal"], surface.inputs["Normal"])
    surface.inputs["Coat Roughness"].default_value = .41
    surface.inputs["Specular IOR Level"].default_value = .28
    surface.inputs["Emission Strength"].default_value = .045


def refine_materials(scene, swimmer):
    refine_scales()
    nodes, _, hair = surface_tree("hair")
    repalette(nodes, "Hair root to tip", ("612C42", "9A4559", "C26666", "E99C7F"))
    hair.inputs["Roughness"].default_value = .48
    hair.inputs["Specular IOR Level"].default_value = .22
    hair.inputs["Sheen Weight"].default_value = .14
    hair.inputs["Sheen Roughness"].default_value = .55
    hair.inputs["Coat Weight"].default_value = .13
    hair.inputs["Coat Roughness"].default_value = .52
    hair.inputs["Emission Strength"].default_value = .075

    nodes, links, fabric = surface_tree("outfit")
    repalette(nodes, "Woven edge", ("4D355F", "804E7A", "DFBC84"))
    edge = field(nodes, "Woven edge")
    gold = math_node(nodes, links, "POWER", edge, 2.7)
    links.new(math_node(nodes, links, "MULTIPLY", gold, .58), fabric.inputs["Metallic"])
    links.new(math_node(nodes, links, "SUBTRACT", .49, math_node(nodes, links, "MULTIPLY", gold, .22)),
              fabric.inputs["Roughness"])
    fabric.inputs["Sheen Weight"].default_value = .17
    fabric.inputs["Emission Strength"].default_value = .034


def set_light(name, position, aim, power, diameter, color):
    light = bpy.data.objects[name]
    light.location = position
    light.rotation_euler = (Vector(aim) - light.location).to_track_quat("-Z", "Y").to_euler()
    light.data.energy = power
    light.data.size = diameter
    light.data.color = color


def finish_light(scene):
    scene.view_settings.exposure = -.04
    set_light("Broad surface light", (.1, -1.75, 6.1), (0, 0, 1.11), 840, 4.35, (1., .94, .86))
    set_light("Front fill", (1.85, -4.40, 2.24), (0, 0, 1.44), 182, 4.9, (.64, .84, 1.))
    set_light("Edge of the sun", (-2.2, 3.45, 4.06), (.3, 0, 1.46), 690, 3.8, (.39, .82, 1.))

    water = scene.world.node_tree.nodes
    water["Map Range"].inputs["From Min"].default_value = -.38
    water["Map Range"].inputs["From Max"].default_value = .37
    colors = water["Color Ramp"].color_ramp
    colors.interpolation = "EASE"
    colors.elements[0].color = rgb("28576D")
    colors.elements[1].color = rgb("09263F")
    colors.elements.new(.44).color = rgb("194766")
    water["Background"].inputs["Strength"].default_value = .96

    nodes, _, sand = surface_tree("Fine blue sand")
    network = nodes["Color Ramp"].color_ramp
    network.elements[0].position = .012
    network.elements[0].color = (.036, .119, .151, 1.)
    network.elements[1].position = .102
    network.elements[1].color = (.019, .063, .087, 1.)
    nodes["Emission"].inputs["Color"].default_value = (.012, .063, .108, 1.)
    nodes["Map Range"].inputs["From Min"].default_value = 5.3
    nodes["Map Range"].inputs["From Max"].default_value = 13.4
    sand.inputs["Emission Strength"].default_value = .063

    nodes, links, rock = surface_tree("Basalt blue")
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 4.3
    grain.inputs["Detail"].default_value = 2.5
    coordinates = nodes.new("ShaderNodeTexCoord")
    links.new(coordinates.outputs["Object"], grain.inputs["Vector"])
    color = ramp(nodes, links, grain.outputs["Fac"], ((.19, "133040"), (.81, "2A5361")))
    links.new(color, rock.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = .11
    bump.inputs["Strength"].default_value = .20
    links.new(grain.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], rock.inputs["Normal"])


def finish_cameras(scene):
    cameras = [marker.camera for marker in sorted(scene.timeline_markers, key=lambda marker: marker.frame)]
    for camera, lens in zip(cameras, (43., 44.5, 39.), strict=True):
        camera.data.lens = lens
    previous = None
    for shot, index, count, frame in samples():
        t = index / (count - 1)
        u = pace(shot, t)
        center = route(shot, u)
        if shot == 0:
            heading = direction(shot, u)
            focus = Vector((center.x * .91 + .06, center.y * .66, center.z * .85 + .18))
            focus += .075 * heading
            offset = Vector((1.83 - .50 * ease(t), -5.11, .59 + .12 * math.sin(math.pi * t)))
        elif shot == 1:
            focus = Vector((center.x * .87 - .08, center.y * .61, 1.45 + (center.z - 1.45) * .71))
            offset = Vector((2.18 + .33 * ease(t), -5.43, .52))
        else:
            focus = Vector((.164 - .062 * ease(t), -.035, 1.11 - .018 * ease(t)))
            offset = Vector((2.13 - .45 * ease(t), -4.88, .24 + .17 * ease(t)))

        camera = cameras[shot]
        camera.location = focus + offset
        rotation = (-offset).to_track_quat("-Z", "Y")
        if index:
            rotation.make_compatible(previous)
        previous = rotation.copy()
        camera.rotation_quaternion = rotation
        camera.keyframe_insert(data_path="location", frame=frame, group="Camera")
        camera.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="Camera")


def finish_presentation(scene, swimmer):
    finish_light(scene)
    finish_cameras(scene)
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 810
    scene.eevee.taa_render_samples = 16


def main():
    stage, output = sys.argv[sys.argv.index("--") + 1:]
    scene = bpy.context.scene
    passes = (refine_swimming, refine_gestures, refine_follow_through, refine_materials, finish_presentation)
    passes[int(stage) - 1](scene, PolishSwimmer())
    scene.frame_set(1)
    scene.render.filepath = "//frames/"
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(output).resolve()))


if __name__ == "__main__":
    main()
