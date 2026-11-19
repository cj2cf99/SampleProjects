"""Register a two-step, left-facing walk to 64 source pixels of floor travel.

The shoe and the skirt are independent opaque pieces. The CSS route plays this
atlas once per leg and derives its distance from the rendered figure height.
"""
from pathlib import Path
from math import cos, pi, sin
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

salon = Path(__file__).resolve().parents[1] / "assets" / "salon"
original = Image.open(salon / "stride.webp").convert("RGBA").resize((762, 840))
arms = Image.open(salon / "stroll.webp")
shoe_mask = Image.new("L", original.size)
outline = [(65,406),(73,401),(84,398),(91,392),(99,380),(102,379),
           (110,383),(119,386),(115,393),(114,400),(111,408),
           (108,414),(105,414),(106,405),(97,407),(90,412),(77,411),(64,409)]
ImageDraw.Draw(shoe_mask).polygon([(x*2,y*2) for x,y in outline], fill=255)
shoe = original.copy()
alpha = original.getchannel("A")
shoe.putalpha(ImageChops.darker(alpha, shoe_mask))
skirt = original.copy()
skirt.putalpha(ImageChops.subtract(alpha,shoe_mask.filter(ImageFilter.MaxFilter(5))))
far_shoe = ImageEnhance.Brightness(shoe).enhance(.73)
stride = 64
stance = .56

def foot(phase):
    """A planted foot exactly cancels root travel; swing has matched endpoint velocities."""
    if phase < stance:
        return stride * (phase - stance/2), 0, 0
    u = (phase-stance)/(1-stance)
    advance = u*u*(3-2*u)
    x = stride * (phase - stance/2 - advance)
    return x, -8*sin(pi*u)**2, 8*sin(2*pi*u)*sin(pi*u)

cell = (290,320)
sheet = Image.new("RGBA", (8*cell[0],6*cell[1]))
for i in range(48):
    phase = i/48
    frame = Image.new("RGBA",original.size)
    for source, offset in ((far_shoe,.5),(shoe,0)):
        x,y,angle = foot((phase+offset)%1)
        leg = source.rotate(angle,Image.Resampling.BICUBIC,center=(206,792))
        frame.alpha_composite(leg,(round((x+12)*2),round((y+2-offset*4)*2)))
    # Preserve the painted skirt edge. Most of the far leg passes behind it.
    body = skirt.copy()
    arms.seek(round(phase*arms.n_frames)%arms.n_frames)
    upper = arms.convert("RGBA").resize(original.size,Image.Resampling.LANCZOS)
    body.paste(upper.crop((0,0,762,524)),(0,0))
    frame.alpha_composite(body,(0,-round(3*(1-cos(4*pi*phase)))))
    sheet.paste(frame.resize(cell,Image.Resampling.LANCZOS),((i%8)*cell[0],(i//8)*cell[1]))
sheet.save(salon / "footsteps.webp",quality=86,method=5)
