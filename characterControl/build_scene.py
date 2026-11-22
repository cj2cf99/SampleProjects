import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


HERE = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
mode = ARGS[0] if ARGS else "setup"
root = Path(ARGS[1]).resolve() if len(ARGS) > 1 else HERE
root.mkdir(parents=True, exist_ok=True)
BASE_COLOR = (1., 1., 1., 1.)
FLOOR_Z = -.03
BALL_RADIUS = .116
MARKERS = (
    ("Ball handling", 1),
    ("Toss", 260),
    ("Back-facing shoulder accents", 292),
    ("Turning footwork", 332),
    ("Hand across face", 657),
)


def clamp(value, lower=0., upper=1.):
    return min(upper, max(lower, value))


def central(a, b):
    return (a+b)*.5


def normalized(value, fallback):
    return value.normalized() if value.length > 1e-6 else fallback


def orient(side, up):
    x = normalized(side,Vector((1.,0.,0.)))
    y = normalized(up.cross(x),Vector((0.,1.,0.)))
    z = x.cross(y).normalized()
    return Matrix((x,y,z)).transposed().to_quaternion()


def material(name, color, rough=.75):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color,1.)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color,1.)
    shader.inputs["Roughness"].default_value = rough
    shader.inputs["Specular IOR Level"].default_value = .27
    return mat


