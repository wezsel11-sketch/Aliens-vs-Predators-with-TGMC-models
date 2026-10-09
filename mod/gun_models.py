"""Hand-built voxel models of the weapons, rendered straight ahead like classic Doom's first-person guns.

Each model is a handful of boxes and tubes (stock, receiver, barrel, magazine, sights, grip) sized after the
TGMC side-view icons. Axes: X forward (rear of the stock at 0), Y up, Z right. One unit is one voxel.
Rendering reuses voxel_gun.draw_voxels (pinhole camera behind and above the gun, centred).
"""
import math

from PIL import Image

import voxel_gun as vg

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
GLOVE = (30, 30, 34)
SLEEVE = (40, 44, 38)
SLEEVE_HI = (64, 68, 56)


K = 2  # model resolution: voxels per modelling unit (finer voxels = smoother curves)


class Model:
    def __init__(self):
        self.vox = {}

    def box(self, x0, x1, y0, y1, z0, z1, color):
        for x in range(int(round(x0 * K)), int(round((x1 + 1) * K))):
            for y in range(int(round(y0 * K)), int(round((y1 + 1) * K))):
                for z in range(int(round(z0 * K)), int(round((z1 + 1) * K))):
                    self.vox[(x, y, z)] = color

    def tube(self, x0, x1, cy, cz, r, color):
        """Cylinder along X with radius r (in voxels) around (cy, cz)."""
        cy, cz, r = cy * K, cz * K, r * K
        ri = int(math.ceil(r))
        for x in range(int(round(x0 * K)), int(round((x1 + 1) * K))):
            for y in range(int(math.floor(cy - ri)), int(math.ceil(cy + ri)) + 1):
                for z in range(int(math.floor(cz - ri)), int(math.ceil(cz + ri)) + 1):
                    if (y - cy) ** 2 + (z - cz) ** 2 <= r * r:
                        self.vox[(x, y, z)] = color

    def arms(self, grip_x, grip_y, fore_x, fore_y, fore_z=0):
        """Right hand on the grip and left hand on the fore-end; short, thick forearms come in from the lower corners."""
        gun = set(self.vox)
        self.box(grip_x - 2, grip_x + 3, grip_y - 3, grip_y + 2, 1, 5, GLOVE)                    # right hand
        self.box(fore_x - 2, fore_x + 3, fore_y - 3, fore_y + 1, fore_z - 5, fore_z - 1, GLOVE)  # left hand
        for i in range(1, 7):
            col = SLEEVE_HI if i == 3 else SLEEVE
            self.box(grip_x - 3 - i * 1.4, grip_x + 1 - i * 1.4, grip_y - 3 - i * 0.7, grip_y + 3 - i * 0.7,
                     2 + i * 1.3, 8 + i * 1.3, GLOVE if i < 2 else col)
            self.box(fore_x - 3 - i * 1.4, fore_x + 1 - i * 1.4, fore_y - 3 - i * 0.7, fore_y + 3 - i * 0.7,
                     fore_z - 8 - i * 1.3, fore_z - 2 - i * 1.3, GLOVE if i < 2 else col)
        return gun

    def shifted(self, back=0, up=0):
        """A copy of the voxels moved toward the camera and up (recoil)."""
        b, u = int(round(back * K)), int(round(up * K))
        return {(x - b, y + u, z): c for (x, y, z), c in self.vox.items()}

    def render(self, gun_keys, size=(150, 100), length=60.0, back=0, up=0, fit=None):
        """Render the model (optionally kicked back/up by some voxels). Returns (image, fit)."""
        length = length * K
        cam = (-length * 0.95, length * 0.62, 0.0)
        target = (length * 0.55, 0.0, 0.0)
        if back or up:
            vox = self.shifted(back, up)
            b, u = int(round(back * K)), int(round(up * K))
            keys = {(x - b, y + u, z) for (x, y, z) in gun_keys}
        else:
            vox, keys = self.vox, gun_keys
        return vg.draw_voxels_smooth(vox, keys, cam, target, size, margin=0.9, gun_height_frac=0.78, fit=fit, return_fit=True)


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


def render_weapon(prefix, size=(150, 100), back=0, up=0, fit=None):
    model, gun_keys, length = MODELS[prefix]()
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
