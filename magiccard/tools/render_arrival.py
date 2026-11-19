"""Register the five hand-drawn exposures of each beat on the same floor.

The input strips live next to this script in artwork/arrival. A cell is 480 x
720. The last seated pose also supplies the live greeting, on the identical
crop used by the browser's closing camera move.
"""
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

root = Path(__file__).resolve().parents[1]
salon = root / "assets/salon"
cell = (480, 720)
floor = 702
rig_crop = (51, 187, 441, 707)
# Corrections made with the shoe and the chair foot on a common ground plane.
# Fixed scale within each take preserves the photographed knee flexion.
groups = [
    ("turn", .866, [261,261,262,264,265]),
    ("reach", .931, [70,70,70,70,70]),
    ("lower", .977, [70,70,70,70,70]),
    ("sit", .770, [76,76,76,76,76]),
    ("offer", .761, [73,73,73,73,73]),
]

# Seeds along the visible seam between the brocade sleeve/skirt and the wood.
# GrabCut follows the local colour boundaries rather than cutting off the fingers.
levels = [300,350,395,443,473,495,525,560,600,645,675,705]
edges = {
    "side":[192,185,185,182,176,174,183,173,163,143,106,75],
    "backrail":[176,131,176,184,181,174,177,177,162,140,105,75],
    "arm":[184,170,149,124,112,163,166,172,169,148,111,77],
    "down":[175,164,147,119,111,142,155,164,160,141,99,77],
    "rest":[171,159,143,130,119,113,107,139,132,105,86,75],
    "lap":[166,154,142,137,127,125,123,124,126,111,84,73]
}
edge_sets={"reach":["side","backrail","backrail","backrail","backrail"],
           "lower":["backrail","arm","arm","arm","arm"], "sit":["down"]*5,
           "offer":["rest","lap","lap","lap","lap"]}
ankles={"reach":[339,343,341,344,344],"lower":[338,346,343,348,356],
        "sit":[318,318,312,313,311],"offer":[325,321,318,317,320]}

def remove_painted_chair(frame, edge):
    rgba = np.asarray(frame)
    y,x = np.indices(rgba.shape[:2])
    seam = x-np.interp(y,levels,edges[edge])
    labels = np.where(seam>0,cv2.GC_PR_FGD,cv2.GC_PR_BGD).astype(np.uint8)
    labels[(seam>27)|(y<302)|(y>678)] = cv2.GC_FGD
    labels[(seam< -28)&(y>310)&(y<678)] = cv2.GC_BGD
    labels[rgba[:,:,3]<16] = cv2.GC_BGD
    model=lambda:np.zeros((1,65),np.float64)
    cv2.grabCut(rgba[:,:,:3].copy(),labels,None,model(),model(),3,cv2.GC_INIT_WITH_MASK)
    mask=cv2.GaussianBlur((labels%2*255).astype(np.uint8),(3,3),.55)
    frame.putalpha(Image.fromarray(np.minimum(mask,rgba[:,:,3])))
    return frame

chair = Image.new("RGBA",cell)
wood = Image.open(root/"tools/artwork/arrival/chair.webp").convert("RGBA")
wood.thumbnail((225,335),Image.Resampling.LANCZOS)
chair.alpha_composite(wood,(65,346))
chair.save(salon/"windowchair.webp",quality=92)

def drawings(name):
    strip = Image.open(root / f"tools/artwork/arrival/{name}.webp").convert("RGBA")
    coverage = (np.asarray(strip.getchannel("A")) > 60).sum(axis=0)
    cuts = [0]
    for i in range(1,5):
        middle = round(strip.width*i/5)
        radius = round(strip.width*.066)
        interval = coverage[middle-radius:middle+radius]
        gaps = np.flatnonzero(interval==interval.min())
        cuts.append(int(middle-radius+gaps[np.abs(gaps-radius).argmin()]))
    for x,right in zip(cuts,cuts[1:]+[strip.width]):
        drawing = strip.crop((x,0,right,strip.height))
        bounds = drawing.getchannel("A").point(lambda a: 255 if a>40 else 0).getbbox()
        yield drawing.crop(bounds)

rows = {}
for name, scale, horizontal in groups:
    frames = []
    for j, drawing in enumerate(drawings(name)):
        w,h = drawing.size
        drawing = drawing.resize((round(w*scale),round(h*scale)),Image.Resampling.LANCZOS)
        x = horizontal[j] - (drawing.width//2 if name=="turn" else 0)
        frame = Image.new("RGBA", cell)
        frame.alpha_composite(drawing,(x,floor-drawing.height))
        if name!="turn":
            frame=remove_painted_chair(frame,edge_sets[name][j])
            shifted=Image.new("RGBA",cell)
            shifted.alpha_composite(frame,(342-ankles[name][j],0))
            frame=shifted
        frames.append(frame)
    rows[name] = frames

def save_rows():
    for name,frames in rows.items():
        sheet = Image.new("RGBA",(cell[0]*5,cell[1]))
        for j,frame in enumerate(frames):
            sheet.paste(frame,(j*cell[0],0))
        sheet.save(salon/f"arrival{name}.webp",quality=90,method=5)

save_rows()
settled = chair.copy()
settled.alpha_composite(rows["offer"][-1])
greeting = settled.crop(rig_crop)
greeting.save(salon/"seatinvite.webp",quality=94)

# The final exposure becomes the live rig without changing lens or costume.
base=np.array(greeting)
removed=np.zeros(base.shape[:2],np.uint8)
for part,points in {
    "arm":[(252,190),(274,180),(293,170),(309,158),(327,151),(360,150),
           (369,154),(366,160),(353,164),(374,165),(377,171),(370,179),
           (355,186),(340,192),(320,192),(304,190),(291,201),(269,216),(256,220)],
    "head":[(102,159),(108,127),(117,102),(123,82),(131,62),(146,36),
            (166,21),(190,16),(214,21),(226,34),(234,60),(239,90),(247,114),
            (251,131),(241,139),(226,135),(209,126),(199,138),(185,148),
            (172,154),(158,148),(146,145),(129,153),(116,165)]
}.items():
    mask=np.zeros_like(removed)
    cv2.fillPoly(mask,[np.asarray(points,np.int32)],255)
    pixels=np.array(greeting)
    pixels[:,:,3]=np.minimum(pixels[:,:,3],mask)
    Image.fromarray(pixels).save(salon/f"seatinvite{part}.webp",quality=93)
    removed|=mask
# Preserve interior paint immediately beneath the edges as the wrist/head turn.
edge=cv2.dilate(removed,np.ones((3,3),np.uint8))
base[:,:,:3]=cv2.inpaint(base[:,:,:3].copy(),edge,4,cv2.INPAINT_TELEA)
base[:,:,3]=cv2.inpaint(base[:,:,3].copy(),edge,4,cv2.INPAINT_TELEA)
base[:,:,3][(removed>0)&(np.asarray(greeting)[:,:,3]<16)]=0
Image.fromarray(base).save(salon/"seatinvitebase.webp",quality=93)
