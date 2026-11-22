"""Bake three underwater actions on the supplied Mermaid Anime rig."""

import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


FPS = 30
SECTIONS = (
    ("Agile swim", 168),
    ("Advancing spiral", 180),
    ("Treading hover", 162),
)
UP = Vector((0, 0, 1))
RIGHT = Vector((1, 0, 0))
BACK = Vector((0, 1, 0))
TAU = math.tau
OUTPUT = Path(sys.argv[sys.argv.index("--") + 1]).resolve()


def mix(a, b, t):
    return a + (b - a) * t


def eased(t):
    t = min(1., max(0., t))
    return t * t * (3. - 2. * t)


def route(shot, t):
    if shot == 0:
        u = t - .105 * math.sin(TAU*t) / TAU + .14 * math.sin(2*TAU*t) / (2*TAU)
        return Vector((-2.54 + 5.20*u, .74*math.sin(TAU*u+.28), 1.44 + .51*math.cos(TAU*u+.65)))
    if shot == 1:
        u = t - .14*math.sin(TAU*t)/TAU
        theta = TAU*u + .28
        return Vector((-2.34 + 4.68*u, .52*math.cos(theta), 1.45 + .48*math.sin(theta)))
    theta = TAU*t
    return Vector((.18 + .034*math.sin(theta), -.16 + .032*math.sin(theta+.35),
                   1.35 + .038*math.cos(theta*2)))


def direction(shot, t):
    return (route(shot, t+.002) - route(shot, t-.002)).normalized()


def body_rotation(heading, roll):
    lateral = UP.cross(heading).normalized()
    dorsal = heading.cross(lateral).normalized()
    basis = Matrix((lateral, dorsal, heading)).transposed().to_quaternion()
    return Quaternion(heading, roll) @ basis


def arm_vector(side, angle, lead):
    return Vector((side*math.cos(angle)*math.cos(lead), -math.sin(lead),
                   math.sin(angle)*math.cos(lead)))


def arm_moves(shot, t, time, side):
    if shot == 0:
        # Lead with each hand through the S turns. The recovery is softer
        # than the pull, and the two arms use separate timings.
        bias = .15 if side == 1 else .58
        power = .5 + .5*math.sin(TAU*(.66*time+bias) + .32*math.sin(TAU*t))
        sweep = eased(power)
        extension = mix(-1.10, .99, sweep)
        ahead = mix(.20, .54, sweep)
        upper = arm_vector(side, extension, ahead)
        lower = arm_vector(side, extension-.06 + .26*(1-sweep), ahead+.23*(1.-sweep))
        return upper, lower, side*.21*math.sin(TAU*.66*time+bias)
    if shot == 1:
        # Bring the hands near the line of travel before the middle of the
        # barrel roll. Reopen them to brake and square up on exit.
        tuck = math.sin(math.pi*t)**1.4
        offset = .17*side*math.sin(TAU*t)
        upper = arm_vector(side, mix(-.62,.91,tuck)+offset, .22+.20*tuck)
        lower = arm_vector(side, mix(-.40,1.23,tuck)+offset*.6, .34+.04*tuck)
        return upper, lower, side*mix(.17,-.27,tuck)
    rhythm = TAU*(.77*time + (.44 if side<0 else 0))
    upper = arm_vector(side, -.92+.14*math.cos(rhythm), .23+.15*math.sin(rhythm))
    lower = arm_vector(side, -.33+.24*math.cos(rhythm+.4), .58+.23*math.sin(rhythm+.24))
    return upper, lower, side*.30*math.cos(rhythm+.26)


