"""Hand-built 3D models of the weapons, rendered straight ahead like classic Doom's first-person guns.

Each model is a handful of rounded boxes and tubes (stock, receiver, barrel, magazine, sights, grip) sized after the
TGMC side-view icons. Axes: X forward (rear of the stock at 0), Y up, Z right. One unit is one voxel.
Rendering ray-marches the signed distance field from a pinhole camera behind and above the gun, centred.
"""
import math

import numpy as np
from PIL import Image

STEEL = (96, 102, 110)
DARK_STEEL = (52, 56, 62)
GUNMETAL = (70, 75, 82)
POLYMER = (44, 46, 52)
POLYMER_HI = (66, 69, 76)
WOOD = (122, 84, 52)
WOOD_DARK = (92, 62, 38)
BRASS = (200, 160, 70)
ORANGE = (220, 120, 30)
OLIVE = (88, 92, 62)
RED = (190, 40, 36)
WHITE = (214, 210, 196)
CYAN = (90, 220, 230)
GLOVE = (54, 54, 60)
SLEEVE = (52, 58, 46)
SLEEVE_HI = (64, 68, 56)


class Model:
    """A gun as a union of smooth primitives, rendered by ray-marching signed distance fields.

    Units are modelling units (about one voxel of the old voxel models). X forward, Y up, Z right.
    """

    def __init__(self):
        self.prims = []      # (kind, params, color, is_gun)
        self.arm_mode = False
        self.texture = None  # (rgb array, alpha array): the TGMC side-view icon, projected onto the gun

    def box(self, x0, x1, y0, y1, z0, z1, color, round_=0.55):
        """Rounded box covering [x0, x1+1] x [y0, y1+1] x [z0, z1+1]."""
        c = ((x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2, (z0 + z1 + 1) / 2)
        h = ((x1 - x0 + 1) / 2, (y1 - y0 + 1) / 2, (z1 - z0 + 1) / 2)
        r = min(round_, min(h) * 0.9)
        self.prims.append(("box", (c, h, r), color, not self.arm_mode))

    def tube(self, x0, x1, cy, cz, r, color):
        """Cylinder along X with radius r around (cy, cz), slightly rounded at the ends."""
        self.prims.append(("cyl", (x0, x1 + 1, cy + 0.5, cz + 0.5, r), color, not self.arm_mode))

    def capsule(self, a, b, r, color):
        self.prims.append(("cap", (a, b, r), color, not self.arm_mode))

    def arms(self, grip_x, grip_y, fore_x, fore_y, fore_z=0):
        """Gloved hands on the grip and fore-end with sleeved forearms coming in from the lower corners."""
        gun = True  # (kept for the old call signature)
        self.arm_mode = True
        # right hand and forearm (to the lower right, toward the camera)
        self.box(grip_x - 2, grip_x + 2, grip_y - 3, grip_y + 1, 1, 5, GLOVE, round_=1.0)
        self.capsule((grip_x - 3, grip_y - 3.5, 5.0), (grip_x - 17, grip_y - 11, 18), 2.5, SLEEVE)
        self.capsule((grip_x - 1, grip_y - 2, 3.5), (grip_x - 5, grip_y - 4, 6.5), 2.8, GLOVE)
        # left hand and forearm (to the lower left)
        self.box(fore_x - 2, fore_x + 2, fore_y - 3, fore_y + 1, fore_z - 6, fore_z - 2, GLOVE, round_=1.0)
        self.capsule((fore_x - 3, fore_y - 3.5, fore_z - 5.0), (fore_x - 17, fore_y - 11, fore_z - 18), 2.5, SLEEVE)
        self.capsule((fore_x - 1, fore_y - 2, fore_z - 3.5), (fore_x - 5, fore_y - 4, fore_z - 6.5), 2.8, GLOVE)
        self.arm_mode = False
        return gun

    def render(self, gun_keys=None, size=(150, 100), length=60.0, back=0, up=0, fit=None, ss=2):
        return sdf_render(self, size, length, back, up, fit, ss)


# --------------------------------------------------------------------------- ray-marching renderer

def _sd_box(P, c, h, r):
    q = np.abs(P - np.array(c)) - np.array(h) + r
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(np.max(q, axis=1), 0.0) - r


def _sd_cyl_x(P, x0, x1, cy, cz, R):
    xc, hl = (x0 + x1) / 2.0, (x1 - x0) / 2.0
    dx = np.abs(P[:, 0] - xc) - hl
    dr = np.hypot(P[:, 1] - cy, P[:, 2] - cz) - R
    return np.minimum(np.maximum(dx, dr), 0.0) + np.hypot(np.maximum(dx, 0.0), np.maximum(dr, 0.0))


def _sd_capsule(P, a, b, r):
    a, b = np.array(a, float), np.array(b, float)
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1) - r


