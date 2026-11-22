"""Rectify public-domain feather photographs and derive study-only texture maps."""

from pathlib import Path

import bpy
import numpy as np


SOURCES = Path(__file__).resolve().parent / 'sources'
WIDTH, HEIGHT = 352, 624
COLS, ROWS = 4, 2
PADDING = 3
SIZE = (WIDTH * COLS, HEIGHT * ROWS)


def smooth(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def photograph(name):
    image = bpy.data.images.load(str(SOURCES / name), check_existing=False)
    w, h = image.size
    pixels = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    rgb = pixels.reshape(h, w, 4)[::-1, :, :3].copy()
    bpy.data.images.remove(image)
    return rgb


def sample(image, x, y):
    x = np.clip(x, 0, image.shape[1] - 1.001)
    y = np.clip(y, 0, image.shape[0] - 1.001)
    x0, y0 = x.astype(np.int32), y.astype(np.int32)
    u, v = (x - x0)[..., None], (y - y0)[..., None]
    lower = image[y0, x0] * (1 - u) + image[y0, x0 + 1] * u
    upper = image[y0 + 1, x0] * (1 - u) + image[y0 + 1, x0 + 1] * u
    return (lower * (1 - v) + upper * v).astype(np.float32)


def blurred(data, radius):
    """Separable running mean used to suppress photographed macro lighting."""
    result = data
    for axis in (0, 1):
        pads = [(0, 0), (0, 0)]
        pads[axis] = (radius, radius)
        padded = np.pad(result, pads, mode='edge')
        start = np.zeros_like(np.take(padded, [0], axis=axis))
        summed = np.concatenate((start, np.cumsum(padded, axis=axis, dtype=np.float32)), axis=axis)
        n = 2 * radius + 1
        if axis == 0:
            result = (summed[n:] - summed[:-n]) / n
        else:
            result = (summed[:, n:] - summed[:, :-n]) / n
    return result


def luminance(rgb):
    return rgb[..., 0] * .2126 + rgb[..., 1] * .7152 + rgb[..., 2] * .0722


def atlas_coordinate(u, v, tile):
    x = tile % COLS * WIDTH + PADDING + .5 + u * (WIDTH - 2 * PADDING - 1)
    y = tile // COLS * HEIGHT + PADDING + .5 + v * (HEIGHT - 2 * PADDING - 1)
    return x / SIZE[0], y / SIZE[1]


def rectify_contour(rgb, t, across):
    # Rachis landmarks in Greyling's 1920x1280 photograph, from base to tip.
    controls = np.array([(1370, 1142), (1212, 1047), (1093, 978), (980, 897),
                         (869, 807), (741, 702), (617, 591), (490, 461),
                         (377, 350), (292, 252), (242, 172), (260, 134)], dtype=np.float32)
    along = np.r_[0., np.cumsum(np.linalg.norm(np.diff(controls, axis=0), axis=1))]
    along /= along[-1]
    x = np.interp(t, along, controls[:, 0])
    y = np.interp(t, along, controls[:, 1])
    dx, dy = np.gradient(x), np.gradient(y)
    extension = np.hypot(dx, dy)
    nx, ny = -dy / extension, dx / extension

    def samples(offset):
        return sample(rgb, x[:, None] + nx[:, None] * offset,
                      y[:, None] + ny[:, None] * offset)

    def foreground(img):
        blue = img[..., 2] - img[..., 0]
        return 1 - smooth(.042, .086, blue)

    offsets = np.linspace(-221., 254., 320)
    probe = foreground(samples(offsets[None, :]))
    inside = probe > .75
    # The neutral feather is on blue-grey cloth. Ignore isolated cloth flecks.
    stable = inside & np.roll(inside, 1, axis=1) & np.roll(inside, -1, axis=1)
    negative = np.maximum(16, np.max(np.where(stable & (offsets < 0), -offsets, 0), axis=1))
    positive = np.maximum(16, np.max(np.where(stable & (offsets > 0), offsets, 0), axis=1))
    blur = lambda seq: blurred(seq[:, None], 5)[:, 0]
    spread = np.where(across < 0, blur(negative)[:, None], blur(positive)[:, None])
    resampled = samples(across * spread * 1.08)
    mask = foreground(resampled)
    return resampled, mask


def crow_detail(rgb, u, v, variant):
    # A lens macro across the two vanes supplies actual barb / barbule contrast.
    # Keep the sample centres off the large overexposed shaft in this picture.
    shifted = v * .91 + .035 * (variant % 3)
    offset = .14 * ((variant % 4) - 1.5)
    top_x = 296 + shifted * 1115 + abs(u) * 174
    top_y = 916 - shifted * 746 - abs(u) * (92 + 52 * offset)
    bot_x = 545 + shifted * 1110 + abs(u) * (162 + 38 * offset)
    bot_y = 1054 - shifted * 746 + abs(u) * 174
    x, y = np.where(u < 0, top_x, bot_x), np.where(u < 0, top_y, bot_y)
    value = luminance(sample(rgb, x, y))
    fine = np.clip((value - blurred(value, 4)) / .13, -.70, .70)
    middle = np.clip((blurred(value, 3) - blurred(value, 22)) / .13, -.7, .7)
    return fine.astype(np.float32), middle.astype(np.float32)


def tile(contour, macro, fine_plume, tile_number):
    rng = np.random.default_rng(9122 + tile_number * 13)
    u = np.linspace(-1, 1, WIDTH - 2 * PADDING, dtype=np.float32)[None, :]
    v = np.linspace(0, 1, HEIGHT - 2 * PADDING, dtype=np.float32)[:, None]
    feather_type = 'flight' if tile_number < 2 else ('bar' if tile_number < 6 else 'small')
    flip = -1 if tile_number % 2 else 1
    photo_u = u * flip
    if feather_type == 'flight':
        donor = .168 + v.ravel() * (.54 + .02 * tile_number)
    elif feather_type == 'bar':
        donor = np.interp(v.ravel(), (0, .34, .70, .82, .94, 1),
                          (.16, .34, .54, .68 + rng.uniform(-.025, .016), .84, .968))
    else:
        donor = .11 + v.ravel() * (.65 + .047 * (tile_number - 6))
    rgb, photo_mask = rectify_contour(contour, donor, photo_u)
    source_value = luminance(rgb)
    detail, mottles = crow_detail(macro, photo_u, v, tile_number)
    source_blur = blurred(source_value, 8)
    source_detail = np.clip((source_value - source_blur) / .17, -.5, .5)
    dark = (.021 + .028 * smooth(.075, .32, source_blur)) * (.90 + .36 * v)
    dark *= 1 + .22 * mottles + .105 * detail + .095 * source_detail
    dark *= 1 + .11 * rng.normal(0, .13, dark.shape)
    dark = np.clip(dark, .012, .101)
    # The photograph supplies real irregularities at the transition; reposition them
    # for the much smaller white tips on these coverts.
    if feather_type == 'bar':
        limit = .818 + .030 * (tile_number - 3) + .045 * photo_u
        growth = smooth(limit - .041, limit + .058, v)
        pale = smooth(.46, .80, source_blur) * growth
        pale = np.maximum(pale, .92 * smooth(limit + .054, .995, v) * growth)
    elif feather_type == 'small' and tile_number == 7:
        pale = smooth(.42, .87, source_blur) * smooth(.62, .99, v) * .72
    else:
        pale = np.zeros_like(dark)
    warm = .86 + .15 * smooth(-.72, .79, photo_u) + .09 * mottles
    grey = np.stack((dark * 1.06, dark * .99, dark * warm), axis=-1)
    whites = np.stack((.47 + .035 * detail, .445 + .032 * detail, .403 + .030 * detail), axis=-1)
    rgb = grey * (1 - pale[..., None]) + whites * pale[..., None]

    # Fine plumulaceous material from Ballantyne contributes only to the lower vane.
    if feather_type == 'small':
        x = 224 + (v * 260 - 26) + photo_u * (123 - 34 * v)
        y = 1120 - v * 661 + photo_u * 57
        fuzz = luminance(sample(fine_plume, x, y))
        photo_mask *= 1 - (1 - smooth(.02, .23, fuzz)) * (1 - smooth(.08, .46, v)) * .64
    edge = smooth(.55, 1., abs(u))
    # Preserve solid interior vanes and pick up only actual notches and fraying near the rim.
    photo_emphasis = .085 + .64 * edge if feather_type == 'flight' else .12 + .73 * edge
    alpha = np.clip(1 - (1 - photo_mask) * photo_emphasis, 0, 1)
    alpha *= 1 - smooth(.945, 1.015, abs(u)) * (1 - .35 * photo_mask)
    alpha *= smooth(.023, .17 if feather_type == 'small' else .085, v)
    # Only a small part of the photographed texture becomes bump, with no claim of measured normals.
    height = np.clip(.5 + .58 * detail + .22 * source_detail, .04, .96)
    gaps = np.clip(.044 + .38 * (1 - photo_mask) * edge + .085 * (1 - smooth(.03, .52, v)), 0, 1)
    polish = np.clip(.51 + .37 * detail + .25 * mottles, .08, .90)
    pad = ((PADDING, PADDING), (PADDING, PADDING), (0, 0))
    color = np.pad(np.dstack((rgb, alpha)), pad, mode='edge')
    structure = np.pad(np.dstack((height, gaps, polish, np.ones_like(height))), pad, mode='edge')
    return color, structure


def packed_image(name, array):
    image = bpy.data.images.new(name, width=SIZE[0], height=SIZE[1], alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    image.alpha_mode = 'CHANNEL_PACKED'
    image.pixels.foreach_set(array.ravel())
    image.update()
    image.pack()
    return image


def build_photographic_atlases():
    contour = photograph('grey-feather.jpg')
    macro = photograph('black-feather.jpg')
    fine_plume = photograph('light-feather.jpg')
    color = np.empty((SIZE[1], SIZE[0], 4), dtype=np.float32)
    structure = np.empty_like(color)
    for index in range(COLS * ROWS):
        x, y = index % COLS * WIDTH, index // COLS * HEIGHT
        c, s = tile(contour, macro, fine_plume, index)
        color[y:y + HEIGHT, x:x + WIDTH] = c
        structure[y:y + HEIGHT, x:x + WIDTH] = s
    return (packed_image('Photographic feather colors and edges', color),
            packed_image('Feather relief and thin areas', structure))
