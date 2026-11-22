import math

import bpy
import numpy as np
from mathutils import Quaternion, Vector


def unit(vector, fallback):
    return vector.normalized() if vector.length_squared>1e-10 else fallback


def clearance(point, rest, capsules):
    for start,end,radius in capsules:
        axis=end-start
        length=axis.length_squared
        if length<1e-8:
            continue
        def nearest(value):
            t=max(0.,min(1.,(value-start).dot(axis)/length))
            return start+axis*t
        outside=rest-nearest(rest)
        # An authored inner lock or strap may sit against the body at rest.
        # Use its rest spacing as the collider limit in that case.
        limit=min(radius,max(0.,outside.length-.007))
        base=nearest(point)
        away=point-base
        if away.length<limit:
            point=base+unit(away,outside.normalized())*limit
    return point


class Drag:
    def __init__(self, lag, drop):
        self.lag=lag
        self.drop=Vector((0.,0.,-drop))
        self.point=None

    def predict(self,target,dt):
        if self.point is None:
            self.point=target.copy()
        # A first-order response retains lag and gravity bias without spring
        # overshoot when the character stops or the direction reverses.
        return self.point.lerp(target+self.drop,1.-math.exp(-dt/self.lag))

    def commit(self,point):
        self.point=point.copy()


class Strand:
    def __init__(self,actor,bone,kind):
        self.bone=bone
        rest=bone.bone.matrix_local
        parent=bone.parent.bone.matrix_local
        self.relative=parent.inverted() @ rest
        tip=next((child.bone.head_local for child in bone.children if "_end_" not in child.name),None)
        if tip is None:
            tip=bone.bone.tail_local
        self.tip=rest.inverted() @ tip
        self.length=max(.007,self.tip.length*actor.scale)
        self.limit=.088 if kind=="hair" else .112
        if self.length<.035:
            self.limit*=.72
        self.drag=Drag(.060,.0037) if kind=="hair" else Drag(.047,.0046)
        self.previous=Quaternion()
        bone.rotation_mode="QUATERNION"

    def bake(self,world,computed,capsules,frame,dt):
        parent=self.bone.parent
        base=computed.get(parent.name)
        if base is None:
            base=world @ parent.matrix
        local=base @ self.relative
        head=local.translation
        ideal=local.to_quaternion() @ unit(self.tip,Vector((0,1,0)))
        target=head+ideal*self.length
        relaxed=clearance(self.drag.predict(target,dt),target,capsules)
        direction=unit(relaxed-head,ideal)
        swing=ideal.rotation_difference(direction)
        angle=swing.angle
        if angle>self.limit:
            swing=Quaternion(swing.axis,self.limit)
        self.drag.commit(head+(swing @ ideal)*self.length)
        world_rotation=local.to_quaternion()
        q=world_rotation.inverted() @ swing @ world_rotation
        q.make_compatible(self.previous)
        self.bone.rotation_quaternion=q
        self.bone.keyframe_insert(data_path="rotation_quaternion",frame=frame,group="Hair and cloth dynamics")
        self.previous=q
        # Parent motion drives the following point in each strand immediately.
        computed[self.bone.name]=local @ q.to_matrix().to_4x4()


class SurfaceSpring:
    def __init__(self,actor,bone_role,point,node,mesh,kind):
        self.actor=actor
        self.bone=actor.bones[bone_role]
        bind=actor.arm_zero @ self.bone.bone.matrix_local
        self.point=bind.inverted() @ Vector(point)
        self.node=node
        self.mesh=mesh
        self.hair=kind.startswith("hair")
        if actor.label=="NOTPB":
            self.maximum=.132 if self.hair else .047
            self.drag=Drag(.112,.006) if self.hair else Drag(.080,.004)
        else:
            self.maximum=.024
            self.drag=Drag(.052,.003)

    def bake(self,world,capsules,frame,dt):
        target=world @ self.bone.matrix @ self.point
        prediction=self.drag.predict(target,dt)
        point=clearance(prediction,target,capsules) if self.hair else prediction
        offset=point-target
        if offset.length>self.maximum:
            offset=offset.normalized()*self.maximum
        self.drag.commit(target+offset)
        local=self.mesh.matrix_world.to_3x3().inverted() @ offset
        for i,component in enumerate(local):
            self.node.inputs[i].default_value=component
            self.node.inputs[i].keyframe_insert(data_path="default_value",frame=frame)


def ramp(values,low,high):
    t=np.clip((values-low)/(high-low),0.,1.)
    return t*t*(3.-2.*t)


def rest_coordinates(obj,actor):
    data=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get("co",data)
    to_world=np.array(obj.matrix_world,dtype=np.float32)
    xyz=data.reshape(-1,3) @ to_world[:3,:3].T + to_world[:3,3]
    xyz+=np.array(actor.arm_zero.translation-actor.arm.matrix_world.translation,dtype=np.float32)
    xyz[:,0]-=actor.center
    return xyz


def neutral_colors(obj,atlas):
    if atlas is None:
        return np.ones(len(obj.data.vertices),dtype=np.float32)
    loops=obj.data.loops
    indices=np.empty(len(loops),dtype=np.int32)
    uv=np.empty(len(loops)*2,dtype=np.float32)
    loops.foreach_get("vertex_index",indices)
    obj.data.uv_layers.active.uv.foreach_get("vector",uv)
    vertex_uv=np.zeros((len(obj.data.vertices),2),dtype=np.float32)
    vertex_uv[indices]=uv.reshape(-1,2)
    size=np.array((atlas.shape[1],atlas.shape[0]))
    pixel=np.clip((vertex_uv*size).astype(np.int32),0,size-1)
    color=atlas[pixel[:,1],pixel[:,0],:3]
    return 1.-ramp(color[:,0]-color[:,2],.026,.088)