def toon_surface(mat):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image = next(node for node in nodes if node.type=="TEX_IMAGE")
    output = next(node for node in nodes if node.type=="OUTPUT_MATERIAL")
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(image.outputs["Color"],sep.inputs["Color"])
    warm = nodes.new("ShaderNodeMath"); warm.operation = "SUBTRACT"
    links.new(sep.outputs["Red"],warm.inputs[0]); links.new(sep.outputs["Blue"],warm.inputs[1])
    picker = nodes.new("ShaderNodeMapRange")
    picker.inputs["From Min"].default_value = .021
    picker.inputs["From Max"].default_value = .091
    links.new(warm.outputs[0],picker.inputs["Value"])
    height = nodes.new("ShaderNodeAttribute")
    height.attribute_name = "rest_height"
    palette=nodes.new("ShaderNodeValToRGB")
    palette.color_ramp.elements[0].position=.61
    palette.color_ramp.elements[0].color=(.44,.21,1.08,1.)
    palette.color_ramp.elements[1].position=.90
    palette.color_ramp.elements[1].color=(.32,.62,1.52,1.)
    links.new(height.outputs["Fac"],palette.inputs[0])
    tint = nodes.new("ShaderNodeMixRGB")
    links.new(palette.outputs[0],tint.inputs[1])
    tint.inputs[2].default_value = (1.23,1.05,1.03,1.)
    links.new(picker.outputs["Result"],tint.inputs[0])
    paint = nodes.new("ShaderNodeMixRGB"); paint.blend_type = "MULTIPLY"
    paint.inputs[0].default_value = .94
    links.new(image.outputs["Color"],paint.inputs[1]); links.new(tint.outputs[0],paint.inputs[2])
    diffuse = nodes.new("ShaderNodeBsdfDiffuse"); diffuse.inputs["Color"].default_value = BASE_COLOR
    light = nodes.new("ShaderNodeShaderToRGB"); links.new(diffuse.outputs[0],light.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = .09
    ramp.color_ramp.elements[0].color = (.70,.64,.78,1.)
    ramp.color_ramp.elements[1].position = .30
    ramp.color_ramp.elements[1].color = (1.13,1.10,1.17,1.)
    ramp.color_ramp.interpolation = "EASE"
    links.new(light.outputs["Color"],ramp.inputs[0])
    shaded = nodes.new("ShaderNodeMixRGB"); shaded.blend_type = "MULTIPLY"; shaded.inputs[0].default_value = .86
    links.new(paint.outputs[0],shaded.inputs[1]); links.new(ramp.outputs["Color"],shaded.inputs[2])
    emission = nodes.new("ShaderNodeEmission")
    links.new(shaded.outputs[0],emission.inputs["Color"]); links.new(emission.outputs[0],output.inputs["Surface"])
    mat.name = "NOTPB - soft cel color over the supplied atlas"


MINT_MAP = {
    "hips": "Bip001-Pelvis_099", "spine": "Bip001-Spine_0100", "chest": "Bip001-Spine2_0102",
    "neck": "Bip001-Neck_0173", "head": "Bip001-Head_0174",
}
CUTE_MAP = {"hips":"root.x_67","spine":"spine_01.x_54","chest":"spine_03.x_52","neck":"neck.x_1","head":"head.x_0"}
for role, name in (("clav", "Clavicle"), ("arm", "UpperArm"), ("fore", "Forearm"), ("hand", "Hand"), ("thigh", "Thigh"), ("shin", "Calf"), ("foot", "Foot"), ("toe", "Toe0"), ("finger", "Finger2")):
    for side in "LR":
        MINT_MAP[role + side] = f"Bip001-{side}-{name}_"
for role, name in (("clav","shoulder"),("arm","arm_stretch"),("fore","forearm_stretch"),("hand","hand"),("thigh","thigh_stretch"),("shin","leg_stretch"),("foot","foot"),("toe","toes_01"),("finger","middle1")):
    for side in "LR":
        CUTE_MAP[role+side] = f"{name}.{side.lower()}_"


class Actor:
    def __init__(self, label, path, centers, mapping):
        old = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path), guess_original_bind_pose=False,disable_bone_shape=True)
        created = set(bpy.data.objects)-old
        rigs = [obj for obj in created if obj.type=="ARMATURE"]
        self.arm = max(rigs,key=lambda item:len(item.data.bones))
        self.arm.name = label + " - pose rig"
        self.arm.show_in_front = False
        self.label = label
        self.center = centers
        for rig in rigs:
            rig.animation_data_clear()
            for bone in rig.pose.bones:
                bone.matrix_basis = Matrix.Identity(4)
        for obj in created:
            # The Mint upload stages three independent accessories to the left of the actor.
            if obj.type == "MESH" and obj.find_armature() != self.arm:
                obj.hide_viewport = True
                obj.hide_render = True
        self.meshes = [obj for obj in created if obj.type=="MESH" and obj.find_armature() == self.arm]
        self.master = bpy.data.objects.new(label + " - stage position",None)
        bpy.context.collection.objects.link(self.master)
        for obj in created:
            if obj.parent is None:
                obj.parent = self.master
        bpy.context.view_layer.update()
        coords = [obj.matrix_world @ Vector(corner) for obj in self.meshes for corner in obj.bound_box]
        low = min(v.z for v in coords)
        self.scale = 1.66 / (max(v.z for v in coords) - low)
        self.base_z = -self.scale*low
        self.master.scale = (self.scale,)*3
        self.master.location = (centers,0,self.base_z)
        bpy.context.view_layer.update()
        self.arm_zero = self.arm.matrix_world.copy()
        self.from_stage = self.arm_zero.to_quaternion().inverted()
        self.to_stage = self.arm_zero.to_quaternion()
        self.bones = {role: next(b for b in self.arm.pose.bones if b.name.startswith(prefix)) for role,prefix in mapping.items()}
        self.rest_heads = {b.name:b.head_local.copy() for b in self.arm.data.bones}
        self.rest_q = {b.name:b.matrix_local.to_quaternion() for b in self.arm.data.bones}
        self.relative_q, self.relative_p = {},{}
        for b in self.arm.data.bones:
            q = self.rest_q[b.parent.name].inverted() if b.parent else Quaternion()
            p = self.rest_heads[b.parent.name] if b.parent else Vector()
            self.relative_q[b.name] = q @ self.rest_q[b.name]
            self.relative_p[b.name] = q @ (self.rest_heads[b.name]-p)
        self.rest_frame = {
            "hips": orient(self.rest("thighL")-self.rest("thighR"),self.rest("chest")-self.rest("hips")),
            "chest": orient(self.rest("armL")-self.rest("armR"),self.rest("neck")-self.rest("spine")),
        }
        self.rest_sole = {role:(self.arm_zero @ self.rest(role)).z for role in ("footL","footR","toeL","toeR")}
        self.last_key={}
        self.prev_floor=None
        self.hand_depth=None
        self.face_groups = [b for b in self.arm.pose.bones if any(b.name.startswith(prefix) for prefix in ("Bon_Lolip","Bon_colip_", "BON_eyelid_up_", "BON_eyelid_lo_")) and "_end_" not in b.name]
        self.stats={"floor_min":1.0,"floor_max":-1.0,"source_face_bones":len(self.face_groups)}
        if label=="NOTPB":
            for obj in self.meshes:
                coords = np.empty(len(obj.data.vertices)*3, dtype=np.float32)
                obj.data.vertices.foreach_get("co", coords)
                transform = obj.matrix_world[2]
                height = (coords.reshape(-1,3) @ np.array(transform[:3],dtype=np.float32) + transform[3])/1.66
                attr = obj.data.attributes.new(name="rest_height",type="FLOAT",domain="POINT")
                attr.data.foreach_set("value",height.astype(np.float32))
            toon_surface(self.meshes[0].data.materials[0])
        self.sole_adjust = -.02 if label=="NOTPB" else -.369
        print("ACTOR_READY",label,len(self.meshes),len(self.arm.pose.bones),"FACE",len(self.face_groups),flush=True)

    def rest(self,role):
        return self.rest_heads[self.bones[role].name]

    def animate(self,row,frame,refinement,ball_floor):
        points = [self.from_stage @ Vector(value) for value in row["body"]]
        p = points
        hips = central(p[23],p[24]); shoulders=central(p[11],p[12]); torso=shoulders-hips
        vertical = self.from_stage @ Vector((0,0,1.))
        hips_orientation=orient(p[23]-p[24],vertical.lerp(torso.normalized(),.39))
        chest_orientation=orient(p[11]-p[12],torso)
        hips_delta=hips_orientation @ self.rest_frame["hips"].inverted()
        chest_delta=chest_orientation @ self.rest_frame["chest"].inverted()
        computed, heads, targets={},{},{}

        def get(bone):
            if bone.name not in computed:
                q,h=get(bone.parent) if bone.parent else (Quaternion(),Vector())
                computed[bone.name]=q @ self.relative_q[bone.name]
                heads[bone.name]=h + q @ self.relative_p[bone.name]
            return computed[bone.name],heads[bone.name]

        def rotate(role, result):
            b=self.bones[role]
            q,_=get(b)
            k=q.inverted() @ result
            k.normalize()
            if b.name in self.last_key:
                k.make_compatible(self.last_key[b.name])
            targets[b.name]=k
            computed[b.name]=result

        def aim(role, child, direction, mix=1.):
            if direction.length < 1e-5:
                return
            b=self.bones[role]
            q,_=get(b)
            rest_direction=self.rest(child)-self.rest(role)
            local=self.rest_q[b.name].inverted() @ rest_direction
            base=q @ local
            change=base.rotation_difference(direction)
            rotate(role, Quaternion().slerp(change,mix) @ q)

        rotate("hips",hips_delta @ self.rest_q[self.bones["hips"].name])
        rotate("spine",hips_delta.slerp(chest_delta,.53) @ self.rest_q[self.bones["spine"].name])
        rotate("chest",chest_delta @ self.rest_q[self.bones["chest"].name])
        for side,s,e,w,h,k,a,heel,toe,i in (("L",11,13,15,23,25,27,29,31,19),("R",12,14,16,24,26,28,30,32,20)):
            aim("clav"+side,"arm"+side,p[s]-shoulders+torso.normalized()*.045,.27)
            aim("arm"+side,"fore"+side,p[e]-p[s])
            aim("fore"+side,"hand"+side,p[w]-p[e])
            aim("hand"+side,"finger"+side,p[i]-p[w],.84)
            aim("thigh"+side,"shin"+side,p[k]-p[h])
            aim("shin"+side,"foot"+side,p[a]-p[k])
            foot_direction=p[toe]-p[heel]
            if row["visibility"][a]<.53:
                forward=chest_orientation @ Vector((0,-1.,0))
                foot_direction=foot_direction.lerp(forward*.15,.44)
            aim("foot"+side,"toe"+side,foot_direction,.78)
        face_side=p[7]-p[8]
        nose=p[0]-central(p[7],p[8])
        chest_front=chest_orientation @ Vector((0,-1.,0))
        front=normalized(nose-vertical*nose.dot(vertical),chest_front)
        lateral=normalized(vertical.cross(front),chest_orientation @ Vector((1,0,0)))
        ear_horizon=normalized(face_side,lateral)
        if ear_horizon.dot(lateral)>0:
            lateral=lateral.lerp(ear_horizon,.6)
        ratio=min(row["visibility"][7],row["visibility"][8])
        head_aim=orient(lateral,vertical.lerp(normalized(central(p[2],p[5])-central(p[9],p[10]),vertical),.48))
        head_delta=self.rest_frame["chest"].inverted()
        neck_gain=clamp(.22+ratio*.27,0,.59)
        head_gain=clamp(.35+ratio*.40,0,.76)
        rotate("neck",(chest_orientation.slerp(head_aim,neck_gain) @ head_delta) @ self.rest_q[self.bones["neck"].name])
        rotate("head",(chest_orientation.slerp(head_aim,head_gain) @ head_delta) @ self.rest_q[self.bones["head"].name])
        for name,q in targets.items():
            b=self.arm.pose.bones[name]; b.rotation_mode="QUATERNION"; b.rotation_quaternion=q
            self.last_key[name]=q.copy()
            b.keyframe_insert(data_path="rotation_quaternion",frame=frame,group=b.name)
        floor = min((self.arm_zero @ get(self.bones[key])[1]).z - self.rest_sole[key] for key in self.rest_sole)
        floor_shift = clamp(-floor,-.52,.42)
        if refinement and self.prev_floor is not None:
            floor_shift=self.prev_floor*.18 + floor_shift*.82
        self.prev_floor=floor_shift
        vertical_offset=floor_shift + row["lift"]*.80 + (self.sole_adjust if refinement else 0.)
        horizontal_offset=row["x"] * .96
        self.master.location=(self.center+horizontal_offset,0.,self.base_z+vertical_offset)
        self.master.keyframe_insert(data_path="location",frame=frame,group="Source trajectory and ground contact")
        self.stats["floor_min"]=min(self.stats["floor_min"],floor+floor_shift)
        self.stats["floor_max"]=max(self.stats["floor_max"],floor+floor_shift)
        # Local facial bones on the supplied Mint asset can be used without adding physics.
        jaw,blink_l,blink_r,smile_l,smile_r,brow,pucker,funnel=row["face"]
        for b in self.face_groups:
            side=b.name.split("_")[-2]
            displacement=Vector()
            if b.name.startswith("Bon_Lolip"):
                displacement.z=-clamp(jaw-.075,0,.72)*.015
                displacement.y=-clamp(funnel+pucker)*.003
            elif b.name.startswith("Bon_colip"):
                displacement.z=(smile_l if side=="L" else smile_r)*.010 - jaw*.002
            elif b.name.startswith("BON_eyelid_up"):
                displacement.z=-clamp((blink_l if side=="L" else blink_r)-.13,0,.85)*.013
            else:
                displacement.z=clamp((blink_l if side=="L" else blink_r)-.13,0,.85)*.005
            convert=(self.to_stage @ self.rest_q[b.name]).inverted()
            b.location=(convert @ displacement)/self.scale
            b.keyframe_insert(data_path="location",frame=frame,group="Facial performance")

        if row["ball"]:
            bx,by,radius,hand,strength = row["ball"]
            source_hips = central(Vector(row["img"][23]),Vector(row["img"][24]))
            side="L" if hand==0 else "R"
            hand_index=15 if hand==0 else 16
            hand_position=self.arm_zero @ get(self.bones["hand"+side])[1]
            delta=Vector((horizontal_offset,0,vertical_offset))
            hand_position+=delta
            lowest_ball = FLOOR_Z+BALL_RADIUS
            projected = Vector((self.center+horizontal_offset+(bx-source_hips.x)*3.25,-.22,max(lowest_ball,lowest_ball+(ball_floor-by)*2.04)))
            if self.hand_depth is None:
                self.hand_depth=hand_position.y-.07
            if strength>.30:
                self.hand_depth=self.hand_depth*.34+(hand_position.y-.075)*.66
            projected.y=clamp(self.hand_depth,-.56,.26)
            wrist=row["img"][hand_index]
            touch_offset = Vector(((bx-wrist[0])*3.25,-.040,-(by-wrist[1])*1.78))
            palm_dir = normalized(self.to_stage @ (p[19 if hand==0 else 20]-p[hand_index]),touch_offset.normalized())
            palm_position = hand_position + palm_dir*.046
            touched=palm_position+touch_offset.normalized()*(BALL_RADIUS+.005)
            attachment = clamp((strength-.32)/.48)
            attachment = attachment*attachment*(3-2*attachment)
            point=projected.lerp(touched,attachment)
            point.z=max(lowest_ball,point.z)
            self.ball.location=point; self.ball.scale=(1.,)*3
            self.ball.rotation_euler=(frame*.147,frame*.116,frame*.052)
            self.ball.keyframe_insert(data_path="location",frame=frame,group="Ball track")
            self.ball.keyframe_insert(data_path="rotation_euler",frame=frame,group="Ball spin")
        else:
            self.ball.scale=(0.,)*3
        if frame == 1 or bool(row["ball"]) != getattr(self,"ball_last_visible",None):
            self.ball.keyframe_insert(data_path="scale",frame=max(1,frame-1),group="Ball visibility") if frame>1 and row["ball"] else None
            if frame>1 and not row["ball"]:
                self.ball.scale=(1.,)*3; self.ball.keyframe_insert(data_path="scale",frame=frame-1,group="Ball visibility"); self.ball.scale=(0.,)*3
            self.ball.keyframe_insert(data_path="scale",frame=frame,group="Ball visibility")
        self.ball_last_visible=bool(row["ball"])


