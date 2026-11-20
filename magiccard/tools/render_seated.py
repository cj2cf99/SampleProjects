"""Cut acting hands and gripped cards from the four seated paintings.

Outlines are traced in the 288 x 384 storyboard coordinate system.
"""
from pathlib import Path
import argparse
import cv2
import numpy as np
from PIL import Image

salon = Path(__file__).resolve().parents[1] / "assets" / "salon"
arms = {
    "welcome": [(204,139),(217,129),(231,118),(242,115),(263,113),(265,117),(251,122),(259,125),(276,126),(279,130),(274,134),(253,140),(240,139),(230,135),(219,145),(207,157)],
    "deal": [(111,142),(122,132),(131,122),(145,104),(156,99),(176,95),(199,95),(201,99),(180,104),(196,110),(195,114),(187,115),(193,119),(188,121),(170,114),(160,115),(146,126),(136,140),(117,161)],
    "think": [(174,195),(173,176),(170,161),(165,153),(164,145),(167,137),(168,133),(178,134),(189,138),(193,143),(194,154),(190,161),(192,180),(193,194)],
    "answer": [(197,158),(210,152),(219,144),(232,140),(251,137),(254,141),(243,146),(256,147),(265,146),(267,151),(256,157),(240,162),(229,161),(216,157),(198,173)]
}
props = {
    "think": [(164,143),(168,104),(192,103),(194,108),(186,147)]
}
grip = [(176,159),(178,155),(186,157),(188,154),(202,160),(205,165),(202,173),(197,177),(193,178),(182,169)]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--pose", choices=arms)
pose = parser.parse_args().pose
for name, outline in arms.items():
    if pose and pose != name:
        continue
    if name == "deal":
        # The empty hands and complete bodice are painted on the source plate.
        # Cards are supplied at runtime, behind the fingers.
        source = Path(__file__).parent / "artwork" / "seatdeal-empty.png"
        with Image.open(source) as painting:
            painting.convert("RGBA").resize((543, 724), Image.Resampling.LANCZOS).save(salon/"seatdeal.webp", quality=95)
    src = np.array(Image.open(salon/f"seat{name}.webp").convert("RGBA"))
    def mask(points):
        a = np.zeros(src.shape[:2],np.uint8)
        cv2.fillPoly(a,[np.rint(np.asarray(points)*[src.shape[1]/288,src.shape[0]/384]).astype(np.int32)],255)
        return a
    def layer(points,suffix):
        img = src.copy()
        img[:,:,3] = np.minimum(img[:,:,3],cv2.GaussianBlur(mask(points),(3,3),.5))
        Image.fromarray(img).save(salon/f"seat{name}{suffix}.webp",quality=93)
    layer(outline,"arm")
    lifted = mask(outline)
    # Keep the rigid head turn very small at the collar; the chair and knees stay fixed.
    head = [(62,91),(72,71),(79,48),(85,24),(96,9),(110,2),(130,1),(146,7),(154,20),
            (160,39),(163,57),(161,76),(170,96),(151,101),(141,94),(133,102),(117,100),
            (107,91),(93,91),(80,100),(63,105)]
    offset = {"welcome":0,"deal":3,"think":10,"answer":-2}[name]
    head = [(x+offset,y) for x,y in head]
    layer(head,"head")
    lifted |= mask(head)
    if name in props:
        lifted |= mask(props[name])
    if name == "deal":
        layer(grip,"grip")
    # Remove the original silhouette where the raised palm was surrounded by air.
    outer = cv2.dilate((src[:,:,3]<50).astype(np.uint8),np.ones((7,7),np.uint8))
    cut = cv2.dilate(lifted,np.ones((3,3),np.uint8))
    src[:,:,3] = cv2.inpaint(src[:,:,3].copy(),cut,5,cv2.INPAINT_TELEA)
    src[:,:,3][(outer>0)&(lifted>0)] = 0
    src[:,:,:3] = cv2.inpaint(src[:,:,:3].copy(),cut,5,cv2.INPAINT_TELEA)
    Image.fromarray(src).save(salon/f"seat{name}base.webp",quality=91)
