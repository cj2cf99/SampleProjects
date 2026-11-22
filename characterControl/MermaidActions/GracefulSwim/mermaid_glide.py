"""Give the existing colored mermaid restrained upper-body choreography."""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Quaternion, Vector


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / "swim_reference.py").exists() else HERE.parent / "ColoredSwim"))
from swim_reference import BACK, FPS, RIGHT, SECTIONS, TAU, UP, Swimmer, solve_arm


# Wrist target, elbow guide, then wrist pitch and roll. The vectors are relative
# to the shoulder in rig space: outward, behind the chest, and toward the head.
DRIFT = (.098, -.084, -.358, .113, -.018, -.170, -.055, .11)
ARRIVE = (.176, -.152, -.202, .171, -.043, -.086, .046, .17)
GUIDE = (.262, -.222, .059, .174, -.091, -.058, .077, .22)
RELEASE = (.211, -.144, -.244, .163, -.029, -.158, -.014, .21)
INNER = (.105, -.156, -.311, .119, -.058, -.160, -.039, .12)
LEAD = (.117, -.142, .341, .142, -.068, .146, -.055, .25)
OPEN = (.245, -.130, -.257, .182, -.021, -.145, -.091, .27)
ASCEND = (.294, -.173, .165, .177, -.078, .050, .046, .21)


def ease(t):
    t = max(0., min(1., t))
    return t*t*t*(t*(6*t-15)+10)


def pose_between(a, b, portion):
    start, end = Vector(a[:3]), Vector(b[:3])
    # Keep the wrist on an arc so the elbow does not collapse halfway into a reach.
    direction = start.normalized().slerp(end.normalized(), portion)
    distance = start.length + (end.length - start.length) * portion
    wrist = direction * distance
    elbow_and_wrist_angles = tuple(x + (y - x) * portion for x, y in zip(a[3:], b[3:]))
    return (*wrist, *elbow_and_wrist_angles)


def pose_at(keys, seconds):
    for (start,a),(end,b) in zip(keys,keys[1:]):
        if seconds<=end:
            return pose_between(a,b,ease((seconds-start)/(end-start)))
    return keys[-1][1]


def arm_pose(shot, t, seconds, side):
    if shot==0:
        if side==1:
            values=pose_at(((0.,ARRIVE),(.77,GUIDE),(1.94,RELEASE),(2.67,DRIFT)),seconds)
        else:
            values=pose_at(((0.,DRIFT),(2.43,DRIFT),(3.66,ASCEND),
                            (4.66,RELEASE),(5.47,DRIFT)),seconds)
    elif shot==1:
        if side==1:
            values=pose_at(((0.,DRIFT),(.11,DRIFT),(.38,LEAD),
                            (.57,LEAD),(.87,RELEASE),(1.,DRIFT)),t)
        else:
            values=pose_at(((0.,ARRIVE),(.30,INNER),(.62,INNER),
                            (.88,OPEN),(1.,RELEASE)),t)
    else:
        wave=TAU*(.30*seconds+(.38 if side<0 else 0.))
        values=(.157+.035*math.sin(wave),-.226+.012*math.cos(2*wave+.33),
                -.202+.015*math.sin(wave+.54),
                .116+.016*math.sin(wave+.55),-.041,-.169,
                .045*math.cos(wave+.41),.14+.155*math.cos(wave+.2))
    x,y,z,ex,ey,ez,pitch,roll=values
    return Vector((side*x,y,z)),Vector((side*ex,ey,ez)),pitch,side*roll