def build_ball(name, orange, grooves):
    radius=BALL_RADIUS
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=radius)
    ball=bpy.context.object
    ball.name=name+" - basketball"
    ball.data.materials.append(orange)
    bpy.ops.object.shade_smooth()
    curve=bpy.data.curves.new(name+" - seams","CURVE")
    curve.dimensions="3D"; curve.resolution_u=2; curve.bevel_depth=.00265; curve.bevel_resolution=3
    for k in range(4):
        spline=curve.splines.new("POLY"); spline.points.add(95); spline.use_cyclic_u=True
        for i,point in enumerate(spline.points):
            t=i*math.tau/96
            if k==0:
                p=(math.cos(t),math.sin(t),0)
            elif k==1:
                p=(0,math.cos(t),math.sin(t))
            else:
                x=(1 if k==2 else -1)*(.54+.20*math.cos(2*t))
                ring=math.sqrt(1-x*x)
                p=(x,ring*math.cos(t),ring*math.sin(t))
            point.co=tuple(pv*(radius+.0004) for pv in p)+(1,)
    seams=bpy.data.objects.new(name+" - black channels",curve)
    bpy.context.collection.objects.link(seams); seams.parent=ball; seams.data.materials.append(grooves)
    return ball


def box(name,dimensions,location,mat):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object; obj.name=name; obj.dimensions=dimensions
    obj.data.materials.append(mat)
    return obj