def _prim_dist(prim, P):
    kind, params = prim[0], prim[1]
    if kind == "box":
        return _sd_box(P, *params)
    if kind == "cyl":
        return _sd_cyl_x(P, *params)
    return _sd_capsule(P, *params)


def _scene(prims, P, offset):
    """Distance to the nearest primitive and the index of that primitive. `offset` moves the whole model."""
    Q = P - offset
    best = np.full(len(P), 1e9)
    idx = np.zeros(len(P), dtype=int)
    for i, prim in enumerate(prims):
        d = _prim_dist(prim, Q)
        closer = d < best
        best = np.where(closer, d, best)
        idx = np.where(closer, i, idx)
    return best, idx


def _bbox_corners(prim):
    kind, p = prim[0], prim[1]
    if kind == "box":
        (cx, cy, cz), (hx, hy, hz), _ = p
        lo, hi = (cx - hx, cy - hy, cz - hz), (cx + hx, cy + hy, cz + hz)
    elif kind == "cyl":
        x0, x1, cy, cz, r = p
        lo, hi = (x0, cy - r, cz - r), (x1, cy + r, cz + r)
    else:
        a, b, r = p
        lo = tuple(min(a[i], b[i]) - r for i in range(3))
        hi = tuple(max(a[i], b[i]) + r for i in range(3))
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


SHININESS = {STEEL: 40.0, DARK_STEEL: 24.0, GUNMETAL: 28.0}