class Swimmer:
    def __init__(self):
        self.rig = bpy.data.objects["Mermaid Anime"]
        self.mesh = bpy.data.objects["mermaid"]
        self.pivot = Vector((0., .017, 1.062))
        if self.rig.animation_data:
            self.rig.animation_data.action = None
        self.rig.rotation_mode = "QUATERNION"
        self.bones = self.rig.pose.bones
        for side in "LR":
            self.bones[f"upper_arm_parent.{side}"]["IK_FK"] = 1.
        self.rest = {bone.name:bone.bone.matrix_local.to_quaternion() for bone in self.bones}
        self.previous = {}
        self.root_previous = None
        self.tail = ["tail", "tail.001", "tail.002", "tail.003", "tail.004"]
        self.hair = {side:[f"tail.{side}"]+[f"tail.{n:03d}.{side}" for n in range(9,16)] for side in "LR"}
        # Each child already inherits the parent's rotation through parenting.
        # These source constraints copy that rotation a second time.
        for chain in (self.tail, *self.hair.values()):
            for parent, name in zip(chain,chain[1:]):
                for c in self.bones[name].constraints:
                    if c.type=="COPY_ROTATION" and c.subtarget==parent:
                        c.mute=True
        self.fin = self.add_fin_shape()

    def add_fin_shape(self):
        self.mesh.shape_key_add(name="Basis", from_mix=False)
        shape = self.mesh.shape_key_add(name="Fin membrane flex", from_mix=False)
        shape.slider_min = -1.
        shape.slider_max = 1.
        for v, point in zip(self.mesh.data.vertices,shape.data):
            if v.co.z<-.064:
                flex = eased((-v.co.z-.064)/.265)
                tip_weight = .64 + .36*eased(abs(v.co.x)/.29)
                point.co.y += .082*flex*tip_weight
                point.co.z += .019*flex
        return shape

    def bone_key(self, name, q, frame):
        bone = self.bones[name]
        if name in self.previous:
            q.make_compatible(self.previous[name])
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = q
        bone.keyframe_insert(data_path="rotation_quaternion",frame=frame,group=name)
        self.previous[name] = q.copy()

    def bend(self, name, frame, pitch=0., bank=0., twist=0.):
        axes = self.rest[name].inverted()
        q = (Quaternion(axes @ RIGHT,pitch) @ Quaternion(axes @ BACK,bank)
             @ Quaternion(axes @ UP,twist))
        self.bone_key(name,q,frame)

    def aim(self, name, vector, frame):
        bone = self.bones[name]
        parent = bone.parent
        base = parent.matrix.to_quaternion() @ self.rest[parent.name].inverted() @ self.rest[name]
        target = base.inverted() @ vector.normalized()
        self.bone_key(name, BACK.rotation_difference(target),frame)

    def pose(self, shot, local, count, frame):
        t = local/(count-1)
        time = local/FPS
        center = route(shot,t)
        if shot == 0:
            roll = -1.06 + .44*math.sin(TAU*t+.45) - .19*math.sin(TAU*2*t)
            root = body_rotation(direction(shot,t),roll)
            phase = TAU*(1.12*time+.074*time*time)
            thrust = .83 + .19*math.sin(TAU*t-.30) + .13*math.cos(2*TAU*t)
            side_curve = .082*math.sin(TAU*t)
            pitch_bias = -.072
        elif shot == 1:
            roll = -1.04 + TAU*(t-.17*math.sin(TAU*t)/TAU)
            root = body_rotation(direction(shot,t),roll)
            phase = TAU*(1.31*time + .11*math.sin(TAU*t))
            thrust = .79 + .11*math.cos(TAU*t)
            side_curve = .061*math.sin(TAU*t+.4)
            pitch_bias = -.055
        else:
            phase = TAU*(.93*time + .047*math.sin(TAU*t))
            root = (Quaternion(UP, .27+.115*math.sin(TAU*t))
                    @ Quaternion(RIGHT, .035*math.sin(phase+.2))
                    @ Quaternion(BACK, .022*math.cos(phase)))
            thrust = .72 + .085*math.cos(TAU*t)
            side_curve = .086*math.sin(phase*.56)
            pitch_bias = .155
        if local and self.root_previous:
            root.make_compatible(self.root_previous)
        self.root_previous = root.copy()
        self.rig.rotation_quaternion = root
        self.rig.location = center - root @ self.pivot
        self.rig.keyframe_insert(data_path="rotation_quaternion",frame=frame,group="Swim trajectory")
        self.rig.keyframe_insert(data_path="location",frame=frame,group="Swim trajectory")
        self.bend("chest",frame,.041*math.sin(phase+.7),-.29*side_curve,.036*math.cos(phase*.61))
        head_lift = -.32 if shot<2 else -.04
        self.bend("head",frame,head_lift+.052*math.sin(phase*.64),-.52*side_curve,
                  (.05 if shot<2 else .10)*math.sin(TAU*t+.6))
        for i, name in enumerate(self.tail):
            progress = phase - .88*i
            wave = (.123,.169,.203,.264,.298)[i]*thrust
            pitch = wave*(math.sin(progress)+.19*math.sin(2*progress-.65))
            self.bend(name,frame,pitch_bias*(1. if i==0 else .39)+pitch,
                      side_curve*(1. if i<2 else .43)+.039*math.sin(progress+.85),
                      .033*math.cos(progress-.41))
        self.fin.value = .66*thrust*math.sin(phase-3.67) + .095*math.sin(phase*2-1.12)
        self.fin.keyframe_insert(data_path="value",frame=frame,group="Fin flex")
        for side in "LR":
            sign = 1. if side=="L" else -1.
            for i, name in enumerate(self.hair[side]):
                distal = i/7
                drag = .02 if shot==2 else .045
                p = phase*.62 - i*.49 + sign*.27
                self.bend(name,frame,drag*(1.-distal)+(.016+.026*distal)*math.sin(p),
                          sign*.020*(1.-distal)+.44*side_curve+.022*math.cos(p-.38),
                          .018*math.sin(p-.55))
        bpy.context.view_layer.update()
        arm_goals = {}
        for s, side in ((1,"L"),(-1,"R")):
            u, l, wrist = arm_moves(shot,t,time,s)
            self.aim("upper_arm_fk."+side,u,frame)
            arm_goals[side] = (l,wrist)
        bpy.context.view_layer.update()
        for side, (lower, wrist) in arm_goals.items():
            self.aim("forearm_fk."+side,lower,frame)
            self.bone_key("hand_fk."+side,
                          Quaternion(BACK,wrist) @ Quaternion(RIGHT,.085*math.sin(phase+.71)),frame)
        return center


