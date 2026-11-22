"""Adapt the three existing mermaid takes using stroke and tail references."""

from bisect import bisect_right
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Quaternion, Vector


HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE if (HERE/"animate_mermaid.py").is_file() else HERE.parent))
from animate_mermaid import BACK, FPS, RIGHT, SECTIONS, TAU, UP, Swimmer, body_rotation, direction, eased, route


# Each row gives cycle time, wrist goal, elbow-plane guide, and wrist pitch.
# Points are metrics relative to the shoulder: lateral, ventral, and forward.
# The returning arm draws forward underwater with its palm feathered.
CRAWL=(
    (.00, (.048,-.068,.422), (.102,-.018,.200), -.08),
    (.15, (.106,-.153,.295), (.160,-.026,.120), .14),
    (.32, (.129,-.235,.092), (.176,-.054,.044), .22),
    (.43, (.086,-.238,-.095), (.151,-.071,-.016), .15),
    (.58, (.060,-.117,-.403), (.123,-.044,-.145), -.05),
    (.72, (.158,-.110,-.232), (.205,-.020,-.127), -.17),
    (.87, (.154,-.091,.163), (.196,-.009,.081), -.19),
)


def frame_value(row):
    return np.array((*row[1],*row[2],row[3]))


def stroke_cycle(phase):
    t=phase%1.
    times=[row[0] for row in CRAWL]
    i=bisect_right(times,t)-1
    before=CRAWL[(i-1)%len(CRAWL)]
    start=CRAWL[i]
    end=CRAWL[(i+1)%len(CRAWL)]
    after=CRAWL[(i+2)%len(CRAWL)]
    a,b,c,d=map(frame_value,(before,start,end,after))
    ta=before[0]-(1. if before[0]>start[0] else 0.)
    tb=start[0]
    tc=end[0]+(1. if end[0]<=tb else 0.)
    td=after[0]+(1. if after[0]<=end[0] or tc>=1. else 0.)
    span=tc-tb
    u=(t-tb)/span
    u2,u3=u*u,u*u*u
    return ((2*u3-3*u2+1)*b+(u3-2*u2+u)*(c-a)*(span/(tc-ta))
            +(-2*u3+3*u2)*c+(u3-u2)*(d-b)*(span/(td-tb)))


def human_arms(shot,t,phase,seconds,side):
    if shot==0:
        side_phase=(phase+(.50 if side<0 else 0.))%1.
        values=stroke_cycle(side_phase)
        wrist=Vector((side*values[0],values[1],values[2]))
        elbow=Vector((side*values[3],values[4],values[5]))
        # Broad palm through the pull, then turn the edge into the recovery.
        feather=eased((side_phase-.54)/.16)*(1.-eased((side_phase-.90)/.10))
        return wrist,elbow,values[6],side*(.18+.79*feather)
    if shot==1:
        fold=eased((t-.115)/.215)*(1.-eased((t-.69)/.21))
        stroke=math.sin(TAU*t+.3)*side
        open_wrist=Vector((side*(.177+.05*stroke),-.166,-.225+.095*stroke))
        open_elbow=Vector((side*.180,-.036,-.105))
        reach=Vector((-side*.071,-.051,.416))
        reach_elbow=Vector((side*.043,-.032,.206))
        return open_wrist.lerp(reach,fold),open_elbow.lerp(reach_elbow,fold),-.07*fold,side*(.30-.16*fold)
    p=TAU*(.91*seconds+(.36 if side<0 else 0.))
    # Small fore-and-back figure eights. The hands stay ahead of the ribs
    # while the upper arm supports a relaxed, flexed elbow.
    wrist=Vector((side*(.217+.077*math.sin(p)),-.235+.031*math.sin(2*p+.40),
                  -.161+.026*math.sin(2*p-.17)))
    elbow=Vector((side*(.140+.025*math.sin(p+.64)),-.061,-.156))
    return wrist,elbow,.16*math.cos(p),side*(.43*math.cos(p+.31))


def solve_arm(wrist,elbow_hint,upper_length,lower_length):
    direction=wrist.normalized()
    distance=min(upper_length+lower_length-.003,max(wrist.length,.045))
    projected=(upper_length*upper_length-lower_length*lower_length+distance*distance)/(2.*distance)
    rise=math.sqrt(max(.0,upper_length*upper_length-projected*projected))
    plane=elbow_hint-direction*elbow_hint.dot(direction)
    if plane.length_squared<1e-6:
        plane=RIGHT-direction*direction.x
    elbow=direction*projected+plane.normalized()*rise
    return elbow,direction*distance-elbow