def sdf_render(model, size, length, back, up, fit, ss):
    """Ray-march the model from behind and above. Returns (RGBA image, fit) like the voxel renderer did."""
    sw, sh = size
    cam = np.array((-length * 0.95, length * 0.62, 0.0))
    target = np.array((length * 0.55, 0.0, 0.0))
    fwd = target - cam
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, (0.0, 1.0, 0.0))
    right /= np.linalg.norm(right)
    upv = np.cross(right, fwd)
    prims = model.prims
    offset = np.array((-float(back), float(up), 0.0))

    if fit is None:
        xs, ys = [], []
        for prim in prims:
            if not prim[3]:
                continue
            for corner in _bbox_corners(prim):
                rel = np.array(corner) - cam
                dc = rel @ fwd
                xs.append((rel @ right) / dc)
                ys.append((rel @ upv) / dc)
        scale = min(sw * 0.9 / (max(xs) - min(xs)), sh * 0.78 / (max(ys) - min(ys)))
        fit = (scale, (max(xs) + min(xs)) / 2, min(ys))
    scale, cx_mid, y_min = fit
    gun_pts = np.array([c for prim in prims if prim[3] for c in _bbox_corners(prim)])
    gx0, gx1 = gun_pts[:, 0].min(), gun_pts[:, 0].max()
    gy0, gy1 = gun_pts[:, 1].min(), gun_pts[:, 1].max()

    W, H = sw * ss, sh * ss
    gx, gy = np.meshgrid((np.arange(W) + 0.5) / ss, (np.arange(H) + 0.5) / ss)
    px_ = (gx - sw / 2) / scale + cx_mid
    py_ = (sh * 0.76 - gy) / scale + y_min
    dirs = fwd + px_[..., None] * right + py_[..., None] * upv
    dirs = dirs.reshape(-1, 3)
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)

    n = len(dirs)
    t = np.full(n, length * 0.45)           # start close to the model
    alive = np.ones(n, dtype=bool)
    hit = np.zeros(n, dtype=bool)
    tmax = length * 2.2
    for _ in range(90):
        idx = np.nonzero(alive)[0]
        if idx.size == 0:
            break
        P = cam + dirs[idx] * t[idx, None]
        d, _m = _scene(prims, P, offset)
        got = d < 0.02
        hit[idx[got]] = True
        alive[idx[got]] = False
        t[idx] += np.where(got, 0.0, d)
        alive[idx[t[idx] > tmax]] = False

    rgb = np.zeros((n, 3))
    hi = np.nonzero(hit)[0]
    if hi.size:
        P = cam + dirs[hi] * t[hi, None]
        d0, mat = _scene(prims, P, offset)
        eps = 0.05
        grad = np.zeros((hi.size, 3))
        for k in range(3):
            e = np.zeros(3)
            e[k] = eps
            dp, _a = _scene(prims, P + e, offset)
            dm, _b = _scene(prims, P - e, offset)
            grad[:, k] = dp - dm
        normal = grad / np.maximum(np.linalg.norm(grad, axis=1, keepdims=True), 1e-9)
        light = np.array((-0.35, 0.85, -0.40)); light /= np.linalg.norm(light)
        view = -dirs[hi]
        half = light + view; half /= np.linalg.norm(half, axis=1, keepdims=True)
        diffuse = np.clip(normal @ light, 0.0, 1.0)
        # ambient occlusion: how much free space there is just above the surface
        ao_d, _c = _scene(prims, P + normal * 0.9, offset)
        ao = np.clip(ao_d / 0.9, 0.35, 1.0)
        rim = np.clip(1.0 - np.sum(normal * view, axis=1), 0.0, 1.0) ** 3 * 0.18
        base = np.array([prims[i][2] for i in mat], float)
        if model.texture is not None:
            # Project the TGMC icon along Z onto the gun (arms keep their own colours).
            trgb, ta = model.texture
            Q = P - offset
            u = np.clip((Q[:, 0] - gx0) / (gx1 - gx0), 0.0, 1.0)
            v = np.clip((gy1 - Q[:, 1]) / (gy1 - gy0), 0.0, 1.0)
            ix = (u * (trgb.shape[1] - 1)).astype(int)
            iy = (v * (trgb.shape[0] - 1)).astype(int)
            tex = trgb[iy, ix].astype(float)
            use = np.array([prims[i][3] for i in mat]) & (ta[iy, ix] >= 128)
            base = np.where(use[:, None], 0.30 * base + 0.70 * tex, base)
        shin = np.array([SHININESS.get(prims[i][2], 10.0) for i in mat])
        spec = np.clip(np.sum(normal * half, axis=1), 0.0, 1.0) ** shin
        spec_amt = np.where(shin > 20, 0.55, 0.12)
        lit = (0.42 + 0.78 * diffuse) * ao + rim
        rgb[hi] = np.clip(base * lit[:, None] + 255 * (spec * spec_amt * ao)[:, None], 0, 255)
    # gamma lift (TGMC-style guns are dark; Doom's floors are dark too)
    rgb = 255.0 * (rgb / 255.0) ** 0.82

    cov = hit.reshape(H, W).astype(float)
    img = rgb.reshape(H, W, 3)
    cov_s = cov.reshape(sh, ss, sw, ss).sum(axis=(1, 3))
    col_s = (img * cov[..., None]).reshape(sh, ss, sw, ss, 3).sum(axis=(1, 3))
    out = np.zeros((sh, sw, 4), dtype=np.uint8)
    opaque = cov_s >= (ss * ss) / 2.0
    avg = col_s / np.maximum(cov_s[..., None], 1.0)
    out[..., :3] = np.clip(avg, 0, 255).astype(np.uint8)
    out[..., 3] = np.where(opaque, 255, 0)
    return Image.fromarray(out, "RGBA"), fit


