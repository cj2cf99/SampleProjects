"""Bake the hostess's polishing gesture on the transparent window portrait."""
from pathlib import Path
import math

import cv2
import numpy as np
from PIL import Image

salon = Path(__file__).resolve().parents[1] / "assets" / "salon"
portrait = np.array(Image.open(salon / "lamp.webp").convert("RGBA"))
height, width = portrait.shape[:2]
# Forearm, fingers and the linen cloth. Keep the brass and the supporting hand fixed.
outline = [(170,270),(188,258),(215,247),(237,229),(252,211),(257,197),
           (266,191),(283,187),(294,188),(300,189),(305,193),(305,198),
           (299,202),(292,207),(290,219),(288,236),(287,251),(289,263),
           (281,269),(274,272),(262,282),(258,278),(259,261),(263,242),
           (264,228),(252,239),(241,250),(229,263),(213,279),(193,292),
           (182,295),(174,286)]
mask = np.zeros((height, width), np.uint8)
cv2.fillPoly(mask, [np.array(outline,np.int32)], 255)
ink = cv2.inpaint(portrait[:,:,:3].copy(), cv2.dilate(mask,np.ones((3,3),np.uint8)), 3, cv2.INPAINT_TELEA)
alpha = cv2.GaussianBlur(mask,(3,3),.55).astype(np.float32)/255
layer = np.dstack((portrait[:,:,:3]*alpha[:,:,None],alpha*255)).astype(np.uint8)
frames = []
for i in range(90):
    phase = 2 * math.pi * i / 90
    angle = 2.8 * math.sin(phase)
    shift = cv2.getRotationMatrix2D((178,280),angle,1)
    shift[0,2] += 1.6 * math.sin(phase*2)
    moved = cv2.warpAffine(layer,shift,(width,height))
    composite = moved[:,:,:3] + ink * (1-moved[:,:,3:4].astype(np.float32)/255)
    frames.append(Image.fromarray(np.dstack((composite.clip(0,255).astype(np.uint8),portrait[:,:,3]))))
frames[0].save(salon/"polish.webp", save_all=True, append_images=frames[1:], loop=0,
               duration=40, quality=85, method=4)