def new_material(name, color, roughness=.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color,1.)
    p = mat.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color,1.)
    p.inputs["Roughness"].default_value = roughness
    return mat, p


def model_materials(swimmer):
    for name, texture, roughness in (("base skin","mermaid skin.png",.51),
                                     ("outfit","outfit mermaid.png",.38),
                                     ("hair","hair",.37)):
        mat = bpy.data.materials[name]
        nodes,links = mat.node_tree.nodes,mat.node_tree.links
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        image = nodes.new("ShaderNodeTexImage")
        image.image = bpy.data.images[texture]
        links.new(image.outputs["Color"],bsdf.inputs["Base Color"])
        links.new(image.outputs["Color"],bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = .075
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Specular IOR Level"].default_value = .35
        bsdf.inputs["Coat Weight"].default_value = .09
        links.new(bsdf.outputs[0],output.inputs["Surface"])
        if name=="base skin":
            attribute = nodes.new("ShaderNodeAttribute")
            attribute.attribute_name = "Fin and scales"
            gloss = nodes.new("ShaderNodeMapRange")
            gloss.inputs["To Min"].default_value = .50
            gloss.inputs["To Max"].default_value = .28
            links.new(attribute.outputs["Fac"],gloss.inputs["Value"])
            links.new(gloss.outputs["Result"],bsdf.inputs["Roughness"])
            scale_tint = nodes.new("ShaderNodeMixRGB")
            scale_tint.blend_type = "MULTIPLY"
            scale_tint.inputs[2].default_value = (.46,.89,.93,1.)
            links.new(image.outputs["Color"],scale_tint.inputs[1])
            links.new(attribute.outputs["Fac"],scale_tint.inputs[0])
            links.new(scale_tint.outputs[0],bsdf.inputs["Base Color"])
    m = swimmer.mesh.data
    attribute = m.attributes.new("Fin and scales","FLOAT","POINT")
    attribute.data.foreach_set("value",[eased((1.14-v.co.z)/.30) for v in m.vertices])
    for ob in bpy.data.objects:
        if ob.type=="MESH" and ob.parent == swimmer.rig:
            ob.data.polygons.foreach_set("use_smooth",[True]*len(ob.data.polygons))
    smooth = swimmer.mesh.modifiers.new("Smooth swimming silhouettes","SUBSURF")
    smooth.levels = 1
    smooth.render_levels = 1


def area(name, position, target, watts, size, color):
    data = bpy.data.lights.new(name,"AREA")
    ob = bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(ob)
    ob.location = position
    ob.rotation_euler = (Vector(target)-ob.location).to_track_quat("-Z","Y").to_euler()
    data.color = color
    data.energy = watts
    data.shape = "DISK"
    data.size = size
    return ob


def seabed():
    mat, bsdf = new_material("Fine blue sand",(.036,.118,.135),.86)
    nodes,links = mat.node_tree.nodes,mat.node_tree.links
    coord = nodes.new("ShaderNodeTexCoord")
    warp = nodes.new("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = 1.2
    warp.inputs["Detail"].default_value = 2.
    links.new(coord.outputs["Object"],warp.inputs["Vector"])
    ripples = nodes.new("ShaderNodeTexVoronoi")
    ripples.feature = "DISTANCE_TO_EDGE"
    ripples.inputs["Scale"].default_value = 3.9
    distorted = nodes.new("ShaderNodeVectorMath")
    distorted.operation = "MULTIPLY_ADD"
    links.new(warp.outputs["Color"],distorted.inputs[0])
    distorted.inputs[1].default_value = (.53,.53,.06)
    links.new(coord.outputs["Object"],distorted.inputs[2])
    links.new(distorted.outputs[0],ripples.inputs["Vector"])
    caustic = nodes.new("ShaderNodeValToRGB")
    caustic.color_ramp.elements[0].position = .017
    caustic.color_ramp.elements[0].color = (.043,.148,.169,1.)
    caustic.color_ramp.elements[1].position = .095
    caustic.color_ramp.elements[1].color = (.023,.072,.096,1.)
    links.new(ripples.outputs["Distance"],caustic.inputs[0])
    depth = nodes.new("ShaderNodeCameraData")
    fade = nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = 5.2
    fade.inputs["From Max"].default_value = 18.0
    links.new(depth.outputs["View Distance"],fade.inputs["Value"])
    wet = nodes.new("ShaderNodeMixShader")
    haze = nodes.new("ShaderNodeEmission")
    haze.inputs["Color"].default_value = (.019,.108,.158,1.)
    links.new(fade.outputs["Result"],wet.inputs[0])
    links.new(bsdf.outputs[0],wet.inputs[1])
    links.new(haze.outputs[0],wet.inputs[2])
    links.new(wet.outputs[0],nodes.get("Material Output").inputs["Surface"])
    links.new(caustic.outputs[0],bsdf.inputs["Base Color"])
    links.new(caustic.outputs[0],bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = .09
    bpy.ops.mesh.primitive_plane_add(size=130,location=(0,0,-.98))
    floor = bpy.context.object
    floor.name = "Sand with broken caustics"
    floor.data.materials.append(mat)


def reef():
    rng = random.Random(192)
    rock, _ = new_material("Basalt blue",(.021,.091,.123),.89)
    grass, _ = new_material("Sea grass",(.026,.154,.133),.78)
    for i in range(17):
        x = -10.8 + 21.6*i/16 + rng.uniform(-.24,.24)
        y = rng.uniform(2.5,7.6)
        size = rng.uniform(.20,.71)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=(x,y,-.96+size*.17))
        obj = bpy.context.object
        obj.name = f"Reef stone {i+1:02}"
        obj.scale = (size*rng.uniform(1.3,1.85),size*rng.uniform(.8,1.4),size*rng.uniform(.39,.83))
        obj.rotation_euler.z = rng.uniform(0,TAU)
        obj.data.materials.append(rock)
        for p in obj.data.polygons:
            p.use_smooth = True
    curves = bpy.data.curves.new("Sea grass silhouettes","CURVE")
    curves.dimensions = "3D"
    curves.bevel_depth = .013
    curves.bevel_resolution = 2
    for _ in range(42):
        x,y = rng.uniform(-9,9),rng.uniform(2.6,6.5)
        h = rng.uniform(.24,.79)
        lean = rng.uniform(-.19,.25)
        strand=curves.splines.new("BEZIER")
        strand.bezier_points.add(3)
        for j,p in enumerate(strand.bezier_points):
            u = j/3
            p.co = (x+lean*u*u,y+.088*u*u,-.97+h*u)
            p.radius = (.95,.76,.49,.07)[j]
            p.handle_left_type = p.handle_right_type = "AUTO"
    obj = bpy.data.objects.new("Sparse reef plants",curves)
    bpy.context.collection.objects.link(obj)
    curves.materials.append(grass)


def sunbeams():
    mat=bpy.data.materials.new("Soft underwater shafts")
    mat.use_nodes=True
    mat.surface_render_method="BLENDED"
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    nodes.clear()
    uv=nodes.new("ShaderNodeTexCoord")
    split=nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"],split.inputs[0])
    across=nodes.new("ShaderNodeValToRGB")
    across.color_ramp.interpolation="EASE"
    across.color_ramp.elements[0].color = (0,0,0,1)
    across.color_ramp.elements[1].color = (0,0,0,1)
    across.color_ramp.elements.new(.49).color = (1,1,1,1)
    links.new(split.outputs["X"],across.inputs[0])
    height=nodes.new("ShaderNodeValToRGB")
    height.color_ramp.interpolation="EASE"
    height.color_ramp.elements[0].color = (0,0,0,1)
    height.color_ramp.elements[1].color = (0,0,0,1)
    height.color_ramp.elements.new(.74).color = (.20,.20,.20,1)
    links.new(split.outputs["Y"],height.inputs[0])
    opacity=nodes.new("ShaderNodeMath")
    opacity.operation="MULTIPLY"
    links.new(across.outputs[0],opacity.inputs[0])
    links.new(height.outputs[0],opacity.inputs[1])
    air=nodes.new("ShaderNodeBsdfTransparent")
    halo=nodes.new("ShaderNodeEmission")
    halo.inputs["Color"].default_value=(.092,.38,.49,1.)
    shade=nodes.new("ShaderNodeMixShader")
    links.new(opacity.outputs[0],shade.inputs[0])
    links.new(air.outputs[0],shade.inputs[1])
    links.new(halo.outputs[0],shade.inputs[2])
    out=nodes.new("ShaderNodeOutputMaterial")
    links.new(shade.outputs[0],out.inputs["Surface"])
    for i,(x,y,w) in enumerate(((-6.0,5.7,.75),(-2.6,5.2,1.13),(.2,5.8,.73),(3.8,5.1,1.16),(6.4,6.0,.81))):
        mesh=bpy.data.meshes.new("Refracted light")
        mesh.from_pydata([(x-2.0-w,y,-.8),(x-2.0+w,y,-.8),(x+w*.40,y,5.0),(x-w*.40,y,5.0)],[],[(0,1,2,3)])
        uv=mesh.uv_layers.new(name="Light falloff")
        for d,co in zip(uv.uv,((0,0),(1,0),(1,1),(0,1))):
            d.vector=co
        obj=bpy.data.objects.new(f"Diffused light shaft {i+1}",mesh)
        bpy.context.collection.objects.link(obj)
        mesh.materials.append(mat)


def water(scene):
    world = bpy.data.worlds.new("Open blue water")
    world.use_nodes = True
    nodes, links = world.node_tree.nodes,world.node_tree.links
    bg = nodes.get("Background")
    tex = nodes.new("ShaderNodeTexCoord")
    axis = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tex.outputs["Normal"],axis.inputs[0])
    contrast = nodes.new("ShaderNodeMapRange")
    contrast.inputs["From Min"].default_value = -.29
    contrast.inputs["From Max"].default_value = .45
    links.new(axis.outputs["Z"],contrast.inputs["Value"])
    color = nodes.new("ShaderNodeValToRGB")
    color.color_ramp.elements[0].color = (.028,.154,.221,1.)
    color.color_ramp.elements[1].color = (.009,.060,.097,1.)
    links.new(contrast.outputs["Result"],color.inputs[0])
    links.new(color.outputs[0],bg.inputs["Color"])
    bg.inputs["Strength"].default_value = .92
    scene.world = world
    sunbeams()
    area("Broad surface light",(1.4,-1.9,6.0),(0,0,1),820,5.3,(.68,.91,1.))
    area("Front fill",(1.5,-4.4,2.65),(0,0,1.4),320,4.0,(.96,.96,1.))
    area("Edge of the sun",(-2.6,3.8,4.2),(1,0,1.45),495,3.3,(.31,.82,1.))


def bubbles(scene):
    rng = random.Random(75)
    material, surface = new_material("Small transparent glints",(.113,.47,.57),.22)
    surface.inputs["Metallic"].default_value = .35
    surface.inputs["Coat Weight"].default_value = .56
    surface.inputs["Emission Color"].default_value = (.039,.24,.30,1.)
    surface.inputs["Emission Strength"].default_value = .26
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1)
    seed = bpy.context.object
    mesh = seed.data
    mesh.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = True
    count = 48
    for i in range(count):
        o = bpy.data.objects.new(f"Water mote {i+1:02}",mesh)
        bpy.context.collection.objects.link(o)
        x,y,z = rng.uniform(-8,8),rng.uniform(.9,7.2),rng.uniform(-.64,3.6)
        size = rng.uniform(.009,.023)*(1.22 if y>4 else 1.)
        o.scale = (size,size,size)
        o.location = (x,y,z)
        o.keyframe_insert(data_path="location",frame=1)
        o.location = (x+.17+rng.uniform(-.24,.24),y+.09,z+rng.uniform(.7,1.6))
        o.keyframe_insert(data_path="location",frame=scene.frame_end)
    bpy.data.objects.remove(seed,do_unlink=True)


