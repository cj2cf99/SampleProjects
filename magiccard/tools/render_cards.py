"""Bake articulated paper cutouts and pip arrangements to the game's local films.

Requires Python, OpenCV, Pillow, NumPy and ffmpeg (FFMPEG environment variable).
Run in magiccard: python tools/render_cards.py [card numbers ...]
"""
import math
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cutouts import RIGS, head, arm, cloth

SIZE = 320
FPS = 24
ASSETS = Path("assets")
cv2.setNumThreads(1)
cv2.setRNGSeed(73)


def outline_mask(image, points):
    poly = np.rint(np.asarray(points) * (SIZE - 1) / 100).astype(np.int32)
    mask = np.zeros((SIZE, SIZE), np.uint8)
    cv2.fillPoly(mask, [poly], 255)
    # Refine only the narrow band around the hand-traced silhouette.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    core = cv2.erode(mask, kernel)
    if cv2.countNonZero(core) > 12:
        labels = np.zeros_like(mask)
        labels[cv2.dilate(mask, kernel) > 0] = cv2.GC_PR_BGD
        labels[mask > 0] = cv2.GC_PR_FGD
        labels[core > 0] = cv2.GC_FGD
        cv2.grabCut(image, labels, None, np.zeros((1,65)), np.zeros((1,65)), 2, cv2.GC_INIT_WITH_MASK)
        mask = ((labels & 1) * 255).astype(np.uint8)
    return mask


def layer_pixels(base, alpha, spec):
    x, y, w, h = cv2.boundingRect(alpha)
    a = alpha[y:y+h,x:x+w].astype(np.float32) / 255
    rgba = np.dstack((base[y:y+h,x:x+w] * a[:,:,None], a * 255)).astype(np.uint8)
    return (spec, (x,y), rgba)


def cut_painting(image, specs):
    plate = image.copy()
    layers = []
    for spec in reversed(specs):
        mask = outline_mask(image, spec["points"])
        alpha = cv2.GaussianBlur(mask, (3,3), .48)
        layers.append(layer_pixels(plate, alpha, spec))
        plate = cv2.inpaint(plate, cv2.dilate(mask, np.ones((3,3),np.uint8)), 4, cv2.INPAINT_TELEA)
    return plate, list(reversed(layers))