class GlideSwimmer(Swimmer):
    def __init__(self):
        self.rig=bpy.data.objects["Mermaid Anime"]
        self.bones=self.rig.pose.bones
        self.rest={bone.name:bone.bone.matrix_local.to_quaternion() for bone in self.bones}
        self.previous={}

    def relax_fingers(self, frame):
        fingers = (("f_index", .10), ("f_middle", .14), ("f_ring", .18), ("f_pinky", .22))
        for side in "LR":
            for finger, curl in fingers:
                for joint, weight in (("01", 1.), ("02", .66)):
                    name = f"{finger}.{joint}.{side}"
                    forward = self.rest[name] @ BACK
                    curl_axis = self.rest[name].inverted() @ forward.cross(-UP).normalized()
                    self.bone_key(name, Quaternion(curl_axis, curl * weight), frame)

    def upper_body(self, shot, local, count, frame):
        seconds=local/FPS
        t=local/(count-1)
        if shot==0:
            dive=ease(seconds/.80)*(1-ease((seconds-1.1)/1.43))
            rise=ease((seconds-2.65)/1.07)*(1-ease((seconds-3.97)/1.38))
            tilt=.068*dive-.061*rise
            self.bend("chest",frame,.015*math.sin(TAU*t-.37),.019*(dive+rise),tilt)
            self.bend("head",frame,-.190-.035*dive+.035*rise,-.026*dive+.021*rise,-.53*tilt)
        elif shot==1:
            bank=.045*math.sin(TAU*t)
            self.bend("chest",frame,.014*math.sin(TAU*t+.5),.017,bank)
            self.bend("head",frame,-.183+.023*math.cos(TAU*t),-.015*math.sin(TAU*t),-.46*bank)
        else:
            quiet=TAU*.28*seconds
            sway=.022*math.sin(quiet)
            self.bend("chest",frame,.009*math.cos(quiet),.011*math.sin(quiet+.3),.011*math.cos(quiet+.6))
            self.bend("head",frame,-.010+.021*math.sin(quiet+.38),-.42*sway,.72*sway)
        bpy.context.view_layer.update()
        forearms=[]
        for sign,side in ((1,"L"),(-1,"R")):
            wrist,elbow,pitch,roll=arm_pose(shot,t,seconds,sign)
            upper="upper_arm_fk."+side
            lower="forearm_fk."+side
            u,v=solve_arm(wrist,elbow,self.bones[upper].length,self.bones[lower].length)
            self.aim(upper,u,frame)
            forearms.append((side,lower,v,pitch,roll))
        bpy.context.view_layer.update()
        for side,lower,vector,pitch,roll in forearms:
            self.aim(lower,vector,frame)
            self.bone_key("hand_fk."+side,Quaternion(BACK,roll) @ Quaternion(RIGHT,pitch),frame)
        bpy.context.view_layer.update()

    def wrists(self):
        return [(self.bones[f"DEF-hand.{side}"].head-self.bones[f"DEF-upper_arm.{side}"].head)[:]
                for side in "LR"]

    def tail_points(self):
        names=("DEF-tail","DEF-tail.001","DEF-tail.002","DEF-tail.003","DEF-tail.004")
        return np.array([(self.bones[name].head[:],self.bones[name].tail[:]) for name in names])


def speeds(points):
    values=np.linalg.norm(np.diff(np.array(points),axis=0),axis=-1)*FPS
    return round(float(np.mean(values)),3),round(float(np.percentile(values,95)),3)


def main():
    out=Path(sys.argv[sys.argv.index("--")+1]).resolve()
    out.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    swimmer=GlideSwimmer()
    frame=1
    worst_tail=0.
    for shot,(label,count) in enumerate(SECTIONS):
        before=[]
        after=[]
        for local in range(count):
            scene.frame_set(frame)
            before.append(swimmer.wrists())
            tail=swimmer.tail_points()
            swimmer.upper_body(shot,local,count,frame)
            after.append(swimmer.wrists())
            worst_tail=max(worst_tail,float(np.max(np.abs(swimmer.tail_points()-tail))))
            frame+=1
        print("WRIST_SPEED_MEAN_P95",label,"before",speeds(before),"after",speeds(after),flush=True)
    print("TAIL_COORDINATE_CHANGE",worst_tail,flush=True)
    swimmer.relax_fingers(1)
    swimmer.relax_fingers(scene.frame_end)
    scene["Upper-body reference"]="Mermaid performance: slow guiding arms, long glides, quiet sculling"
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"Mermaid_GracefulSwim.blend"))


if __name__=="__main__":
    main()