def shot_camera(shot):
    data = bpy.data.cameras.new(SECTIONS[shot][0])
    obj = bpy.data.objects.new(SECTIONS[shot][0]+" camera",data)
    bpy.context.collection.objects.link(obj)
    data.lens = (39.5,41.0,43.0)[shot]
    data.clip_end = 72
    obj.rotation_mode = "QUATERNION"
    return obj


def set_camera(camera,shot,center,local,count,frame):
    t = local/(count-1)
    if shot==0:
        focus = Vector((center.x*.76+.13,center.y*.48,center.z*.70+.36))
        eye = focus + Vector((2.17-.71*t,-5.15,.54+.24*math.sin(math.pi*t)))
    elif shot==1:
        focus = Vector((center.x*.67+.09,center.y*.41,1.47+(center.z-1.47)*.57))
        eye = focus + Vector((2.28+.38*t,-5.5,.47))
    else:
        focus = Vector((.15,-.04,1.09))
        eye = focus + Vector((2.47-.67*t,-4.76,.27+.21*t))
    camera.location = eye
    rotation = (focus-eye).to_track_quat("-Z","Y")
    camera.rotation_quaternion = rotation
    camera.keyframe_insert(data_path="location",frame=frame,group="Camera")
    camera.keyframe_insert(data_path="rotation_quaternion",frame=frame,group="Camera")