def court_specs(card):
    # Head center, hair/helmet bounds, neckline. Painted to each court portrait.
    heads = {
      32:(48,20,17,18),33:(47,25,19,20),34:(50,22,16,21),35:(50,22,16,21),
      46:(49,26,16,20),47:(47,28,20,20),48:(54,26,16,20),49:(51,24,16,21),
      60:(49,24,14,19),61:(51,29,17,19),62:(50,24,15,21),63:(51,23,17,20),
      74:(49,26,16,19),75:(49,25,18,19),76:(50,22,16,20),77:(49,24,16,21),
    }
    x,y,w,h = heads[card]
    contour = [(-.65,.67),(-1,.17),(-.91,-.49),(-.53,-.84),(0,-1),(.72,-.76),(1,-.2),(.88,.38),(.51,.67),(.43,.95),(-.36,1)]
    hair = " ".join(f"{x+a*w},{y+b*h}" for a,b in contour)
    hands = {
      32:((83,66),"71,50 73,45 71,42 72,34 74,22 79,7 78,1 80,2 84,14 79,24 77,42 80,45 79,50 83,60 87,66 84,71 80,70",3),
      33:((66,76),"62,77 68,68 74,61 79,56 79,50 79,40 80,32 81,20 84,8 87,4 91,1 89,13 85,25 83,43 82,54 85,57 84,63 79,67 72,77 68,83",4),
      34:((80,66),"74,65 74,43 74,41 74,38 76,36 77,29 79,17 82,8 86,1 88,2 85,17 82,23 80,36 83,39 82,44 84,64 83,69",3),
      35:((86,65),"77,48 77,43 80,42 82,31 82,21 85,16 86,5 89,1 91,3 88,18 85,30 83,43 86,46 88,61 91,66 87,70 82,60",3),
      46:((48,80),"46,77 53,71 59,66 62,63 59,60 58,51 61,49 75,49 78,52 75,59 71,63 69,65 72,67 71,74 68,77 73,79 76,82 60,82 64,78 63,75 56,77 50,83",5),
      47:((69,70),"65,68 72,58 78,51 78,47 82,44 80,40 75,34 74,26 92,25 93,29 91,35 86,40 85,44 88,47 86,54 90,56 91,58 80,59 75,64 70,74",5),
      48:((12,65),"9,61 14,46 17,33 19,31 18,27 15,25 13,16 29,14 31,17 28,24 23,27 23,30 26,31 26,35 24,38 23,41 27,43 27,45 16,45 15,61 13,68",7),
      49:((24,70),"22,66 27,55 30,48 32,46 29,43 26,38 26,31 42,31 45,34 41,41 37,44 37,47 40,48 39,52 36,56 36,61 41,63 41,66 27,65 30,61 29,58 26,68",5),
      60:((17,79),"14,78 17,71 17,65 15,63 15,60 8,60 8,58 18,58 18,4 20,0 21,4 21,58 28,57 28,59 23,61 24,66 22,70 21,80",3),
      61:((66,86),"64,83 75,75 85,69 87,65 84,64 78,63 79,61 86,61 86,9 88,2 90,6 91,61 96,60 97,63 92,65 94,68 91,73 90,78 86,77 84,75 75,82 68,89",3),
      62:((17,55),"12,54 15,45 19,39 19,37 15,36 14,34 21,34 21,3 23,0 24,3 24,34 31,34 32,36 26,37 26,41 23,45 23,65 21,66 20,44 15,56",3),
      63:((18,71),"14,68 16,57 15,54 19,51 12,50 12,48 19,48 19,4 21,0 23,5 23,48 29,47 30,50 25,52 25,56 23,62 24,70 20,72 17,69",3),
      74:((72,69),"68,68 73,49 74,43 73,39 69,36 68,30 69,25 74,21 80,21 85,24 88,29 86,35 81,39 84,40 83,44 79,48 78,62 76,72",6),
      75:((74,65),"73,62 80,52 83,46 86,43 80,40 76,35 75,29 79,24 85,22 90,23 95,27 96,34 92,39 88,42 93,43 91,49 87,51 80,65 76,69",5),
      76:((80,67),"77,65 78,47 79,37 78,34 72,30 71,25 72,20 77,16 84,16 90,20 92,26 89,31 84,35 88,36 89,39 85,44 85,61 83,68",6),
      77:((86,59),"80,57 82,42 82,38 81,34 77,32 74,27 74,21 78,16 84,14 90,16 94,21 94,27 90,31 86,33 90,35 90,42 88,47 91,57 89,60",5),
    }
    return [cloth((50,78),"27,45 36,42 46,45 53,47 64,44 69,47 65,58 59,63 47,69 36,61"),
            head((x,y+h*.85),hair,3.5),arm(*hands[card])]


def compose(frame, layer, transform):
    spec, (x,y), rgba = layer
    h,w = rgba.shape[:2]
    affine = transform.copy()
    affine[:2,2] += affine[:2,:2] @ np.array([x,y])
    corners = (affine[:2,:2] @ np.array([[0,w,0,w],[0,0,h,h]])).T + affine[:2,2]
    left,top = np.maximum(0,np.floor(corners.min(axis=0)-1)).astype(int)
    right,bottom = np.minimum(SIZE,np.ceil(corners.max(axis=0)+1)).astype(int)
    if right<=left or bottom<=top: return
    affine[:2,2] -= [left,top]
    ink = cv2.warpAffine(rgba,affine[:2],(right-left,bottom-top),flags=cv2.INTER_LINEAR)
    dest = frame[top:bottom,left:right]
    dest[:] = cv2.add(ink[:,:,:3], np.rint(dest*(1-ink[:,:,3,None].astype(np.float32)/255)).astype(np.uint8))


def smooth(u):
    u = min(1,max(0,u))
    return u*u*(3-2*u)


def gesture(u):
    keys = [(0,0),(.15,-.15),(.44,1),(.59,1),(.85,-.08),(1,0)]
    for (a,v),(b,w) in zip(keys,keys[1:]):
        if a <= u < b: return v+(w-v)*smooth((u-a)/(b-a))
    return 0


def frame_at(plate,layers,t,card,period):
    result = plate.copy()
    parents = {}
    phase = (t-1.5)*math.tau/period
    for i, layer in enumerate(layers):
        spec = layer[0]
        name = spec["name"]
        lag = {"breath":0,"head":.07,"hand":.13,"prop":.24}.get(name,i*.04)
        breath = math.sin(phase*3+card*.41-lag)
        idle = math.sin(phase*2+card*.52-i*.47)
        special = gesture((t-1.5-period*.43)/(2.2+card%4*.14)-lag)
        entry = (1-smooth((t-lag)/1.5))
        angle = spec["degrees"]*(.24*idle+special-.85*entry)
        pivot = tuple(v*SIZE/100 for v in spec["pivot"])
        matrix = np.eye(3)
        matrix[:2] = cv2.getRotationMatrix2D(pivot,angle,1.0)
        if name in ("head","breath"):
            matrix[1,2] += (.40 if name=="head" else .65)*breath+entry*.65
        if spec.get("parent") in parents: matrix = parents[spec["parent"]] @ matrix
        parents[name] = matrix
        compose(result,layer,matrix)
    return result


