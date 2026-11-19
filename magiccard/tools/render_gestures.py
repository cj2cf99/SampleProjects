"""Bake hand-inbetweened, rigid layer motions at 30 fps, with fixed face proportions."""
from pathlib import Path
import math
import cv2
import numpy as np
from PIL import Image

salon = Path(__file__).resolve().parents[1] / "assets" / "salon"

def render(source, target, guide_size, parts, count, bob=0):
    art = Image.open(salon/source).convert("RGBA")
    art.thumbnail((590,720),Image.Resampling.LANCZOS)
    original = np.asarray(art)
    h,w = original.shape[:2]
    scale = np.array((w,h))/guide_size
    plate = original.copy()
    layers = []
    for outline,pivot,angle,dx,lift,phase in parts:
        mask = np.zeros((h,w),np.uint8)
        cv2.fillPoly(mask,[np.rint(np.asarray(outline)*scale).astype(np.int32)],255)
        alpha = np.minimum(cv2.GaussianBlur(mask,(3,3),.58),original[:,:,3]).astype(np.float32)/255
        pixels = np.dstack((original[:,:,:3]*alpha[:,:,None],alpha*255)).astype(np.uint8)
        layers.append((pixels,tuple(np.asarray(pivot)*scale),angle,dx,lift,phase))
        cleared = cv2.dilate(mask,np.ones((3,3),np.uint8))
        plate[:,:,:3] = cv2.inpaint(plate[:,:,:3].copy(),cleared,4,cv2.INPAINT_TELEA)
        plate[:,:,3] = cv2.inpaint(plate[:,:,3].copy(),cleared,4,cv2.INPAINT_TELEA)
    frames=[]
    base = plate.astype(np.float32)
    base[:,:,:3] *= base[:,:,3:4]/255
    for i in range(count):
        t = i*2*math.pi/count
        frame=base.copy()
        for pixels,pivot,angle,dx,lift,phase in layers:
            u=t+phase
            matrix=cv2.getRotationMatrix2D(pivot,angle*math.sin(u),1)
            matrix[:,2] += [dx*math.sin(u)*scale[0],-lift*max(0,math.cos(u))*scale[1]]
            ink=cv2.warpAffine(pixels,matrix,(w,h))
            frame=ink+frame*(1-ink[:,:,3:4].astype(np.float32)/255)
        frame[:,:,:3] *= 255/np.maximum(1,frame[:,:,3:4])
        img=Image.fromarray(frame.clip(0,255).astype(np.uint8))
        if bob:
            sheet=Image.new("RGBA",(w,h));sheet.alpha_composite(img,(0,-round(bob*(1-math.cos(2*t)))));img=sheet
        frames.append(img)
    frames[0].save(salon/target,save_all=True,append_images=frames[1:],loop=0,
                   duration=[round((i+1)*1000/30)-round(i*1000/30) for i in range(count)],quality=83,method=4)

# Front hem and shoe, far hand, near sleeve and forearm carry different phases.
render("stride.webp","stroll.webp",(381,420),[
    ([(63,407),(79,399),(81,377),(101,360),(116,330),(129,311),(142,335),(133,371),(127,393),(118,404),(96,411),(66,411)],(142,267),4.5,5,3,0),
    ([(95,193),(108,184),(129,172),(142,155),(151,152),(153,169),(140,182),(121,191),(115,201),(107,205),(95,206)],(150,151),7,2,1,0),
    ([(170,115),(181,109),(197,114),(205,138),(211,165),(229,177),(223,196),(214,196),(211,211),(223,231),(222,246),(212,240),(202,229),(198,206),(194,188),(181,178),(174,157)],(181,119),7.8,1.5,1,math.pi)
],36,1.25)

# The central celestial disc turns inside a stationary outer frame.
ring=[(204+18*math.cos(t),73+17*math.sin(t)) for t in np.linspace(0,2*math.pi,48)]
render("globe.webp","starglobe.webp",(270,540),[(ring,(204,73),17,0,0,0)],72)