# --------------------------------------------------------------------------- models

def sh35():
    """T-35 semi-auto shotgun: polymer stock, boxy receiver, barrel over a magazine tube, pump fore-end."""
    m = Model()
    m.box(0, 15, 0, 7, -3, 3, POLYMER)                      # stock
    m.box(1, 3, 1, 6, -4, 4, DARK_STEEL)                    # butt plate
    m.box(15, 31, 0, 8, -3.5, 3.5, GUNMETAL)                # receiver
    m.box(17, 28, 8, 8, -2, 2, DARK_STEEL)                  # ejection port cover
    m.box(18, 22, -9, -1, -2, 2, POLYMER_HI)                # pistol grip
    m.box(16, 24, -2, -1, -2.5, 2.5, POLYMER)               # trigger guard base
    m.tube(31, 62, 6, 0, 2.2, STEEL)                        # barrel
    m.tube(31, 54, 1.5, 0, 2.0, DARK_STEEL)                 # magazine tube
    m.box(36, 48, -1, 4, -3.5, 3.5, POLYMER_HI)             # pump fore-end
    m.box(16, 18, 9, 10, -1.5, 1.5, DARK_STEEL)             # rear sight
    m.box(60, 61, 8, 10, -0.7, 0.7, ORANGE)                 # front sight
    m.box(19, 30, 9, 9, -0.8, 0.8, STEEL)                   # top rail
    m.tube(52, 54, 6, 0, 2.9, DARK_STEEL)                   # muzzle ring
    m.box(50, 52, 1, 3, -3.4, -3.0, STEEL)                  # fore-end bolt heads
    m.box(50, 52, 1, 3, 3.0, 3.4, STEEL)
    gun = m.arms(grip_x=20, grip_y=-8, fore_x=42, fore_y=-2)
    return m, gun, 62.0


def mg60():
    """T-60 belt-fed machine gun: stock, big receiver with feed cover, ammo box and belt, shrouded barrel."""
    m = Model()
    m.box(0, 13, 1, 8, -3, 3, POLYMER)                      # stock
    m.box(13, 38, 0, 10, -4.5, 4.5, GUNMETAL)               # receiver
    m.box(14, 37, 10, 12, -3.6, 3.6, DARK_STEEL)            # feed cover
    m.box(22, 30, 12, 13, -2.5, 2.5, STEEL)                 # carry handle bar
    m.box(20, 24, -9, -1, -2, 2, POLYMER_HI)                # pistol grip
    m.box(24, 33, -10, -1, -6.5, -4, OLIVE)                 # ammo box (left side)
    m.box(30, 36, -2, 5, -7, -4, BRASS)                     # belt
    m.tube(38, 64, 7, 0, 2.3, STEEL)                        # barrel
    m.tube(38, 54, 7, 0, 3.4, DARK_STEEL)                   # barrel shroud
    m.box(55, 61, 1, 3, -4, -3, STEEL)                      # folded bipod legs
    m.box(55, 61, 1, 3, 3, 4, STEEL)
    m.box(14, 16, 13, 14, -1.5, 1.5, DARK_STEEL)            # rear sight
    m.box(62, 63, 9, 12, -0.7, 0.7, ORANGE)                 # front sight post
    m.tube(62, 65, 7, 0, 3.0, DARK_STEEL)                   # flash hider
    m.box(20, 32, 13, 13, -1, 1, STEEL)                     # top rail
    m.box(36, 38, 11, 12, -4.7, 4.7, ORANGE)                # feed tray accent
    gun = m.arms(grip_x=22, grip_y=-8, fore_x=46, fore_y=3)
    return m, gun, 64.0


