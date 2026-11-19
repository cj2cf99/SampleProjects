"""Separate the painted acting arm, original cards and overlapping fingers."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

salon = Path(__file__).resolve().parents[1] / "assets" / "salon"
arms = {
    "welcome": [(67,518),(86,518),(110,520),(144,523),(164,535),(184,560),(188,585),(201,594),(220,584),(230,586),(224,598),(203,624),(181,636),(150,638),(128,640),(108,628),(99,610),(94,575),(85,553),(67,540),(61,529)],
    "deal": [(84,505),(104,472),(117,445),(148,421),(178,402),(212,394),(248,379),(255,378),(255,385),(241,401),(223,411),(253,427),(274,442),(308,441),(317,445),(313,452),(299,455),(320,462),(333,473),(331,480),(309,480),(281,472),(254,467),(229,477),(160,478),(140,497),(117,557),(90,612),(83,601)],
    "think": [(133,714),(139,657),(150,631),(176,602),(189,563),(199,539),(213,526),(247,511),(278,516),(285,522),(282,531),(273,534),(279,542),(281,552),(276,560),(281,570),(276,577),(269,578),(270,587),(264,594),(255,600),(251,594),(249,582),(236,593),(220,608),(208,632),(185,651),(159,686)],
    "answer": [(198,708),(220,704),(231,692),(236,665),(246,639),(259,621),(280,614),(302,614),(326,623),(352,646),(369,678),(373,687),(365,690),(345,682),(328,671),(319,670),(318,690),(306,721),(294,748),(283,756),(277,750),(279,728),(263,741),(243,747),(237,742),(240,730),(222,734),(213,727),(199,724),(195,717)]
}
cards = {
    "deal": [(164,598),(187,563),(226,519),(264,498),(310,487),(359,488),(410,504),(411,589),(368,656),(282,685)],
    "think": [(202,541),(228,421),(307,432),(282,563),(262,577)]
}
fingers = {
    "deal": [(280,622),(286,619),(304,625),(301,617),(306,610),(330,617),(362,629),(378,643),(380,669),(366,691),(354,710),(332,708),(314,695),(306,682),(282,661),(279,651),(283,647),(279,639),(284,634)],
    "think": arms["think"]
}

def mask_for(shape, outline):
    mask = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.asarray(outline, np.int32)], 255)
    return mask

def cut(portrait, mask):
    layer = portrait.copy()
    matte = cv2.GaussianBlur(mask, (3,3), .6)
    layer[:,:,3] = np.minimum(layer[:,:,3], matte)
    return Image.fromarray(layer)

for pose, points in arms.items():
    portrait = np.array(Image.open(salon / (pose+".webp")).convert("RGBA"))
    arm = mask_for(portrait.shape, points)
    cut(portrait, arm).save(salon / (pose+"arm.webp"), quality=92)
    if pose in cards:
        arm = cv2.bitwise_or(arm, mask_for(portrait.shape, cards[pose]))
    if pose == "deal":
        cut(portrait, mask_for(portrait.shape, fingers[pose])).save(salon/"dealgrip.webp", quality=92)
    # Inpaint only beneath the moving surfaces; preserve the outer silhouette.
    portrait[:,:,:3] = cv2.inpaint(portrait[:,:,:3].copy(), cv2.dilate(arm,np.ones((3,3),np.uint8)), 5, cv2.INPAINT_TELEA)
    Image.fromarray(portrait).save(salon / (pose+"base.webp"), quality=91)