def pip_scene(card):
    suit,rank = divmod(card-22,14)
    rank += 1
    cols = [[1],[1,1],[1,1,1],[2,2],[2,1,2],[2,2,2],[2,3,2],[3,2,3],[3,3,3],[3,2,2,3]][rank-1]
    yy,xx = np.mgrid[0:SIZE,0:SIZE]
    rng = np.random.default_rng(100+suit)
    glow = np.exp(-((xx-155)**2+(yy-120)**2)/16000)
    tint = [(23,29,41),(39,36,21),(39,29,28),(22,37,26)][suit]
    plate = np.clip(np.array(tint)+glow[:,:,None]*21+rng.normal(0,1.7,(SIZE,SIZE,1)),0,255).astype(np.uint8)
    for r in (117,121,145,147): cv2.circle(plate,(160,160),r,(66,77,89),1,cv2.LINE_AA)
    for k in range(100):
        a=k*math.tau/100
        for r in (143,):
            l=7 if k%5==0 else 3
            cv2.line(plate,(int(160+r*math.cos(a)),int(160+r*math.sin(a))),(int(160+(r-l)*math.cos(a)),int(160+(r-l)*math.sin(a))),(73,88,109),1,cv2.LINE_AA)
    for _ in range(100):
        x,y=rng.integers(8,SIZE-8,2)
        cv2.circle(plate,(int(x),int(y)),1,(103,133,155),-1)
    icon = cv2.imread(str(ASSETS/"suits"/f"{suit}.png"),cv2.IMREAD_UNCHANGED)
    max_size = min(216,int(240/max(len(cols),max(cols))))
    h,w=icon.shape[:2]
    icon=cv2.resize(icon,(max(1,round(w*max_size/max(w,h))),max(1,round(h*max_size/max(w,h)))),interpolation=cv2.INTER_AREA)
    rgba=icon.copy()
    rgba[:,:,:3]=np.rint(rgba[:,:,:3]* (rgba[:,:,3,None].astype(float)/255)).astype(np.uint8)
    layers=[]
    for row,count in enumerate(cols):
        for col in range(count):
            x=(SIZE/2)+(col-(count-1)/2)*min(92,245/max(cols))
            y=(SIZE/2)+(row-(len(cols)-1)/2)*min(96,245/len(cols))
            spec=dict(name=f"pip{len(layers)}",degrees=(-1)**(row+col)*(6 if suit==3 else 4.5),pivot=(x*100/SIZE,y*100/SIZE))
            layers.append((spec,(round(x-rgba.shape[1]/2),round(y-rgba.shape[0]/2)),rgba))
    still=plate.copy()
    for layer in layers: compose(still,layer,np.eye(3))
    cv2.imwrite(str(ASSETS/"cards"/f"{card:02}.jpg"),still,[cv2.IMWRITE_JPEG_QUALITY,93])
    return plate,layers


def encode(card):
    if card>=22 and (card-22)%14<10:
        plate,layers=pip_scene(card)
    else:
        source=cv2.resize(cv2.imread(str(ASSETS/"cards"/f"{card:02}.jpg")),(SIZE,SIZE),interpolation=cv2.INTER_AREA)
        plate,layers=cut_painting(source,RIGS[card] if card<22 else court_specs(card))
    output=ASSETS/"performances"/f"{card:02}.mp4"
    temp=output.with_suffix(".part.mp4")
    cmd=[os.environ.get("FFMPEG","ffmpeg"),"-y","-v","error","-f","rawvideo","-pix_fmt","bgr24","-s",f"{SIZE}x{SIZE}","-r",str(FPS),"-i","-","-an","-c:v","libx264","-threads","2","-preset","veryfast","-crf","19","-pix_fmt","yuv420p","-force_key_frames","1.5","-movflags","+faststart",str(temp)]
    period=9+card%5
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as process:
        for n in range(int((1.5+period)*FPS)):
            process.stdin.write(frame_at(plate,layers,n/FPS,card,period).tobytes())
        process.stdin.close()
        if process.wait(): raise RuntimeError(f"ffmpeg failed on card {card}")
    temp.replace(output)
    print(f"{card:02} {len(layers)} rigid layers",flush=True)


if __name__=="__main__":
    for card in map(int,sys.argv[1:]) if sys.argv[1:] else range(78): encode(card)