def deform_surfaces(actor,objects,regions,atlas=None):
    group=bpy.data.node_groups.new(actor.label+" - simulated hair and cloth","GeometryNodeTree")
    group.interface.new_socket(name="Geometry",in_out="INPUT",socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry",in_out="OUTPUT",socket_type="NodeSocketGeometry")
    nodes,links=group.nodes,group.links
    source=nodes.new("NodeGroupInput")
    out=nodes.new("NodeGroupOutput")
    move=nodes.new("GeometryNodeSetPosition")
    links.new(source.outputs["Geometry"],move.inputs["Geometry"])
    links.new(move.outputs["Geometry"],out.inputs["Geometry"])
    springs=[]
    offset=None
    for kind,(role,target) in regions.items():
        attr=nodes.new("GeometryNodeInputNamedAttribute")
        attr.data_type="FLOAT"
        attr.inputs["Name"].default_value=f"{kind}_simulation_weight"
        vector=nodes.new("ShaderNodeCombineXYZ")
        vector.label=f"{kind.replace('_',' ').title()} drag offset"
        scale=nodes.new("ShaderNodeVectorMath")
        scale.operation="SCALE"
        links.new(vector.outputs["Vector"],scale.inputs[0])
        links.new(attr.outputs["Attribute"],scale.inputs["Scale"])
        if offset is None:
            offset=scale.outputs["Vector"]
        else:
            add=nodes.new("ShaderNodeVectorMath")
            add.operation="ADD"
            links.new(offset,add.inputs[0])
            links.new(scale.outputs["Vector"],add.inputs[1])
            offset=add.outputs["Vector"]
        springs.append(SurfaceSpring(actor,role,target,vector,objects[0],kind))
    links.new(offset,move.inputs["Offset"])
    counts={kind:0 for kind in regions}
    for obj in objects:
        x,y,z=rest_coordinates(obj,actor).T
        z/=actor.height
        neutral=neutral_colors(obj,atlas)
        for kind in regions:
            if kind.startswith("hair"):
                behind=ramp(y,-.040,.096)
                sides=ramp(np.abs(x),.115,.173)*ramp(y,-.164,-.045)
                mask=np.maximum(behind,sides)*ramp(z,.506,.577)*(1.-ramp(z,.727,.937))
                mask*=.16+.84*neutral
            elif actor.label=="NOTPB":
                shell=np.sqrt(x*x+(y+.036)**2)
                mask=(ramp(z,.415,.454)*(1.-ramp(z,.475,.555)))*ramp(shell,.087,.148)*neutral
            else:
                mask=ramp(z,.475,.503)*(1.-ramp(z,.522,.600))
            if kind.endswith(("_left","_right")):
                blended_side=ramp(x,-.135,.135)
                mask*=blended_side if kind.endswith("_left") else 1.-blended_side
            attr=obj.data.attributes.new(name=f"{kind}_simulation_weight",type="FLOAT",domain="POINT")
            attr.data.foreach_set("value",mask.astype(np.float32))
            counts[kind]+=int(np.count_nonzero(mask>.15))
        mod=obj.modifiers.new(name="Baked fabric and hair lag",type="NODES")
        mod.node_group=group
    print("SURFACE_SIMULATION",actor.label,counts,flush=True)
    return springs


def bake_secondary(scene,cute,mint):
    scene.frame_set(1)
    image=next(node.image for node in cute.meshes[0].data.materials[0].node_tree.nodes if node.type=="TEX_IMAGE")
    atlas=np.empty(len(image.pixels),dtype=np.float32)
    image.pixels.foreach_get(atlas)
    atlas=atlas.reshape(image.size[1],image.size[0],4)
    short_springs=deform_surfaces(cute,cute.meshes,{
        "hair_left":("head",(cute.center+.145,.202,cute.height*.647)),
        "hair_right":("head",(cute.center-.145,.202,cute.height*.647)),
        "cloth_left":("hips",(cute.center+.151,.040,cute.height*.459)),
        "cloth_right":("hips",(cute.center-.151,.040,cute.height*.459)),
    },atlas)
    mint_skirt=next(obj for obj in mint.meshes if obj.name=="Object_155")
    mint_springs=deform_surfaces(mint,[mint_skirt],{"cloth":("hips",(mint.center,.075,mint.height*.531))})
    weighted={group.name for obj in mint.meshes for group in obj.vertex_groups}
    names=[b for b in mint.arm.pose.bones if b.name in weighted and "_end_" not in b.name
           and any(word in b.name.lower() for word in ("hair", "piaodai", "qun"))]
    names.sort(key=lambda bone:len(bone.parent_recursive))
    strands=[Strand(mint,bone,"hair" if "hair" in bone.name.lower() else "cloth") for bone in names]
    print("STRAND_SIMULATION",len(strands),"degree-limited nodes",flush=True)
    dt=1/scene.render.fps
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame)
        for actor,surfaces in ((cute,short_springs),(mint,mint_springs)):
            world=actor.arm.matrix_world
            hip=world @ actor.bones["hips"].head
            chest=world @ actor.bones["chest"].head
            capsules=[(hip,chest,.133 if actor.label=="NOTPB" else .144)]
            for side in "LR":
                start=world @ actor.bones["thigh"+side].head
                end=world @ actor.bones["shin"+side].head
                capsules.append((start,end,.066))
            for spring in surfaces:
                spring.bake(world,capsules,frame,dt)
            if actor is mint:
                computed={}
                for strand in strands:
                    strand.bake(world,computed,capsules,frame,dt)
        if frame%200==0:
            print("SIMULATION_FRAME",frame,flush=True)