def area(name,position,power,size,color):
    data=bpy.data.lights.new(name,"AREA")
    data.energy=power; data.shape="DISK"; data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(obj)
    obj.location=position; obj.rotation_euler=(Vector((0,0,.90))-obj.location).to_track_quat("-Z","Y").to_euler()


def stage(scene):
    gray=material("Stage - blue-gray",(.062,.084,.133))
    plum=material("Left lane - violet",(.115,.068,.192))
    aqua=material("Right lane - teal",(.041,.132,.151))
    box("Matte floor",(24,18,.10),(0,1,FLOOR_Z-.05),gray)
    box("Violet backdrop",(4.2,.08,4.),(-2.1,2.5,1.7),plum)
    box("Teal backdrop",(4.2,.08,4.),(2.1,2.5,1.7),aqua)
    area("Main softbox",(-1.8,-4.2,5.2),730,5.1,(1.,.94,.89))
    area("Fill",(3.2,-2.0,3.5),440,4.4,(.86,.94,1.0))
    area("Rim",(0,2.0,4.2),350,3.5,(.86,.88,1.0))
    cam_data=bpy.data.cameras.new("Front comparison")
    cam=bpy.data.objects.new("Front comparison",cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location=(0,-10,1.91); cam.rotation_euler=(Vector((0,.15,1.04))-cam.location).to_track_quat("-Z","Y").to_euler()
    cam_data.type="ORTHO"; cam_data.ortho_scale=5.35; scene.camera=cam
    world=bpy.data.worlds.new("Soft ambient")
    world.use_nodes=True; scene.world=world
    world.node_tree.nodes.get("Background").inputs[0].default_value=(.14,.19,.26,1.)
    world.node_tree.nodes.get("Background").inputs[1].default_value=.48


def refine_mint_contact(scene,mint,cute,rows):
    # This rig's foot joints sit far below its visible soles. Measure the skinned
    # mesh itself at half-frame rate and keep the measured source jumps.
    body=next(obj for obj in mint.meshes if obj.name=="Object_153")
    for obj in cute.meshes:
        obj.hide_viewport=True
    samples=[]; correction=[]
    for index in range(0,len(rows),2):
        scene.frame_set(index+1)
        ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        sole=min((ev.matrix_world @ Vector(corner)).z for corner in ev.bound_box)
        correction.append(clamp(FLOOR_Z+.007+rows[index]["lift"]*.80-sole,-.12,.12))
        samples.append(index)
    smooth=np.convolve(np.pad(correction,1,mode="edge"),[.16,.68,.16],mode="valid")
    for index,(row,adjustment) in enumerate(zip(rows,np.interp(range(len(rows)),samples,smooth))):
        frame=index+1
        scene.frame_set(frame)
        mint.master.location.z+=float(adjustment)
        mint.master.keyframe_insert(data_path="location",index=2,frame=frame,group="Source trajectory and ground contact")
        if row["ball"]:
            attachment=clamp((row["ball"][4]-.32)/.48)
            attachment=attachment*attachment*(3-2*attachment)
            mint.ball.location.z=max(FLOOR_Z+BALL_RADIUS,mint.ball.location.z+float(adjustment)*attachment)
            mint.ball.keyframe_insert(data_path="location",index=2,frame=frame,group="Ball track")
    for obj in cute.meshes:
        obj.hide_viewport=False
    print("MINT_SOLE_CORRECTION",round(min(correction),4),round(max(correction),4),flush=True)


def resolve_floor_penetration(scene,mint_root,mint_body,mint_ball,cute_meshes,rows):
    for obj in cute_meshes:
        obj.hide_viewport=True
    gaps=[]
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame)
        mesh=mint_body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        gaps.append(min((mesh.matrix_world @ Vector(corner)).z for corner in mesh.bound_box)-FLOOR_Z)
    correction=np.maximum(0.,-.008-np.array(gaps))
    # Only bake around real floor crossings. Keep a brief lead and release so
    # the corrective movement does not start and stop on the contact frame.
    correction[correction<.019]=0.
    padded=np.pad(correction,2)
    feather=np.maximum.reduce((correction,padded[1:-3]*.40,padded[3:-1]*.40,padded[:-4]*.10,padded[4:]*.10))
    repaired=[]
    for i,adjustment in enumerate(feather):
        if adjustment <= .001:
            continue
        frame=scene.frame_start+i
        scene.frame_set(frame)
        mint_root.location.z+=float(adjustment)
        mint_root.keyframe_insert(data_path="location",index=2,frame=frame,group="Source trajectory and ground contact")
        tracked=rows[i]["ball"]
        if tracked and tracked[4]>.55:
            mint_ball.location.z+=float(adjustment)*clamp((tracked[4]-.55)/.25)
            mint_ball.keyframe_insert(data_path="location",index=2,frame=frame,group="Ball track")
        repaired.append(frame)
    for obj in cute_meshes:
        obj.hide_viewport=False
    print("MINT_PENETRATION_REPAIR",len(repaired),"FRAMES",repaired,flush=True)
    return repaired