def pistol():
    """M1911-style pistol."""
    m = Model()
    m.box(0, 22, 3, 8, -2.2, 2.2, GUNMETAL)                 # slide
    m.box(22, 28, 4, 6, -1.5, 1.5, STEEL)                   # barrel tip
    m.box(2, 20, 0, 3, -2, 2, DARK_STEEL)                   # frame
    m.box(2, 9, -11, 0, -2.4, 2.4, POLYMER_HI)              # grip
    m.box(8, 9, -12, -10, -2.4, 2.4, DARK_STEEL)            # magazine base
    m.box(1, 3, 9, 10, -1.2, 1.2, DARK_STEEL)               # rear sight
    m.box(26, 27, 9, 10, -0.6, 0.6, WHITE)                  # front sight
    gun = m.arms(grip_x=5, grip_y=-8, fore_x=14, fore_y=-1)
    return m, gun, 30.0


def double_shotgun():
    """Double-barrelled shotgun: wood stock and fore-end, two barrels."""
    m = Model()
    m.box(0, 18, 0, 7, -3, 3, WOOD)                         # stock
    m.box(0, 2, 1, 6, -3.5, 3.5, DARK_STEEL)                # butt plate
    m.box(18, 26, 0, 8, -4.5, 4.5, GUNMETAL)                # receiver
    m.tube(26, 62, 5.5, -2.3, 2.1, STEEL)                   # left barrel
    m.tube(26, 62, 5.5, 2.3, 2.1, STEEL)                    # right barrel
    m.box(26, 44, 0, 3, -4.6, 4.6, WOOD_DARK)               # fore-end
    m.box(60, 61, 8, 9, -0.7, 0.7, WHITE)                   # bead sight
    m.box(22, 25, -7, -1, -1.5, 1.5, WOOD)                  # grip
    gun = m.arms(grip_x=23, grip_y=-6, fore_x=38, fore_y=-1)
    return m, gun, 62.0


def rocket_launcher():
    """RPG: olive launch tube with a red and white warhead."""
    m = Model()
    m.tube(0, 44, 6, 0, 5.0, OLIVE)                         # tube
    m.tube(0, 4, 6, 0, 5.6, DARK_STEEL)                     # rear flare
    m.tube(44, 52, 6, 0, 3.8, WHITE)                        # warhead body
    m.tube(52, 58, 6, 0, 3.0, RED)
    m.tube(58, 62, 6, 0, 1.6, RED)                          # nose
    m.box(18, 22, -6, 0, -2, 2, POLYMER_HI)                 # grip
    m.box(30, 40, 11, 13, -1, 1, DARK_STEEL)                # sight
    gun = m.arms(grip_x=20, grip_y=-5, fore_x=36, fore_y=1)
    return m, gun, 62.0


def plasma_rifle():
    """Plasma rifle: pale body, cyan glow strips, fat barrel."""
    m = Model()
    m.box(0, 12, 1, 9, -3, 3, GUNMETAL)                     # stock
    m.box(12, 40, 0, 12, -5, 5, (150, 158, 166))            # body
    m.box(14, 38, 12, 13, -3, 3, DARK_STEEL)                # top rail
    m.box(14, 38, 5, 6, -5.4, -4.8, CYAN)                   # glow strips
    m.box(14, 38, 5, 6, 4.8, 5.4, CYAN)
    m.tube(40, 62, 6, 0, 3.6, STEEL)                        # barrel
    m.tube(58, 62, 6, 0, 2.0, CYAN)                         # emitter
    m.box(18, 22, -9, 0, -2, 2, POLYMER_HI)                 # grip
    gun = m.arms(grip_x=21, grip_y=-8, fore_x=36, fore_y=-1)
    return m, gun, 62.0


