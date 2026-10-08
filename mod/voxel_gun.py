"""Turn a flat side-view gun icon into a first-person view by extruding it into a voxel model.

Each opaque pixel of the side view becomes a column of voxels across the gun's width (a thin slab,
thicker in the middle). The model is rendered with a pinhole camera behind and above the gun,
looking forward along the barrel, with simple shading (tops bright, sides dark). Two blocky
forearms and hands hold the gun.

Axes: X = along the barrel (stock to muzzle), Y = up, Z = to the right.
The icon is assumed to face right (muzzle on the right), like the TGMC gun art.
"""
import math

from PIL import Image

SLEEVE = (58, 52, 48)
GLOVE = (36, 36, 40)


def build_voxels(icon, depth=7):
    """icon: RGBA side view, cropped. Returns {(x, y, z): (r, g, b)} with y pointing up."""
    w, h = icon.size
    px = icon.load()
    half = depth // 2
    vox = {}
    for ix in range(w):
        for iy in range(h):
            r, g, b, a = px[ix, iy]
            if a < 128:
                continue
            # Slimmer toward the top and bottom edges of the silhouette: rounder look.
            col_top = next(yy for yy in range(h) if px[ix, yy][3] >= 128)
            col_bot = max(yy for yy in range(h) if px[ix, yy][3] >= 128)
            span = max(1, col_bot - col_top)
            rel = abs((iy - col_top) / span - 0.5) * 2  # 0 centre .. 1 edge
            t = max(1, round(half * (1.0 - 0.45 * rel)))
            for z in range(-t, t + 1):
                shade = 1.0 - 0.28 * (abs(z) / max(1, t))
                vox[(ix, h - 1 - iy, z)] = (r * shade, g * shade, b * shade)
    return vox, w, h


def add_box(vox, x0, x1, y0, y1, z0, z1, color):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                vox[(x, y, z)] = color