def finish_project(scene):
    for label,frame in MARKERS:
        if not scene.timeline_markers.get(label):
            scene.timeline_markers.new(label, frame=frame)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                space=area.spaces.active
                space.region_3d.view_perspective="CAMERA"
                space.region_3d.view_camera_zoom=12
                space.overlay.show_overlays=False
    scene.frame_set(1)


def scene_setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    data=json.loads((HERE/"motion.json").read_text(encoding="utf-8"))
    source_root=Path.home()/"Downloads"
    cute=Actor("NOTPB",source_root/"cute_anime_girl_-_fully_rigged_3d_model.glb",-1.37,CUTE_MAP)
    mint=Actor("Mint",source_root/"mint_swimsuit_animated-_neverness_to_everness.glb",1.37,MINT_MAP)
    orange=material("Basketball - orange pebble leather",(.90,.22,.033),.76)
    grooves=material("Basketball - charcoal channels",(.021,.015,.018),.91)
    for actor in (cute,mint):
        actor.ball=build_ball(actor.label,orange,grooves)
    scene=bpy.context.scene
    scene.render.fps=round(data["fps"]); scene.frame_start=1; scene.frame_end=len(data["frames"])
    scene["Source_seconds"]=data["source_span"]
    scene["Reference"]="https://www.bilibili.com/video/BV15b41157i4/"
    # Floor on screen changes with the source camera perspective. The local maxima
    # are the observed bounce frames, where the rendered ball must meet the stage.
    bounces = ((18.76,.881),(19.24,.881),(19.96,.911),(20.88,.942),(21.40,.948),
               (22.04,.917),(22.92,.935),(23.72,.924),(24.68,.874),(26.88,.866),(27.88,.927))
    bounce_times,bounce_positions=zip(*bounces)
    for frame,row in enumerate(data["frames"],1):
        ball_floor=float(np.interp(row["t"],bounce_times,bounce_positions))
        for actor in (cute,mint):
            actor.animate(row,frame,mode!="draft",ball_floor)
        if frame % 125==0:
            print("KEYFRAMES",frame,flush=True)
    if mode!="draft":
        refine_mint_contact(scene,mint,cute,data["frames"])
        resolve_floor_penetration(scene,mint.master,next(obj for obj in mint.meshes if obj.name=="Object_153"),mint.ball,cute.meshes,data["frames"])
    for actor in (cute,mint):
        print("ACTOR_QA",actor.label,actor.stats,flush=True)
    stage(scene)
    scene.render.engine="BLENDER_EEVEE"
    if hasattr(scene.eevee,"taa_samples"):
        scene.eevee.taa_samples=12
    if hasattr(scene.eevee,"taa_render_samples"):
        scene.eevee.taa_render_samples=12
    scene.view_settings.view_transform="Standard"
    scene.render.resolution_x=1280; scene.render.resolution_y=640; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False
    scene.render.filepath="//frames/"
    finish_project(scene)
    # All input textures are embedded in the GLBs, then packed into the editable Blender scene.
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(root/("characterControl_draft.blend" if mode=="draft" else "characterControl.blend")))
    return scene,data


def previews(scene,data):
    scene.render.resolution_percentage=62
    if hasattr(scene.eevee,"taa_render_samples"):
        scene.eevee.taa_render_samples=10
    out=root/("checks" if mode=="draft" else "checks_refined"); out.mkdir(exist_ok=True)
    for t in (18.8,20.00,23.2,25.6,28.4,30.4,32.0,39.0,45.0,51.9):
        frame=round((t-data["source_span"][0])*data["fps"])+1
        scene.frame_set(max(scene.frame_start,min(scene.frame_end,frame)))
        scene.render.filepath=str(out/f"pose_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    scene,data=scene_setup()
    previews(scene,data)
