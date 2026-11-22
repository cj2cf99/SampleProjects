"""Bake the existing mermaid's tied locks with water drag and flexible guides."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(path) for path in (HERE, HERE.parent / "WaterFlow")]
from waterflow_mermaid import FPS, TAU, UP, PolishSwimmer, clamp, samples


SUBSTEPS = 5
STEP = 1. / (FPS * SUBSTEPS)


def centerline(names, bones):
    points = [bones[name].bone.head_local.copy() for name in names]
    return points + [bones[names[-1]].bone.tail_local.copy()]


def nearest_point(point, start, end):
    segment = end - start
    t = clamp((point - start).dot(segment) / max(segment.length_squared, 1e-9), 0., 1.)
    return start + t * segment


def capsule(swimmer, first, last, radius):
    transform = swimmer.rig.matrix_world
    start = transform @ swimmer.bones[first].head
    end = transform @ swimmer.bones[last].head
    return start, end, radius


def body_capsules(swimmer):
    items = [capsule(swimmer, "DEF-spine", "DEF-spine.003", .119),
             capsule(swimmer, "DEF-spine.003", "DEF-spine.005", .101)]
    for side in "LR":
        shoulder = f"DEF-upper_arm.{side}"
        elbow = f"DEF-forearm.{side}"
        hand = f"DEF-hand.{side}"
        items.extend((capsule(swimmer, shoulder, elbow, .054), capsule(swimmer, elbow, hand, .041)))
    return items


class FlexibleLock:
    def __init__(self, swimmer, side):
        self.swimmer = swimmer
        self.side = side
        self.sign = 1 if side == "L" else -1
        self.names = (f"tail.{side}", *(f"tail.{i:03d}.{side}" for i in range(9, 16)))
        self.rest = centerline(self.names, swimmer.bones)
        self.offsets = [point - self.rest[0] for point in self.rest]
        self.edges = [end - start for start, end in zip(self.rest, self.rest[1:])]
        self.lengths = [edge.length for edge in self.edges]
        total = sum(self.lengths)
        self.stations = [sum(self.lengths[:i])/total for i in range(len(self.rest))]
        self.chords = [(end - start).length for start, end in zip(self.rest, self.rest[2:])]
        self.inverse_mass = (0., 0., .68, .91, 1., 1.05, 1.15, 1.24, 1.28)
        self.points = []
        self.velocities = []
        self.anchor = None
        self.orientation = None
        self.anchor_speed = Vector((0., 0., 0.))
        self.filtered_directions = []
        self.splay = None

    def guide(self, anchor, orientation, shot):
        # A small outward set keeps the tied hairstyle recognizable under load.
        offset = Vector((self.sign * (.080 if shot < 2 else .095), .037, 0.))
        return [anchor + orientation @ (point + offset * s**1.12)
                for point, s in zip(self.offsets, self.stations)]

    def move(self, anchor, orientation, colliders, scene_time, shot, anchor_speed):
        guide = self.guide(anchor, orientation, shot)
        start = [point.copy() for point in self.points]
        self.points[:2] = guide[:2]
        for i in range(2, len(self.points)):
            position = start[i]
            s = self.stations[i]
            tangent = (position - start[i - 1]).normalized()
            # Drag uses the velocity of the water relative to each moving point.
            time = scene_time + .29 * self.sign
            wake = TAU * (.52 * time - .63 * s)
            fade = (.16 + .33 * min(anchor_speed.length, 1.4)) * s**.66
            local_flow = Vector((fade * math.sin(wake), .40 * fade * math.cos(wake + .7),
                                .24 * fade * math.sin(wake - .46)))
            current = Vector((.09, .03, .045)) + orientation @ local_flow
            relative = current - self.velocities[i]
            normal = relative - .74 * tangent * relative.dot(tangent)
            drag = normal * (3.4 + 6.6 * normal.length)
            buoyancy = UP * (.73 if shot == 2 else .60)
            stiffness = 4.6 + 21. * (1 - s)**2
            spring = (guide[i] - position) * stiffness
            self.velocities[i] += STEP * (drag + buoyancy + spring)
            self.points[i] += STEP * self.velocities[i]

        inverse = orientation.inverted()
        sides = [collider for collider in colliders if (collider[0] - anchor).length < 1.1]
        for _ in range(7):
            for i, chord in enumerate(self.chords):
                # Compliance softens bends while preventing a sharp hinge at a joint.
                self.constrain_distance(i, i + 2, chord, .034 if i < 5 else .063)
            for i, length in enumerate(self.lengths):
                self.constrain_distance(i, i + 1, length, 1.)
            for i in range(2, len(self.points)):
                self.resolve_contact(i, anchor, orientation, inverse, sides)

        for i in range(2, len(self.points)):
            self.velocities[i] = (self.points[i] - start[i]) * (0.961 / STEP)

    def constrain_distance(self, start, end, length, strength):
        weights = self.inverse_mass[start], self.inverse_mass[end]
        total = weights[0] + weights[1]
        if not total:
            return
        direction = self.points[end] - self.points[start]
        distance = direction.length
        if distance < 1e-9:
            return
        correction = direction * (strength * (distance - length) / (distance * total))
        self.points[start] += weights[0] * correction
        self.points[end] -= weights[1] * correction

    def keep_clear(self, point, index, anchor, orientation, inverse, colliders):
        s = self.stations[index]
        local = self.rest[0] + inverse @ (point - anchor)
        # A shallow back/side envelope keeps broad surface ribbons clear of the rig.
        mid = math.sin(math.pi * s)
        local.y = max(local.y, .114 + .059 * mid)
        local.x = self.sign * max(self.sign * local.x, .088 + .029 * mid)
        point = anchor + orientation @ (local - self.rest[0])
        radius = .024 + .013 * (1 - abs(2 * s - 1))
        for start, end, body_radius in colliders:
            closest = nearest_point(point, start, end)
            outward = point - closest
            limit = radius + body_radius
            if 1e-9 < outward.length_squared < limit**2:
                point = closest + limit * outward.normalized()
        return point

    def resolve_contact(self, index, anchor, orientation, inverse, colliders):
        self.points[index] = self.keep_clear(self.points[index], index, anchor, orientation, inverse, colliders)

    def bend_under_flow(self, direction, segment, now, shot, flow):
        # Direct the bend along the length of the simulated lock. The phase at
        # the tip follows the mid-lock phase, with scale set by water speed.
        s = self.stations[segment + 1]
        load = self.anchor_speed.length / (.46 + self.anchor_speed.length)
        wave = TAU * (.47 * now - .78 * s + .14 * self.sign) - .48 * flow.x
        compliance = clamp((s - .13) / .87, 0., 1.)**1.32
        amplitude = (.46 + .74 * load) if shot < 2 else .78
        lateral = -self.sign * compliance * (.51 + amplitude * math.sin(wave))
        dorsal = compliance * (.30 + .53 * math.cos(wave + .28))
        if segment >= 5:
            rest = self.edges[segment].normalized()
            direction = direction.slerp(rest, .27)
        return Quaternion((0, 1, 0), lateral) @ Quaternion((1, 0, 0), dorsal) @ direction

    def bake(self, shot, index, frame, colliders):
        swimmer = self.swimmer
        root = swimmer.bones[self.names[0]]
        host = root.parent
        parent = host.matrix.to_quaternion()
        head = parent @ swimmer.rest[host.name].inverted()
        armature = swimmer.rig.matrix_world.to_quaternion()
        orientation = armature @ head
        anchor = swimmer.rig.matrix_world @ root.head
        now = index / FPS
        if index == 0:
            self.points = self.guide(anchor, orientation, shot)
            self.velocities = [Vector((0., 0., 0.)) for _ in self.points]
            self.anchor = anchor.copy()
            self.orientation = orientation.copy()
            self.anchor_speed.zero()
            self.filtered_directions.clear()
            for step in range(42):
                self.move(anchor, orientation, colliders, now + (step - 42) * STEP, shot, self.anchor_speed)
        else:
            speed = (anchor - self.anchor) * FPS
            self.anchor_speed = self.anchor_speed.lerp(speed, .12)
            for step in range(1, SUBSTEPS + 1):
                progress = step / SUBSTEPS
                point = self.anchor.lerp(anchor, progress)
                pose = self.orientation.slerp(orientation, progress)
                self.move(point, pose, colliders, now + (step - SUBSTEPS) * STEP, shot, self.anchor_speed)

        self.anchor = anchor.copy()
        self.orientation = orientation.copy()
        inverse = orientation.inverted()
        flow = inverse @ self.anchor_speed
        vertex = anchor.copy()
        for i, (name, edge) in enumerate(zip(self.names, self.edges)):
            direction = (self.points[i+1] - self.points[i]).normalized()
            if index == 0:
                self.filtered_directions.append(direction.copy())
            elif i > 0:
                direction = self.filtered_directions[i].slerp(direction, .56)
                self.filtered_directions[i] = direction.copy()
            local = inverse @ direction
            if i > 0:
                local = self.bend_under_flow(local, i, now, shot, flow)
                end = vertex + orientation @ (local * edge.length)
                end = self.keep_clear(end, i + 1, anchor, orientation, inverse, colliders)
                local = inverse @ (end - vertex).normalized()
            vertex += orientation @ (local * edge.length)
            direction = head @ local
            rest_direction = head @ edge.normalized()
            s = self.stations[i+1]
            twist = .16 * s**2 * math.sin(TAU * (.49 * now - .59 * s + .19 * self.sign))
            absolute = (Quaternion(direction, twist) @ rest_direction.rotation_difference(direction)
                        @ head @ swimmer.rest[name])
            parent_name = swimmer.bones[name].parent.name
            neutral = parent @ swimmer.rest[parent_name].inverted() @ swimmer.rest[name]
            swimmer.bone_key(name, neutral.inverted() @ absolute, frame)
            parent = absolute

        if self.splay is not None:
            speed = self.anchor_speed.length
            self.splay.value = clamp(.68 - 1.03 * speed / (.35 + speed) + .41 * math.sin(TAU * (.47 * now + .14 * self.sign - .72)), -.8, 1.)
            self.splay.keyframe_insert(data_path="value", frame=frame, group="Lock spread under drag")


def add_lock_splay(locks):
    hair = bpy.data.objects["Hair tails"]
    if hair.data.shape_keys is None:
        hair.shape_key_add(name="Basis", from_mix=False)
    basis = hair.data.shape_keys.reference_key
    bind = hair.matrix_parent_inverse @ hair.matrix_basis
    to_object = bind.inverted().to_3x3()
    for lock in locks:
        key = hair.shape_key_add(name=f"Underwater lock spread {lock.side}", from_mix=False)
        key.slider_min = -1.
        lock.splay = key
        edges = tuple(zip(lock.rest, lock.rest[1:]))
        for point, source in zip(key.data, basis.data):
            v = bind @ source.co
            if lock.sign * v.x <= 0.:
                continue
            near = min((nearest_point(v, a, b) for a, b in edges), key=lambda p: (p - v).length_squared)
            falloff = clamp((1.70 - v.z) / .58, 0., 1.)**1.65
            distance = v - near
            spread = Vector((distance.x * .66, distance.y * .50,
                             .012 * math.sin(v.x * 103 + v.y * 48)))
            point.co = source.co + to_object @ (falloff * spread)


def main():
    output = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    swimmer = PolishSwimmer()
    locks = [FlexibleLock(swimmer, side) for side in "LR"]
    add_lock_splay(locks)
    for shot, index, _, frame in samples():
        scene.frame_set(frame)
        colliders = body_capsules(swimmer)
        for lock in locks:
            lock.bake(shot, index, frame, colliders)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__ == "__main__":
    main()