def follow_rotation(shot,t,arm_phase,phase):
    if shot==0:
        roll=-1.09 + .37*math.sin(TAU*t+.45) - .18*math.sin(2*TAU*t) + .12*math.sin(TAU*arm_phase)
        return body_rotation(direction(shot,t),roll)
    if shot==1:
        roll=-1.04 + TAU*(t-.17*math.sin(TAU*t)/TAU)
        return body_rotation(direction(shot,t),roll)
    return (Quaternion(UP,.27+.092*math.sin(TAU*t)) @ Quaternion(RIGHT,.021*math.sin(phase+.2))
            @ Quaternion(BACK,.016*math.cos(phase+.3)))


class StudySwimmer(Swimmer):
    def add_fin_shape(self):
        shape=self.mesh.data.shape_keys
        shape.animation_data_clear()
        for key in shape.key_blocks:
            if key.name!="Basis":
                key.value=0.
        return shape.key_blocks["Fin membrane flex"]

    def __init__(self):
        super().__init__()
        stations=[self.bones[name].bone.head_local.copy() for name in self.tail]
        stations.append(self.bones[self.tail[-1]].bone.tail_local.copy())
        self.segments=[b-a for a,b in zip(stations,stations[1:])]
        distance=sum(v.length for v in self.segments)
        self.stations=[0.]
        for segment in self.segments:
            self.stations.append(self.stations[-1]+segment.length/distance)
        self.fan=self.mesh.shape_key_add(name="Fin spread and unload",from_mix=False)
        self.fan.slider_min=-1.
        self.fan.slider_max=1.
        self.fan.value=0.
        for point,v in zip(self.fan.data,self.mesh.data.vertices):
            width=eased((-.045-v.co.z)/.29)
            point.co.x+=v.co.x*.17*width
            point.co.y-=.018*width
        self.tail_phase=.44
        self.arm_phase=.02

    def fish_tail(self,frame,shot,t,speed,phase):
        boost=eased(.39+.50*math.sin(TAU*(t*2.02)-.3))
        beat=(.34+.081*speed)*(.83+.26*boost) if shot==0 else .347 if shot==1 else .289
        bank=.92*math.sin(TAU*t+.30) if shot==0 else .63*math.sin(TAU*t+.34) if shot==1 else .41*math.sin(TAU*t)
        wave_angle=4.70 if shot<2 else 4.48
        bias=.071 if shot<2 else .198
        lateral=.57 if shot<2 else .78
        offsets=[]
        for s in self.stations:
            # The wave is defined by centerline amplitude and distance
            # from the waist; segment lengths stay fixed in the rig.
            envelope=beat*(.13*s+.87*s**2.28)
            lag=phase-wave_angle*s
            y=bias*s*s+envelope*(math.sin(lag)+.14*math.sin(2*lag-.75))
            x=lateral*envelope*math.sin(lag+.86)+bank*.095*s*s
            offsets.append(Vector((x,y,0.)))
        previous_absolute=None
        for i,name in enumerate(self.tail):
            bone=self.bones[name]
            parent=bone.parent
            if i==0:
                previous_absolute=parent.matrix.to_quaternion()
            neutral=previous_absolute @ self.rest[parent.name].inverted() @ self.rest[name]
            segment=self.segments[i]
            goal=(segment+offsets[i+1]-offsets[i]).normalized()
            absolute=segment.rotation_difference(goal) @ self.rest[name]
            # Only a small amount of axial feathering is needed at the fluke.
            absolute=Quaternion(goal,.070*self.stations[i+1]*math.cos(phase-3.2)) @ absolute
            self.bone_key(name,neutral.inverted() @ absolute,frame)
            previous_absolute=absolute
        fin_phase=phase-wave_angle-.61
        self.fin.value=(.61+.15*boost)*math.sin(fin_phase)+.11*math.sin(fin_phase*2-.5)
        self.fan.value=.26+.47*math.cos(fin_phase-.27)-.25*(1.-boost)
        self.fin.keyframe_insert(data_path="value",frame=frame,group="Fin membrane")
        self.fan.keyframe_insert(data_path="value",frame=frame,group="Fin membrane")

    def bake_frame(self,shot,index,count,frame):
        t=index/(count-1)
        seconds=index/FPS
        duration=(count-1)/FPS
        speed=(route(shot,t+.002)-route(shot,t-.002)).length/(.004*duration)
        if index==0:
            self.tail_phase=.44+.45*shot
            self.arm_phase=.032
        else:
            rate=(.81+.55*speed) if shot==0 else (.87+.40*speed) if shot==1 else (.93+.078*math.sin(TAU*t))
            self.tail_phase+=TAU*rate/FPS
            self.arm_phase+=(.53+.22*speed)/FPS
        phase=self.tail_phase
        root=follow_rotation(shot,t,self.arm_phase,phase)
        if index and self.root_previous:
            root.make_compatible(self.root_previous)
        self.root_previous=root.copy()
        self.rig.rotation_quaternion=root
        self.rig.location=route(shot,t)-root@self.pivot
        self.rig.keyframe_insert(data_path="rotation_quaternion",frame=frame,group="Swim trajectory")
        self.rig.keyframe_insert(data_path="location",frame=frame,group="Swim trajectory")
        twist=(.118*math.sin(TAU*self.arm_phase-.68) if shot==0 else
               .035*math.sin(TAU*t+.6) if shot==1 else .024*math.sin(TAU*.91*seconds))
        self.bend("chest",frame,.027*math.sin(phase+.23),.045*math.sin(TAU*t+.43) if shot<2 else .012,twist)
        self.bend("head",frame,(-.22 if shot<2 else -.015)+.032*math.sin(phase*.60),
                  .027*math.sin(TAU*t),-.66*twist)
        for side in "LR":
            sign=1 if side=="L" else -1
            for i,name in enumerate(self.hair[side]):
                trail=phase*.54-.43*i+.27*sign
                self.bend(name,frame,(.018+.021*i/7)*math.sin(trail)+(.038 if shot<2 else .015),
                          .021*math.cos(trail-.73)+.012*sign*math.sin(TAU*t),
                          .014*math.sin(trail-.22))
        bpy.context.view_layer.update()
        self.fish_tail(frame,shot,t,speed,phase)
        self.place_arms(shot,t,self.arm_phase,seconds,frame)

    def place_arms(self,shot,t,arm_phase,seconds,frame):
        targets={}
        for sign,side in ((1,"L"),(-1,"R")):
            wrist,hint,pitch,feather=human_arms(shot,t,arm_phase,seconds,sign)
            upper="upper_arm_fk."+side
            lower="forearm_fk."+side
            u,v=solve_arm(wrist,hint,self.bones[upper].length,self.bones[lower].length)
            self.aim(upper,u,frame)
            targets[side]=(lower,v,pitch,feather)
        bpy.context.view_layer.update()
        for side,(lower,vector,pitch,feather) in targets.items():
            self.aim(lower,vector,frame)
            self.bone_key("hand_fk."+side,Quaternion(BACK,feather) @ Quaternion(RIGHT,pitch),frame)


def keep_tail_in_shot():
    camera=bpy.data.cameras["Treading hover"]
    camera.lens=39.5
    camera.shift_y=-.022


def main():
    out=Path(sys.argv[sys.argv.index("--")+1]).resolve()
    out.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    scene.frame_set(1)
    swimmer=StudySwimmer()
    first=1
    for shot,(name,count) in enumerate(SECTIONS):
        for local in range(count):
            frame=first+local
            scene.frame_set(frame)
            swimmer.bake_frame(shot,local,count,frame)
        print("REFERENCE_STROKE",name,first,first+count-1,flush=True)
        first+=count
    scene["Upper-body reference"]="USMS underwater-recovery freestyle drill; Swim England treading scull"
    scene["Tail reference"]="Posterior body-caudal wave; narrow waist motion, increasing fin displacement and phase lag"
    keep_tail_in_shot()
    scene.frame_set(1)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"Mermaid_stroke_study.blend"))
    scene.render.resolution_percentage=66
    scene.eevee.taa_render_samples=7
    for frame in (17,28,46,78,132,182,219,252,282,327,365,390,420,462,486):
        scene.frame_set(frame)
        scene.render.filepath=str(out/f"stroke_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    main()