def bfg():
    """Plasma cannon: heavy body with a large glowing muzzle."""
    m = Model()
    m.box(0, 14, 0, 10, -4, 4, GUNMETAL)                    # stock
    m.box(14, 44, -1, 16, -8, 8, (118, 126, 134))           # body
    m.box(16, 42, 16, 17, -5, 5, DARK_STEEL)
    m.tube(44, 60, 8, 0, 6.5, STEEL)                        # muzzle housing
    m.tube(56, 62, 8, 0, 5.0, (60, 230, 120))               # glowing emitter
    m.box(16, 42, 7, 8, -8.4, -7.8, (60, 230, 120))         # side glow
    m.box(16, 42, 7, 8, 7.8, 8.4, (60, 230, 120))
    m.box(20, 25, -10, -1, -2.5, 2.5, POLYMER_HI)           # grip
    gun = m.arms(grip_x=23, grip_y=-9, fore_x=40, fore_y=-3)
    return m, gun, 62.0


def power_axe():
    """TGMC powered axe in place of the chainsaw: long shaft and a big head, held upright."""
    m = Model()
    m.tube(0, 50, 5, 0, 1.8, GUNMETAL)                      # shaft
    m.box(46, 58, -1, 14, -1, 1, STEEL)                     # head / blade
    m.box(46, 52, 8, 11, -1.4, 1.4, ORANGE)                 # power indicator
    m.box(8, 14, 3, 7, -2.5, 2.5, POLYMER_HI)               # hand guard
    gun = m.arms(grip_x=10, grip_y=3, fore_x=26, fore_y=3)
    return m, gun, 58.0


MODELS = {
    "PISG": pistol, "SHTG": sh35, "SHT2": double_shotgun, "CHGG": mg60,
    "MISG": rocket_launcher, "PLSG": plasma_rifle, "BFGG": bfg, "SAWG": power_axe,
}


TEXTURE_ROOT = None   # directory of extracted TGMC sheets (tgmc_sprites); set by build_weapon_view.py
TEXTURE_ICONS = {
    "PISG": ("pistols", "m1911"), "SHTG": ("shotguns64", "t35"), "SHT2": ("shotguns", "dshotgun"),
    "CHGG": ("machineguns64", "t60"), "MISG": ("special64", "rpg"), "PLSG": ("plasma64", "plasma_rifle"),
    "BFGG": ("plasma64", "plasma_cannon"), "SAWG": ("twohanded", "auto_axe_on"),
}


def load_texture(prefix):
    """The TGMC side-view icon for this weapon, cropped, as (rgb array, alpha array); None if unavailable."""
    if not TEXTURE_ROOT:
        return None
    import json
    import os
    sheet, state = TEXTURE_ICONS[prefix]
    try:
        m = json.load(open(os.path.join(TEXTURE_ROOT, sheet, "manifest.json")))
        hit = [x for x in m["states"] if x["name"] == state][0]
        img = Image.open(os.path.join(TEXTURE_ROOT, sheet, hit["files"][0])).convert("RGBA")
    except (OSError, IndexError, KeyError):
        return None
    img = img.crop(img.getchannel("A").getbbox())
    arr = np.array(img)
    return arr[..., :3], arr[..., 3]


def render_weapon(prefix, size=(150, 100), back=0, up=0, fit=None):
    model, gun_keys, length = MODELS[prefix]()
    model.texture = load_texture(prefix)
    return model.render(gun_keys, size=size, length=length, back=back, up=up, fit=fit)


if __name__ == "__main__":
    import sys
    out = sys.argv[1]
    names = list(MODELS)
    cols = 4
    sheet = Image.new("RGBA", (cols * 470, 2 * 330), (48, 48, 48, 255))
    for i, n in enumerate(names):
        r, _fit = render_weapon(n)
        r = r.resize((r.width * 3, r.height * 3), Image.NEAREST)
        sheet.paste(r, ((i % cols) * 470 + 6, (i // cols) * 330 + 6), r)
    sheet.save(out)
    print("saved", out)