def setup():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = sum(length for _,length in SECTIONS)
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 675
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 12
    scene.render.film_transparent = False
    scene.render.filepath = "//frames/"
    scene.eevee.taa_render_samples = 10
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .22
    for marker in tuple(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    for ob in bpy.data.objects:
        if ob.name.startswith("WGT-") or ob.name == "metarig":
            ob.hide_render = True
    # The downloaded project includes a badge add-on. Animation and playback
    # use the asset's mesh and stock constraint rig only.
    for script in tuple(bpy.data.texts):
        if script.name.endswith(".py"):
            bpy.data.texts.remove(script)
    swimmer=Swimmer()
    model_materials(swimmer)
    seabed()
    reef()
    bubbles(scene)
    water(scene)
    first=1
    for shot,(name,count) in enumerate(SECTIONS):
        camera=shot_camera(shot)
        scene.timeline_markers.new(name,frame=first).camera=camera
        for local in range(count):
            frame=first+local
            scene.frame_set(frame)
            center=swimmer.pose(shot,local,count,frame)
            set_camera(camera,shot,center,local,count,frame)
        print("BAKED",name,first,first+count-1,flush=True)
        first+=count
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                view=area.spaces.active
                view.region_3d.view_perspective="CAMERA"
                view.overlay.show_overlays=False
                view.shading.type="MATERIAL"
    scene["Actions"] = "1-168 Agile swim | 169-348 Advancing spiral | 349-510 Treading hover"
    scene.frame_set(1)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/"Mermaid_swim.blend"))
    out = OUTPUT/"checks"
    out.mkdir(exist_ok=True)
    scene.render.resolution_percentage = 66
    scene.eevee.taa_render_samples = 8
    for f in (18,50,88,135,185,220,255,300,332,363,397,437,478):
        scene.frame_set(f)
        scene.render.filepath = str(out/f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    setup()