def add_arms(vox, w, h):
    """Right hand on the grip, left hand under the fore-end, forearms running back toward the camera."""
    grip_x = int(w * 0.30)
    fore_x = int(w * 0.62)
    # right hand + forearm (slightly right of the gun, below the stock line)
    add_box(vox, grip_x - 1, grip_x + 3, -4, 1, 1, 4, GLOVE)
    for i in range(1, 10):
        x = grip_x - 2 - i
        y = -4 - i // 2
        add_box(vox, x, x, y - 1, y + 1, 1 + i // 6, 5 + i // 6, SLEEVE if i > 3 else GLOVE)
    # left hand under the fore-end, forearm angled in from the left
    add_box(vox, fore_x - 1, fore_x + 3, -3, 1, -4, -1, GLOVE)
    for i in range(1, 12):
        x = fore_x - 2 - i
        y = -3 - i // 2
        add_box(vox, x, x, y - 1, y + 1, -5 - i // 5, -1 - i // 5, SLEEVE if i > 3 else GLOVE)


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def render(icon, size=(96, 80), depth=7, cam_back=0.4, cam_up=1.6, cam_right=2.4, arms=True, margin=0.92, gamma=0.72):
    """Render the voxel gun to an RGBA image of `size`, gun pointing away from the viewer.

    The camera sits behind, above and to the right of the stock and looks at the middle of the gun;
    the image is scaled to fill the frame and its bottom edge sits on the bottom of the sprite.
    """
    icon = icon.convert("RGBA")
    icon = icon.crop(icon.getchannel("A").getbbox())
    vox, w, h = build_voxels(icon, depth)
    gun_keys = set(vox)
    if arms:
        add_arms(vox, w, h)

    cam = (-w * cam_back, h * cam_up, h * cam_right)
    target = (w * 0.50, h * 0.35, 0.0)
    fwd = _norm(tuple(t - c for t, c in zip(target, cam)))
    right = _norm(_cross(fwd, (0.0, 1.0, 0.0)))
    up = _cross(right, fwd)

    pts = []
    for (x, y, z), col in vox.items():
        rel = (x - cam[0], y - cam[1], z - cam[2])
        dc = _dot(rel, fwd)
        if dc <= 1:
            continue
        pts.append((x, y, z, _dot(rel, right) / dc, _dot(rel, up) / dc, dc, col, (x, y, z) in gun_keys))

    # Auto-fit: scale so the projected model fills the sprite.
    xs = [p[3] for p in pts if p[7]]
    ys = [p[4] for p in pts if p[7]]
    scale = min(size[0] * margin / (max(xs) - min(xs)), size[1] * 0.72 / (max(ys) - min(ys)))
    cx_mid = (max(xs) + min(xs)) / 2
    y_min = min(ys)  # bottom of the gun itself; the forearms run below it, off the sprite edge

    sw, sh = size
    SS = 3
    W2, H2 = sw * SS, sh * SS
    color = [[None] * W2 for _ in range(H2)]
    zbuf = [[1e9] * W2 for _ in range(H2)]
    for x, y, z, px_, py_, dc, (r, g, b), _is_gun in pts:
        lit = 1.0
        if (x, y + 1, z) not in vox:
            lit = 1.28
        elif (x - 1, y, z) not in vox:
            lit = 1.08
        elif (x, y, z + 1) not in vox or (x, y, z - 1) not in vox:
            lit = 0.82
        sx = sw / 2 + (px_ - cx_mid) * scale
        sy = sh * 0.74 - (py_ - y_min) * scale
        size_px = max(1.2, scale / dc)
        x0, x1 = int((sx - size_px / 2) * SS), int(math.ceil((sx + size_px / 2) * SS))
        y0, y1 = int((sy - size_px / 2) * SS), int(math.ceil((sy + size_px / 2) * SS))
        # Gamma lift: TGMC guns are near-black, which vanishes against Doom's dark floors.
        col = tuple(min(255, int(255 * (min(255, c * lit) / 255) ** gamma)) for c in (r, g, b))
        for yy in range(max(0, y0), min(H2, y1)):
            zrow, crow = zbuf[yy], color[yy]
            for xx in range(max(0, x0), min(W2, x1)):
                if dc < zrow[xx]:
                    zrow[xx] = dc
                    crow[xx] = col

    out = Image.new("RGBA", size, (0, 0, 0, 0))
    po = out.load()
    for yy in range(sh):
        for xx in range(sw):
            c = color[yy * SS + SS // 2][xx * SS + SS // 2]
            if c is not None:
                po[xx, yy] = (*c, 255)
    return out


def pose_bottom_right(img, tilt_deg=30):
    """Pose a side-view render like a first-person weapon at the bottom right.

    The render is mirrored (muzzle to the left, forearms running to the lower right) and then tipped
    clockwise about its bottom centre so the muzzle points up toward the middle of the screen.
    """
    img = img.transpose(Image.FLIP_LEFT_RIGHT)
    w, h = img.size
    pad = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    pad.paste(img, (w // 2, h))
    rot = pad.rotate(-tilt_deg, resample=Image.NEAREST, center=(w // 2 + w // 2 + w // 2 - w // 2, h * 2 - 1))
    return rot.crop(rot.getchannel("A").getbbox())


if __name__ == "__main__":
    import json
    import os
    import sys

    root = sys.argv[1]  # tgmc_sprites dir
    out_path = sys.argv[2]
    picks = [("shotguns64", "trenchgun"), ("machineguns64", "t60"), ("special64", "rpg"),
             ("plasma64", "plasma_rifle"), ("pistols", "m1911")]
    tiles = []
    for sheet, state in picks:
        m = json.load(open(os.path.join(root, sheet, "manifest.json")))
        hit = [s for s in m["states"] if s["name"] == state][0]
        icon = Image.open(os.path.join(root, sheet, hit["files"][0]))
        tiles.append(render(icon))
    sheet_img = Image.new("RGBA", (len(tiles) * 100 * 3 + 10, 90 * 3), (40, 40, 40, 255))
    for i, t in enumerate(tiles):
        big = t.resize((t.width * 3, t.height * 3), Image.NEAREST)
        sheet_img.paste(big, (6 + i * 300, 6), big)
    sheet_img.save(out_path)
    print("saved", out_path)
