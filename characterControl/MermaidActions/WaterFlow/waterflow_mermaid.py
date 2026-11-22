"""Bake soft underwater follow-through onto the original mermaid rig."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(path) for path in (HERE, HERE.parent, HERE.parent / "PolishedSwim")]
from polish_mermaid import BACK, FPS, RIGHT, TAU, UP, PolishSwimmer, finger_pose, pulse, samples, solve_arm


def clamp(value, low, high):
    return min(high, max(low, value))


def response(seconds):
    return 1. - math.exp(-1. / (FPS * seconds))


def bias(swimmer, name, frame, axis, angle):
    bone = swimmer.bones[name]
    local_axis = swimmer.rest[name].inverted() @ axis
    swimmer.bone_key(name, bone.rotation_quaternion @ Quaternion(local_axis, angle), frame)


def refine_body(swimmer, shot, index, count, frame):
    seconds = index / FPS
    if shot == 0:
        dip = pulse(seconds, .14, 1.32, 2.51)
        rise = pulse(seconds, 2.25, 3.27, 4.90)
        bias(swimmer, "head", frame, RIGHT, -.044 * rise + .034 * dip)
        bias(swimmer, "chest", frame, BACK, .030 * rise - .018 * dip)
        return
    if shot == 1:
        lead = pulse(index / (count - 1), .04, .32, .74)
        bias(swimmer, "head", frame, UP, .049 * lead)
        bias(swimmer, "chest", frame, BACK, .028 * lead)
        return

    # Loosely feather the palms in opposing phases, with a relaxed recovery.
    sway = TAU * (.255 * seconds + .035 * math.sin(seconds * .86))
    bias(swimmer, "chest", frame, RIGHT, .017 * math.sin(sway - .38))
    bias(swimmer, "head", frame, BACK, .026 * math.sin(sway + .7))
    bpy.context.view_layer.update()
    forearms = []
    for sign, side in ((1, "L"), (-1, "R")):
        phase = sway + (.95 if sign == 1 else 3.72)
        width = .177 + .043 * math.sin(phase)
        wrist = Vector((sign * width, -.212 - .021 * math.cos(phase),
                        -.239 + .029 * math.cos(phase - .78)))
        pole = Vector((sign * .65, .23, -.73))
        upper, lower = f"upper_arm_fk.{side}", f"forearm_fk.{side}"
        arm, forearm = solve_arm(wrist, pole, swimmer.bones[upper].length, swimmer.bones[lower].length)
        swimmer.aim(upper, arm, frame)
        forearms.append((side, lower, forearm, phase, sign))
    bpy.context.view_layer.update()
    for side, lower, forearm, phase, sign in forearms:
        swimmer.aim(lower, forearm, frame)
        pitch = -.06 + .087 * math.sin(phase - .51)
        bank = sign * (.18 + .26 * math.cos(phase - .24))
        swimmer.bone_key(f"hand_fk.{side}", Quaternion(BACK, bank) @ Quaternion(RIGHT, pitch), frame)
        finger_pose(swimmer, side, .56 + .27 * math.cos(phase), frame)


class HairLock:
    def __init__(self, swimmer, side):
        self.swimmer = swimmer
        self.sign = 1 if side == "L" else -1
        self.names = (f"tail.{side}", *(f"tail.{i:03d}.{side}" for i in range(9, 16)))
        self.segments = [swimmer.bones[name].bone.tail_local - swimmer.bones[name].bone.head_local
                         for name in self.names]
        lengths = [segment.length for segment in self.segments]
        chain_length = sum(lengths)
        self.stations = [sum(lengths[:i + 1]) / chain_length for i in range(len(lengths))]
        self.delayed = []
        self.anchor = None
        self.speed = Vector((0, 0, 0))

    def bake(self, shot, index, frame):
        swimmer = self.swimmer
        root = swimmer.bones[self.names[0]]
        host = root.parent
        host_pose = host.matrix.to_quaternion()
        head = host_pose @ swimmer.rest[host.name].inverted()
        world = swimmer.rig.matrix_world.to_quaternion() @ head
        inverse = world.inverted()
        anchor = swimmer.rig.matrix_world @ root.head
        if index == 0:
            self.delayed = [world.copy() for _ in self.names]
            self.speed.zero()
            self.anchor = anchor.copy()
        velocity = (anchor - self.anchor) * FPS
        self.anchor = anchor.copy()
        self.speed = self.speed.lerp(velocity, response(.24))
        slip = inverse @ self.speed
        buoyancy = inverse @ UP
        sign = self.sign
        seconds = index / FPS
        parent = host_pose
        origin = root.bone.head_local.copy()
        for segment, (name, rest, s) in enumerate(zip(self.names, self.segments, self.stations)):
            delay = (.075 + .42 * s**1.25) * (1. if sign == 1 else 1.14)
            self.delayed[segment] = self.delayed[segment].slerp(world, response(delay))
            lag = inverse @ self.delayed[segment]
            lag_angle = lag.angle
            if lag_angle > math.pi:
                lag.negate()
                lag_angle = lag.angle
            drag = Quaternion().slerp(lag, min(.91, .57 / max(.01, lag_angle)))
            flow_phase = TAU * (.27 * seconds + .15 * sign) - 3.4 * s
            slow_phase = TAU * (.123 * seconds - .12 * sign) - 1.8 * s
            softness = s**1.14
            current = Vector((.23 * math.sin(flow_phase) + .093 * math.sin(slow_phase),
                              .16 * math.cos(flow_phase + .74), .072 * math.sin(slow_phase + .65)))
            lift = buoyancy * (.30 if shot == 2 else .19)
            glide = Vector((-.14 * clamp(slip.x, -1.35, 1.35), -.10 * clamp(slip.y, -1.3, 1.3),
                            -.055 * clamp(slip.z, -.8, 1.5)))
            away = Vector((sign * (.150 if shot < 2 else .12), .15, 0.))
            target = (drag @ rest.normalized() + softness * (current + lift + glide + away)).normalized()
            if segment == 0:
                target = rest.normalized().lerp(target, .34).normalized()

            # Keep the center of each lock outside the shoulder/back corridor.
            end = origin + rest.length * target
            if segment > 0:
                mid = math.sin(math.pi * s)
                end.y = max(end.y, .095 + .061 * mid)
                end.x = sign * max(sign * end.x, .092 + .035 * mid)
                target = (end - origin).normalized()
            origin += rest.length * target
            absolute_dir = head @ target
            rest_dir = head @ rest.normalized()
            twist = softness * (.103 * math.sin(flow_phase - .6) + .093 * sign * lag_angle)
            absolute = (Quaternion(absolute_dir, twist) @ rest_dir.rotation_difference(absolute_dir)
                        @ head @ swimmer.rest[name])
            parent_name = swimmer.bones[name].parent.name
            neutral = parent @ swimmer.rest[parent_name].inverted() @ swimmer.rest[name]
            swimmer.bone_key(name, neutral.inverted() @ absolute, frame)
            parent = absolute


def fringe_shapes():
    fringe = bpy.data.objects["Hair"]
    if fringe.data.shape_keys is None:
        fringe.shape_key_add(name="Basis", from_mix=False)
    bind = fringe.matrix_parent_inverse @ fringe.matrix_basis
    to_object = bind.inverted().to_3x3()
    basis = fringe.data.shape_keys.reference_key
    shapes = []
    for name, delta, minimum in (
        ("Fringe side drift", Vector((.021, 0, .004)), -1.),
        ("Fringe float", Vector((0, -.011, .014)), 0.),
    ):
        shape = fringe.shape_key_add(name=name, from_mix=False)
        shape.slider_min = minimum
        for point, neutral in zip(shape.data, basis.data):
            v = bind @ neutral.co
            reach = clamp((1.678 - v.z) / .155, 0., 1.)
            face = clamp((-.025 - v.y) / .044, 0., 1.)
            weight = reach**1.7 * face
            point.co = neutral.co + to_object @ (weight * delta)
        shapes.append(shape)
    return shapes


def main():
    output = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    swimmer = PolishSwimmer()
    locks = [HairLock(swimmer, side) for side in "LR"]
    drift, lift = fringe_shapes()
    for shot, index, count, frame in samples():
        scene.frame_set(frame)
        refine_body(swimmer, shot, index, count, frame)
        bpy.context.view_layer.update()
        for lock in locks:
            lock.bake(shot, index, frame)
        seconds = index / FPS
        drift.value = .63 * math.sin(TAU * .32 * seconds + .92 * shot) + .19 * math.sin(TAU * .17 * seconds)
        lift.value = .48 + .34 * math.sin(TAU * .23 * seconds + .9)
        for shape in (drift, lift):
            shape.keyframe_insert(data_path="value", frame=frame, group="Floating fringe")
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__ == "__main__":
    main()
