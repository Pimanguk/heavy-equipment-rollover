"""CAT 320 excavator: Excavator.blend + spreadsheet tabs 01 / 02 / 03  ->  .blend, .glb (web), params.

Usage (Blender 4.x / 5.x):
  blender -b download/Excavator.blend --python build_excavator_final.py -- <out_dir> [--render]

Outputs in <out_dir>:
  Excavator_CAT320.blend   rigged + limits + sheet properties + demo animation
  web/excavator_3rd.glb    3rd-person model: exterior only (rest pose, no animation)
  web/excavator_1st.glb    1st-person model: + cab interior (seat, joysticks, levers, dash, monitor, Int_Eye), see-through glass
  web/model_data.js        both glb as base64 + params, for web/index.html (works from file://)
  report.json              measured vs. sheet dimensions
  *.png                    stills (with --render)

Sheet tabs
  01_CAT320_기준제원     -> SHEET01   (lengths of boom / stick, track length, gauge, width, mass, speeds)
  02_5부품_질량관성       -> SHEET02   (mass, size, inertia of 5 parts)
  03_가동범위_속도가속도   -> SHEET03   (angle limits, initial angle, max speed, max accel)

Angle convention (side view, +X front, +Z up, CCW positive):
  boom = boom-foot-pin -> boom/stick pin angle above horizontal
  arm  = stick angle relative to boom,   bucket = bucket angle relative to stick (0 = modelled pose)
  swing = rotation about the vertical swing axis, CCW seen from above
"""
import bpy, sys, os, math, json, base64
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]
RENDER = "--render" in argv
os.makedirs(OUT + "/web", exist_ok=True)

# =====================  SHEET VALUES  =====================
SHEET01 = dict(model="CAT 320", total_mass_kg=22600, boom_length_m=5.7, stick_length_m=2.9,
               bucket_capacity_m3=1.19, swing_max_rpm=11.25, track_length_m=4.45,
               roller_center_dist_m=3.65, track_gauge_m=2.38, transport_width_m=2.98,
               gravity=9.81, travel_max_kmh=5.9)
#            mass, length(display), width, height, inertia I kg m^2, axis,            motion
SHEET02 = {
    "bucket": dict(mass=1200,  length=1.57, width=0.95, height=0.55, I=86.5,     axis="bucket pin",       motion="pitch"),
    "stick":  dict(mass=1800,  length=2.90, width=0.45, height=0.65, I=5046.0,   axis="boom-stick pin",   motion="pitch"),
    "boom":   dict(mass=3300,  length=5.70, width=0.65, height=0.85, I=35739.0,  axis="upper-boom pin",   motion="pitch"),
    "upper":  dict(mass=12300, length=4.80, width=2.70, height=2.50, I=31088.25, axis="vertical swing axis", motion="yaw"),
    "lower":  dict(mass=4000,  length=4.45, width=2.98, height=0.90, I=9560.966667, axis="carbody travel axis", motion="translation"),
}
#            min,  max, init, vmax deg/s, amax deg/s^2
ARM_ZERO_SHIFT = 70.0
SHEET03 = {
    "bucket": ( -34.0, 45,  0, 25.0, 55.0),   # min overridden by the user: sheet 03 says -110, minimum is -34.0 deg
    # arm angle zero shifted by the user: the pose sheet 03 calls -70 deg is now 0 deg  ->  every sheet angle + 70
    # (sheet range -130..-8.5 [max overridden by the user, sheet says 30] -> -60..61.5, initial -55 -> 15)
    "arm":    (-130 + ARM_ZERO_SHIFT, -8.5 + ARM_ZERO_SHIFT, -18.0, 20.0, 45.0),   # initial -18 deg set by the user (sheet: -55 + 70 = 15)
    "boom":   ( -20,  75,  39, 12.0, 25.0),                                         # initial 39 deg set by the user (sheet: 25)
    "swing":  (-180, 180,   0, 67.5, 30.0),
}
TRAVEL_VMAX = SHEET01["travel_max_kmh"] / 3.6
TRAVEL_AMAX = 1.0
TRAVEL_DIST, FPS, PAUSE = 8.0, 24, 0.5
PIN_SCALE, CYL_RADIUS_SCALE = 1.6, 1.7

# =====================  SHEET 09_좌표계_무게중심_관절축  =====================
# Frame: O = ground point under the centre of the tracks (between L/R tracks and between front/rear roller centres),
#        +X = machine front, +Y = machine left, +Z = up; chassis frame is fixed at O and moves/rotates with the machine.
# pitch +  = lift (Blender local-Y rotation is the negative of it so that +X goes up);  yaw + = swing left (= Blender +Z).
# Links are straight bars along their local +X; a child's hinge is given in the parent's local frame.
SHEET09 = {   # hinge (parent frame, m)       CG (own frame, m)           axis
    "lower":  dict(hinge=(0.0, 0.0, 0.0),  cg=(0.0, 0.0, 0.65),    axis="travel"),
    "upper":  dict(hinge=(0.0, 0.0, 1.30), cg=(-0.35, 0.0, 1.15),  axis="yaw +Z"),
    "boom":   dict(hinge=(0.75, 0.0, 0.60), cg=(2.85, 0.0, 0.0),   axis="pitch -Y"),
    "stick":  dict(hinge=(5.7, 0.0, 0.0),  cg=(1.45, 0.0, 0.0),    axis="pitch -Y"),
    "bucket": dict(hinge=(2.9, 0.0, 0.0),  cg=(0.785, 0.0, 0.0),   axis="pitch -Y"),
}
PAYLOAD = dict(parent="bucket", min_kg=0, max_kg=1500, cg=(0.785, 0.0, 0.0))   # calculation-only mass

# --- CG REVIEW (own-frame CG = (x along the part's bar / for the upper body: forward of the swing axis, y = machine-left, z = perpendicular
# to the bar / for the upper body: above the swing hinge)). Values below come from the actual mesh layout (surface-area centroid of the
# part's meshes in the rest pose, printed as GEOM_OWN at build time), NOT from the sheet and NOT tuned for stability.
#   upper : x -0.85 is the requested comparison value; mesh centroid x = -0.854 (volume centroid -0.947), y +0.10 (cab/left side)
#           height 1.15 kept (mesh centroid would be 0.54, only the dynamic sensitivity is reported, see report)
#   boom  : mesh centroid 2.68 along the bar (bar mid-point was 2.85), 0.32 above the bar, 0.81 m right of the machine centre plane
#   stick : 1.23 along the bar (mid-point 1.45), 0.06 below the bar, y -0.81
#   bucket: pin-centred body hanging below the pin line: x 0.11, z -0.76, y -0.81;  payload fills the bucket: bbox centre (-0.11, -0.81, -0.81)
import os as _os
CG_STAGE = _os.environ.get("CG_STAGE", "full")        # old = sheet values | upper = only upper X -0.85 | full = layout-based review (default)
if CG_STAGE in ("upper", "full"):
    SHEET09["upper"]["cg"] = (-0.85, 0.0, 1.15)
if CG_STAGE == "full":
    SHEET09["upper"]["cg"] = (-0.85, 0.10, 1.15)
    SHEET09["boom"]["cg"] = (2.68, -0.81, 0.32)
    SHEET09["stick"]["cg"] = (1.23, -0.81, -0.06)
    SHEET09["bucket"]["cg"] = (0.11, -0.81, -0.76)
    PAYLOAD["cg"] = (-0.11, -0.81, -0.81)
print("CG_STAGE", CG_STAGE)

# =====================  READ ORIGINAL MODEL (world space)  =====================
D = bpy.data.objects
bpy.context.view_layer.update()
N = lambda n: "Excavator_" + n
W = {}                                   # name -> world-space vertex array
for o in D:
    if o.type == "MESH":
        M = o.matrix_world
        W[o.name] = np.array([tuple(M @ v.co) for v in o.data.vertices])
ctr = lambda n: (W[N(n)].max(0) + W[N(n)].min(0)) / 2
ext = lambda arrs, ax: np.concatenate(arrs)[:, ax].max() - np.concatenate(arrs)[:, ax].min()

LOWER = ["Tracs", "Idlers", "Base", "Turn_Base"]
UPPER = ["Body", "Lights", "Exhaust", "Filter", "Door_Handle"]
BOOM = ["Arm_Long_01", "Arm_Long_02"]
# Bucket linkage: the link bar (Arm_Bucket) and its left pin (Axle_07) are fixed to the arm - they never leave it. The bucket turns
# about the upper pin (Axle_08, fixed on the arm); only the bucket body and its heel pin (Axle_09) move with the bucket.
STICK = ["Arm_Short", "Arm_Bucket"]
BUCKET = ["Bucket"]
PINS = {"upper": ["Axle_01", "Axle_02"], "boom": ["Axle_03", "Axle_04", "Axle_05"],
        "stick": ["Axle_07", "Axle_08"], "bucket": ["Axle_09"]}
# Axle_06 sat in the middle of the stick: it is neither a hinge nor a cylinder anchor (nearest joint point 0.63 m away), it only
# sticks out of the stick sides -> removed. (Every remaining pin is a pivot or a hydraulic-cylinder anchor.)
for _n in ("Axle_06",):
    bpy.data.objects.remove(D[N(_n)], do_unlink=True)

# --- sheet 09: coordinate frame. Origin O sits on the ground under the swing axis / track centre; +X front, +Y left, +Z up.
S0_orig = ctr("Turn_Base")[:2].copy()
SHIFT = np.array([S0_orig[0], S0_orig[1], 0.0])
for _k in W: W[_k] = W[_k] - SHIFT                                  # swing axis now at x = y = 0
S0 = np.zeros(3)                                                    # swing axis, ground level
Z_RING = W[N("Turn_Base")][:, 2].max()                              # top of lower body (orig)
B0, E0, K0 = ctr("Axle_02"), ctr("Axle_05"), ctr("Axle_08")         # boom foot / elbow / bucket pin
phi = lambda a, b: math.atan2((b - a)[2], (b - a)[0])
phi_b, phi_s = phi(B0, E0), phi(E0, K0)
REST = {"boom": math.degrees(phi_b), "arm": math.degrees(phi_s - phi_b) + ARM_ZERO_SHIFT, "bucket": 0.0, "swing": 0.0}   # arm rest measured in the shifted (user) convention
ARM_SWEEP = f'arm_{SHEET03["arm"][1]:g}_to_{SHEET03["arm"][0]:g}'                      # label of the arm max -> min sweep (used for the still renders)
print("model rest angles", REST)

# =====================  SCALE FACTORS FROM SHEET 01/02  =====================
low_all = [W[N(n)] for n in LOWER]
sx_l = SHEET02["lower"]["length"] / ext(low_all, 0)
sy_l = SHEET02["lower"]["width"] / ext(low_all, 1)
sz_l = SHEET02["lower"]["height"] / (np.concatenate(low_all)[:, 2].max())
up_all = [W[N(n)] for n in UPPER] + [W[N(n)] for n in PINS["upper"]]
su = np.array([SHEET02["upper"]["length"] / ext(up_all, 0),
               SHEET02["upper"]["width"] / ext(up_all, 1),
               SHEET02["upper"]["height"] / ext(up_all, 2)])
Z_UP = SHEET09["upper"]["hinge"][2]                                 # swing hinge height (sheet 09); upper body sits on it

def basis(ph):
    return np.array([math.cos(ph), 0, math.sin(ph)]), np.array([-math.sin(ph), 0, math.cos(ph)])

def link_A(ph, sl, sw, st):
    u, v = basis(ph); y = np.array([0, 1.0, 0])
    return sl * np.outer(u, u) + st * np.outer(v, v) + sw * np.outer(y, y)

def perp_extent(arrs, origin, ph):
    u, v = basis(ph); P = (np.concatenate(arrs) - origin) @ v
    return P.max() - P.min()

boom_arrs = [W[N(n)] for n in BOOM]; stick_arrs = [W[N("Arm_Short")]]      # arm width/height scale from the arm body only (not the link bar)
xz = lambda v: np.linalg.norm(np.asarray(v)[[0, 2]])                 # hinge distances are measured in the kinematic (X-Z) plane
sl_b = SHEET09["stick"]["hinge"][0] / xz(E0 - B0)                    # stick hinge at boom-local (5.7, 0, 0)
sw_b = SHEET02["boom"]["width"] / ext(boom_arrs, 1)
st_b = float(np.clip(SHEET02["boom"]["height"] / perp_extent(boom_arrs, B0, phi_b), 1.0, 3.0))
sl_s = SHEET09["bucket"]["hinge"][0] / xz(K0 - E0)                   # bucket hinge at stick-local (2.9, 0, 0)
sw_s = SHEET02["stick"]["width"] / ext(stick_arrs, 1)
st_s = float(np.clip(SHEET02["stick"]["height"] / perp_extent(stick_arrs, E0, phi_s), 1.0, 3.0))
bk = W[N("Bucket")]
A_k = np.diag([SHEET02["bucket"]["length"] / ext([bk], 0), SHEET02["bucket"]["width"] / ext([bk], 1), 0.0])
A_k[2, 2] = A_k[1, 1]
A_b, A_s = link_A(phi_b, sl_b, sw_b, st_b), link_A(phi_s, sl_s, sw_s, st_s)

# group transforms (original world point(s) -> new world point(s))
_trc = (W[N("Tracs")] - S0) * np.array([sx_l, sy_l, sz_l])
LOWER_SHIFT = -np.array([(_trc.max(0)[0] + _trc.min(0)[0]) / 2, (_trc.max(0)[1] + _trc.min(0)[1]) / 2, 0.0])  # track centre -> O
def G_lower(P): return np.array([S0[0], S0[1], 0]) + (P - S0) * np.array([sx_l, sy_l, sz_l]) + LOWER_SHIFT
def G_upper(P): return np.array([S0[0], S0[1], Z_UP]) + (P - np.array([S0[0], S0[1], Z_RING])) * su
_b_vis = G_upper(B0)                                                 # where the boom foot pin would sit on the scaled body
B1 = np.array([SHEET09["boom"]["hinge"][0], _b_vis[1], Z_UP + SHEET09["boom"]["hinge"][2]])  # boom hinge from sheet 09 (X, Z); keep body Y
INT_OFF = np.array([-S0_orig[0], -S0_orig[1], Z_UP - 0.9])           # cab interior was laid out in the earlier frame
def G_boom(P): return B1 + (P - B0) @ A_b.T
E1 = G_boom(E0)
def G_stick(P): return E1 + (P - E0) @ A_s.T
K1 = G_stick(K0)
def G_bucket(P): return K1 + (P - K0) @ A_k.T
GROUPS = {"lower": G_lower, "upper": G_upper, "boom": G_boom, "stick": G_stick, "bucket": G_bucket}
SW = {"upper": su[1], "boom": sw_b, "stick": sw_s, "bucket": A_k[1, 1], "lower": sy_l}

# =====================  BAKE NEW GEOMETRY  =====================
NEW = {}     # object name -> new world vertex array
for grp, names in (("lower", LOWER), ("upper", UPPER), ("boom", BOOM), ("stick", STICK), ("bucket", BUCKET)):
    for n in names:
        NEW[N(n)] = GROUPS[grp](W[N(n)])
# --- close the gap at the elbow: after anisotropic scaling the boom tip stops short of the boom/stick pin.
# Stretch only the tip region of the boom (along its length) so that it reaches the pin (+8 cm overlap).
_ub = np.array([math.cos(phi_b), 0, math.sin(phi_b)])
_boom_keys = [N(n) for n in BOOM]
_amax = max(float(((NEW[k] - B1) @ _ub).max()) for k in _boom_keys)
ELBOW_T0, ELBOW_REACH = 3.4, SHEET09["stick"]["hinge"][0] + 0.08     # stretch starts past the boom-cylinder pin (~3.2 m)
elbow_gap_before = SHEET09["stick"]["hinge"][0] - _amax
if _amax < ELBOW_REACH - 1e-6:
    _f = (ELBOW_REACH - ELBOW_T0) / (_amax - ELBOW_T0)
    for k in _boom_keys:
        _a = (NEW[k] - B1) @ _ub
        NEW[k] = NEW[k] + np.outer(np.where(_a > ELBOW_T0, (_a - ELBOW_T0) * (_f - 1), 0.0), _ub)
print("elbow: boom tip was", round(elbow_gap_before, 3), "m short of the pin; stretched by factor", round(_f, 3))
# --- centre the rounded boom tip on the elbow pin: the tip used to sit ~0.2 m below the pin axis, so the stick pivoted next to
# the boom instead of in it. Lift the tip (smooth ramp) until the pin runs through the middle of the tip end.
_vb = np.array([-math.sin(phi_b), 0, math.cos(phi_b)])                # perpendicular to the boom link, in the X-Z plane
_al = {k: (NEW[k] - B1) @ _ub for k in _boom_keys}
_a2 = max(float(a.max()) for a in _al.values())
_tipv = np.concatenate([NEW[k][_al[k] > _a2 - 0.25] for k in _boom_keys]) - E1
_tip_c = float((_tipv @ _vb).max() + (_tipv @ _vb).min()) / 2
for k in _boom_keys:
    _w = np.clip((_al[k] - ELBOW_T0) / (5.5 - ELBOW_T0), 0, 1); _w = _w * _w * (3 - 2 * _w)
    NEW[k] = NEW[k] + np.outer(_w * (-_tip_c), _vb)
print("elbow: boom tip centre was", round(_tip_c, 3), "m off the pin axis -> centred")
# --- boom foot: the lower end of the boom was a thin blade that stopped ~0.3-0.4 m away from the foot pin, so the boom hovered
# above the body for most boom angles. Bring the very end of the blade onto the hinge pin (smooth ramp): the foot then turns
# around the pin and stays inside the body outline at every boom angle.
_al = {k: (NEW[k] - B1) @ _ub for k in _boom_keys}; _pp = {k: (NEW[k] - B1) @ _vb for k in _boom_keys}
_amin = min(float(a.min()) for a in _al.values())
_end_a = np.concatenate([_al[k][_al[k] < _amin + 0.15] for k in _boom_keys]); _end_p = np.concatenate([_pp[k][_al[k] < _amin + 0.15] for k in _boom_keys])
_foot_c = np.array([(_end_a.max() + _end_a.min()) / 2, (_end_p.max() + _end_p.min()) / 2])    # (along, perp) of the blade end, hinge = (0, 0)
FOOT_RAMP = 1.2
for k in _boom_keys:
    _w = np.clip((_amin + FOOT_RAMP - _al[k]) / FOOT_RAMP, 0, 1); _w = _w * _w * (3 - 2 * _w)
    NEW[k] = NEW[k] + np.outer(_w * (-_foot_c[0]), _ub) + np.outer(_w * (-_foot_c[1]), _vb)
foot_end_off_before = float(np.linalg.norm(_foot_c))
print("boom foot: blade end was", round(foot_end_off_before, 3), "m from the hinge pin -> moved onto the pin")
# --- arm tip: the lower end of the arm stopped ~0.4 m short of / past the bucket pivot (upper pin Axle_08), so the bucket's heel
# came loose from the arm for most bucket angles. Put the very end of the arm onto the pivot (smooth ramp): the bucket then turns
# about a pin that runs through the arm end and the bucket ear, and the two always overlap.
_us = np.array([math.cos(phi_s), 0, math.sin(phi_s)]); _vs = np.array([-math.sin(phi_s), 0, math.cos(phi_s)])
_sa = (NEW[N("Arm_Short")] - K1) @ _us; _sp = (NEW[N("Arm_Short")] - K1) @ _vs
_se = _sa > _sa.max() - 0.15
_tip_c = np.array([(_sa[_se].max() + _sa[_se].min()) / 2, (_sp[_se].max() + _sp[_se].min()) / 2])   # (along, perp) of the arm end; pivot = (0, 0)
ARM_RAMP = 1.0
_w = np.clip((_sa - (_sa.max() - ARM_RAMP)) / ARM_RAMP, 0, 1); _w = _w * _w * (3 - 2 * _w)
NEW[N("Arm_Short")] = NEW[N("Arm_Short")] + np.outer(_w * (-_tip_c[0]), _us) + np.outer(_w * (-_tip_c[1]), _vs)
arm_tip_off_before = float(np.linalg.norm(_tip_c))
print("arm tip: end was", round(arm_tip_off_before, 3), "m from the bucket pivot -> moved onto the pivot")
for grp, names in PINS.items():                  # pins: move with group, keep round, scale about own centre
    for n in names:
        c0 = ctr(n); c1 = GROUPS[grp](c0)
        NEW[N(n)] = c1 + (W[N(n)] - c0) * np.array([PIN_SCALE, SW[grp], PIN_SCALE])
# boom-foot pin cap (Axle_02) stays on the body but the boom hinge was raised to the sheet-09 height -> follow the hinge
NEW[N("Axle_02")] = NEW[N("Axle_02")] + np.array([B1[0] - _b_vis[0], 0.0, B1[2] - _b_vis[2]])
# boom-foot pin (Axle_02) was only a thin cap on the outside of the body: make it a real pin that runs from the body's outer
# face through the boom foot (so boom and body are visibly joined by it).
_p2 = NEW[N("Axle_02")]
_foot_y = np.concatenate([NEW[N(n)][:, 1] for n in BOOM])                # boom width range (y)
_y_out = float(_p2[:, 1].min())                                          # outer face of the cap (stays where it is)
_y_in = float(_foot_y.max()) + 0.04                                      # inner side: just past the inner face of the boom foot
NEW[N("Axle_02")][:, 1] = _y_out + (_p2[:, 1] - _y_out) * ((_y_in - _y_out) / max(1e-6, float(_p2[:, 1].max() - _y_out)))
# elbow pin (Axle_05): make it longer than the boom width (+-0.32) so the black pin ends show on the outer faces of boom and stick;
# this pin is also the rotation axis of the stick (Pivot_Stick sits at its centre).
_pin = NEW[N("Axle_05")]; _pc = (_pin[:, 1].max() + _pin[:, 1].min()) / 2
ELBOW_PIN_HALF = 0.40
NEW[N("Axle_05")][:, 1] = _pc + (_pin[:, 1] - _pc) * (ELBOW_PIN_HALF / ((_pin[:, 1].max() - _pin[:, 1].min()) / 2))

def write_mesh(name, verts_world):
    o = D[name]
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
    me = o.data
    me.vertices.foreach_set("co", np.asarray(verts_world, dtype=np.float32).ravel())
    me.update()
for n, v in NEW.items():
    write_mesh(n, v)

# hydraulic cylinders: re-modelled along +Y, origin at base anchor, stretched between two anchors at runtime
def cyl_ends(n):
    V = W[N(n)]; c = V.mean(0); _, _, vt = np.linalg.svd(V - c, full_matrices=False); ax = vt[0]
    t = (V - c) @ ax
    return V, c, ax, t, c + ax * t.min(), c + ax * t.max()
CYL = {}
c1v = cyl_ends("Cylinder_01"); c2v = cyl_ends("Cylinder_02"); c3v = cyl_ends("Cylinder_03")
CYL["Cylinder_01"] = (c1v, ("upper", ctr("Axle_01")), ("boom", ctr("Axle_04")))
e2 = c2v[5] if c2v[5][0] > c2v[4][0] else c2v[4]
CYL["Cylinder_02"] = (c2v, ("boom", ctr("Axle_03")), ("stick", e2))
e3 = c3v[5] if c3v[5][2] > c3v[4][2] else c3v[4]
CYL["Cylinder_03"] = (c3v, ("stick", e3), ("bucket", ctr("Axle_09")))     # rod end on the bucket's heel pin -> it follows the bucket
cyl_info = {}
for n, ((V, c, ax, t, _, _), (ga, pa), (gb, pb)) in CYL.items():
    A1, B1c = GROUPS[ga](pa), GROUPS[gb](pb)
    L1 = float(np.linalg.norm(B1c - A1)); w = (B1c - A1) / L1
    e1 = np.cross(w, [0, 1.0, 0]); e1 = e1 / np.linalg.norm(e1) if np.linalg.norm(e1) > 1e-3 else np.cross(w, [1.0, 0, 0])
    e1 /= np.linalg.norm(e1); e2v = np.cross(w, e1)
    f1 = np.cross(ax, [0, 1.0, 0]); f1 = f1 / np.linalg.norm(f1); f2 = np.cross(ax, f1)
    r = (V - c) - np.outer(t, ax)
    loc = np.stack([(r @ f1) * CYL_RADIUS_SCALE, (t - t.min()) / (t.max() - t.min()) * L1, (r @ f2) * CYL_RADIUS_SCALE], 1)
    o = D[N(n)]; o.parent = None
    o.data.vertices.foreach_set("co", loc.astype(np.float32).ravel()); o.data.update()
    Mx = Matrix([[e1[0], w[0], e2v[0], A1[0]], [e1[1], w[1], e2v[1], A1[1]],
                 [e1[2], w[2], e2v[2], A1[2]], [0, 0, 0, 1]])
    o.matrix_world = Mx
    cyl_info[n] = dict(A=(ga, A1), B=(gb, B1c), L=L1)

# =====================  RIG  =====================
sc = bpy.context.scene
for o in list(D):                                   # remove the old non-uniformly scaled root
    if o.name == "Excavator_Empty_Group":
        bpy.data.objects.remove(o)
def empty(name, at, parent=None, size=0.3, kind='ARROWS'):
    e = bpy.data.objects.new(name, None); e.empty_display_type, e.empty_display_size = kind, size
    e.location = Vector(at); sc.collection.objects.link(e)
    if parent is not None:
        e.parent = parent; e.matrix_parent_inverse = parent.matrix_world.inverted()
    return e
def attach(child, parent):
    mw = child.matrix_world.copy(); child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted(); child.matrix_world = mw

root = empty("Excavator_Root", (0, 0, 0), size=0.5)
bpy.context.view_layer.update()
P_SWING = (S0[0], S0[1], Z_UP)
p_swing = empty("Pivot_Swing", P_SWING, root); bpy.context.view_layer.update()
p_boom = empty("Pivot_Boom", B1, p_swing); bpy.context.view_layer.update()
p_stick = empty("Pivot_Stick", E1, p_boom); bpy.context.view_layer.update()
p_bucket = empty("Pivot_Bucket", K1, p_stick); bpy.context.view_layer.update()
PIV = {"lower": root, "upper": p_swing, "boom": p_boom, "stick": p_stick, "bucket": p_bucket}
# Upper body and lower body must always be joined. The upper body sits on the swing hinge plane (1.3 m, sheet 09) while the track
# frames top out at ~0.67-0.86 m, which left a 0.4 m gap under the body. Two parts close it:
#  * slew ring (lower group): from the top of the lower frame (Base) up into the body -> the turntable column
#  * body skirt (upper group, turns with the body): fills the body footprint down to just above the track tops
_base_top = float(NEW[N("Base")][:, 2].max()); _trk_top = float(NEW[N("Tracs")][:, 2].max())
_ring_z0, _ring_z1 = _base_top - 0.02, Z_UP + 0.02
bpy.ops.mesh.primitive_cylinder_add(radius=0.95, depth=_ring_z1 - _ring_z0, vertices=40, location=(0, 0, (_ring_z0 + _ring_z1) / 2))
_ring = bpy.context.active_object; _ring.name = _ring.data.name = N("Slew_Ring")
_ring.data.materials.append(bpy.data.materials["Metal_Black"])
_bv = NEW[N("Body")]; _bot = _bv[_bv[:, 2] < _bv[:, 2].min() + 0.15]
_inset = 0.10                                                          # keep the skirt just inside the body outline
_x0, _x1 = _bot[:, 0].min() + _inset, _bot[:, 0].max() - _inset; _y0, _y1 = _bot[:, 1].min() + _inset, _bot[:, 1].max() - _inset
_sk_z0, _sk_z1 = _trk_top - 0.005, Z_UP + 0.02                         # rests on the track tops (5 mm overlap: no visible seam)
bpy.ops.mesh.primitive_cube_add(size=1, location=((_x0 + _x1) / 2, (_y0 + _y1) / 2, (_sk_z0 + _sk_z1) / 2))
_skirt = bpy.context.active_object; _skirt.name = _skirt.data.name = N("Body_Skirt")
_skirt.scale = (_x1 - _x0, _y1 - _y0, _sk_z1 - _sk_z0)
_skirt.data.materials.append(bpy.data.materials["Metal_Yellow"])
# boom-foot boss: a round boss on the boom foot pin. The boom turns about this pin, so the boss never moves relative to the body:
# the boom stays connected to the body at every boom angle (also fully raised).
_fy = NEW[N("Arm_Long_01")][:, 1]
bpy.ops.mesh.primitive_cylinder_add(radius=0.30, depth=float(_fy.max() - _fy.min()) + 0.04, vertices=32,
                                    location=(B1[0], (_fy.max() + _fy.min()) / 2, B1[2]), rotation=(math.radians(90), 0, 0))
_boss = bpy.context.active_object; _boss.name = _boss.data.name = N("Boom_Foot_Boss")
_boss.data.materials.append(bpy.data.materials["Metal_Yellow"])
MEMBERS = {"lower": LOWER + ["Slew_Ring"], "upper": UPPER + PINS["upper"] + ["Body_Skirt"], "boom": BOOM + PINS["boom"] + ["Boom_Foot_Boss"],
           "stick": STICK + PINS["stick"], "bucket": BUCKET + PINS["bucket"]}
bpy.context.view_layer.update()
for g, names in MEMBERS.items():
    for n in names: attach(D[N(n)], PIV[g])

# anchors + stretched cylinders
for n, info in cyl_info.items():
    k = n[-2:]
    a = empty(f"Cyl{k}_A", info["A"][1], PIV[info["A"][0]], 0.12, 'PLAIN_AXES')
    b = empty(f"Cyl{k}_B", info["B"][1], PIV[info["B"][0]], 0.12, 'PLAIN_AXES')
    bpy.context.view_layer.update()
    cyl = D[N(n)]; attach(cyl, root)
    c1 = cyl.constraints.new('COPY_LOCATION'); c1.target = a
    c2 = cyl.constraints.new('STRETCH_TO'); c2.target = b
    c2.rest_length = info["L"]; c2.volume = 'NO_VOLUME'
    cyl["anchor_a"], cyl["anchor_b"], cyl["rest_length"] = a.name, b.name, info["L"]

# --- geometry check: where the actual mesh material of every part sits (rest pose, world frame). Used to justify the CG coordinates.
def _mesh_tris(o):
    me = o.data; M = np.array(o.matrix_world)
    V_ = np.array([M @ np.array([*v.co, 1.0]) for v in me.vertices])[:, :3]
    T_ = []
    for p in me.polygons:
        ids = list(p.vertices)
        for i in range(1, len(ids) - 1): T_.append((ids[0], ids[i], ids[i + 1]))
    return V_, np.array(T_)
def _centroids(names):
    vol = 0.0; vc = np.zeros(3); area = 0.0; ac = np.zeros(3); allv = []
    for n in names:
        V_, T_ = _mesh_tris(D[N(n)]); a, b, c = V_[T_[:, 0]], V_[T_[:, 1]], V_[T_[:, 2]]
        dv = np.einsum('ij,ij->i', a, np.cross(b, c)) / 6.0
        cen = (a + b + c) / 4.0                                       # tetra centroid (apex at origin)
        vol += dv.sum(); vc += (dv[:, None] * cen).sum(0)
        da = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2.0
        area += da.sum(); ac += (da[:, None] * (a + b + c) / 3.0).sum(0); allv.append(V_)
    allv = np.concatenate(allv)
    return dict(vol_c=(vc / vol if abs(vol) > 1e-9 else None), area_c=ac / area, bbox_c=(allv.max(0) + allv.min(0)) / 2,
                bmin=allv.min(0), bmax=allv.max(0))
GEOM_C = {}
for _g, _names in (("upper", ["Body", "Body_Skirt", "Lights", "Exhaust", "Filter", "Door_Handle"]),
                   ("boom", BOOM), ("stick", STICK), ("bucket", BUCKET)):
    GEOM_C[_g] = _centroids(_names)
    print("GEOM", _g, {k: (None if v is None else np.round(v, 3).tolist()) for k, v in GEOM_C[_g].items()})
_ctr_up = GEOM_C["upper"]["area_c"]
# project the link parts into their own (sheet-09) frame: s along the hinge->next-hinge bar, v perpendicular (+ up), y = lateral
for _g, _h, _ph in (("boom", B1, phi_b), ("stick", E1, phi_s), ("bucket", K1, phi_s)):
    _u, _v = basis(_ph)
    for _k in ("vol_c", "area_c", "bbox_c"):
        _c = GEOM_C[_g][_k]
        if _c is not None:
            _d = _c - _h; GEOM_C[_g][_k + "_own"] = np.array([_d @ _u, _d[1], _d @ _v])
    print("GEOM_OWN", _g, {k: np.round(GEOM_C[_g][k + "_own"], 3).tolist() for k in ("vol_c", "area_c", "bbox_c") if (k + "_own") in GEOM_C[_g]})
_up_own = {k: (GEOM_C["upper"][k] - np.array([0, 0, Z_UP])) for k in ("vol_c", "area_c", "bbox_c")}
print("GEOM_OWN upper (rel. swing hinge)", {k: np.round(v, 3).tolist() for k, v in _up_own.items()})

# centres of mass from sheet 09 (own-frame CG, straight-bar approximation; y = 0 = machine centre plane, ride with the part)
u_b =np.array([math.cos(phi_b), 0, math.sin(phi_b)]); u_s = np.array([math.cos(phi_s), 0, math.sin(phi_s)])
def _flat(p): return np.array([p[0], 0.0, p[2]])
hinge_w = {"boom": B1, "stick": E1, "bucket": K1}
v_b = np.array([-math.sin(phi_b), 0, math.cos(phi_b)]); v_s = np.array([-math.sin(phi_s), 0, math.cos(phi_s)])
def _own(h, u, v, cg):    # own-frame (x along bar, y lateral, z perpendicular) -> rest-pose world point
    return _flat(h) + cg[0] * u + cg[2] * v + np.array([0, cg[1], 0])
cg_world = {
    "lower":  np.array(SHEET09["lower"]["cg"]),
    "upper":  np.array([0, 0, Z_UP]) + np.array(SHEET09["upper"]["cg"]),
    "boom":   _own(B1, u_b, v_b, SHEET09["boom"]["cg"]),
    "stick":  _own(E1, u_s, v_s, SHEET09["stick"]["cg"]),
    "bucket": _own(K1, u_s, v_s, SHEET09["bucket"]["cg"]),
}
cg_world["payload"] = _own(K1, u_s, v_s, PAYLOAD["cg"])
com_nodes = {}
for g, p in cg_world.items():
    parent = PIV["bucket" if g == "payload" else g]
    e = empty(f"CoM_{g}", p, parent, 0.2, 'SPHERE')
    e["mass_kg"] = PAYLOAD["max_kg"] if g == "payload" else SHEET02[g]["mass"]
    if g == "payload": e["mass_kg_range"] = f'{PAYLOAD["min_kg"]}..{PAYLOAD["max_kg"]}'
    com_nodes[g] = e
bpy.context.view_layer.update()

# =====================  FIRST-PERSON CAB INTERIOR (objects named Int_*; only in the 1st-person model) =====================
def mat(name, rgb, rough=0.7, metal=0.0, emit=None, strength=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = strength
    return m
M_FAB = mat("Int_Fabric", (0.07, 0.075, 0.08), 0.95)
M_PLA = mat("Int_Plastic", (0.03, 0.033, 0.036), 0.5)
M_MET = mat("Int_Metal", (0.5, 0.52, 0.55), 0.35, 0.9)
M_KNB = mat("Int_Knob", (0.95, 0.55, 0.05), 0.45)
M_FLR = mat("Int_Floor", (0.05, 0.05, 0.055), 0.9)
M_SCR = mat("Int_Screen", (0.02, 0.08, 0.1), 0.2, emit=(0.1, 0.8, 0.9), strength=2.5)

CAB_FLOOR = 1.50                     # (earlier frame) measured from the cab shell (floor faces at z = 1.48 .. 1.57)
EYE_OLD = (-0.82, 0.65, 2.58)        # (earlier frame) seated eye point, centre of the cab
O = lambda c: tuple(np.asarray(c, dtype=float) + INT_OFF)       # earlier frame -> sheet-09 frame (swing axis at O, hinge plane z = 1.3)
EYE = O(EYE_OLD)
def _new(op, name, m, loc, rot=None, scale=None):
    op(location=O(loc)); o = bpy.context.active_object; o.name = name; o.data.name = name
    o.data.materials.append(m)
    if rot: o.rotation_euler = [math.radians(a) for a in rot]
    if scale: o.scale = scale
    return o
def box(name, c, s, m, rot=None): return _new(lambda location: bpy.ops.mesh.primitive_cube_add(size=1, location=location), name, m, c, rot, s)
def cylinder(name, c, r, h, m): return _new(lambda location: bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=20, location=location), name, m, c)
def ball(name, c, r, m): return _new(lambda location: bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=16, ring_count=10, location=location), name, m, c)

joy = {"L": (-0.38, 1.08, 2.06), "R": (-0.38, 0.22, 2.06)}          # joystick bases (L = operator's left = +Y)
lev = {"L": (0.15, 0.80, CAB_FLOOR + 0.02), "R": (0.15, 0.50, CAB_FLOOR + 0.02)}  # travel lever bases
piv = {}
for side, at in joy.items(): piv["Joy" + side] = empty("Int_Joy" + side, O(at), None, 0.1, 'PLAIN_AXES')
for side, at in lev.items(): piv["Lev" + side] = empty("Int_Lev" + side, O(at), None, 0.1, 'PLAIN_AXES')
eye = empty("Int_Eye", EYE, None, 0.15, 'SPHERE')
bpy.context.view_layer.update()
parts = [  # (object, parent)
    (box("Int_Floor", (-0.5, 0.65, CAB_FLOOR + 0.01), (1.9, 1.0, 0.02), M_FLR), p_swing),
    (cylinder("Int_Seat_Base", (-0.8, 0.65, 1.63), 0.11, 0.26, M_PLA), p_swing),
    (box("Int_Seat_Cushion", (-0.78, 0.65, 1.79), (0.52, 0.50, 0.12), M_FAB), p_swing),
    (box("Int_Seat_Back", (-1.03, 0.65, 2.12), (0.10, 0.50, 0.64), M_FAB, rot=(0, -10, 0)), p_swing),
    (box("Int_Seat_Head", (-1.10, 0.65, 2.52), (0.08, 0.30, 0.20), M_FAB, rot=(0, -10, 0)), p_swing),
    (box("Int_Console_L", (-0.62, 1.08, 1.78), (0.55, 0.20, 0.56), M_PLA), p_swing),
    (box("Int_Console_R", (-0.62, 0.22, 1.78), (0.55, 0.20, 0.56), M_PLA), p_swing),
    (box("Int_Armrest_L", (-0.80, 1.08, 2.09), (0.28, 0.14, 0.05), M_FAB), p_swing),
    (box("Int_Armrest_R", (-0.80, 0.22, 2.09), (0.28, 0.14, 0.05), M_FAB), p_swing),
    (box("Int_Dash", (0.45, 0.65, 1.68), (0.30, 1.10, 0.34), M_PLA), p_swing),
    (box("Int_Monitor", (0.40, 1.08, 2.45), (0.05, 0.34, 0.22), M_PLA), p_swing),
    (box("Int_Screen", (0.372, 1.08, 2.45), (0.006, 0.30, 0.18), M_SCR), p_swing),
]
for side in ("L", "R"):
    jx, jy, jz = joy[side]; lx, ly, lz = lev[side]
    parts += [(cylinder(f"Int_Joy{side}_Stick", (jx, jy, jz + 0.14), 0.017, 0.28, M_MET), piv["Joy" + side]),
              (ball(f"Int_Joy{side}_Knob", (jx, jy, jz + 0.30), 0.038, M_KNB), piv["Joy" + side]),
              (cylinder(f"Int_Lev{side}_Stick", (lx, ly, lz + 0.20), 0.02, 0.40, M_MET), piv["Lev" + side]),
              (box(f"Int_Lev{side}_Knob", (lx, ly, lz + 0.42), (0.05, 0.05, 0.09), M_KNB), piv["Lev" + side]),
              (box(f"Int_Pedal_{side}", (lx + 0.11, ly, CAB_FLOOR + 0.03), (0.14, 0.10, 0.02), M_MET), p_swing)]
bpy.context.view_layer.update()
for o, par in parts: attach(o, par)
for k in piv.values(): attach(k, p_swing)
attach(eye, p_swing)
cam_fp_d = bpy.data.cameras.new("Int_Camera"); cam_fp_d.lens = 20; cam_fp_d.clip_start = 0.05
cam_fp = bpy.data.objects.new("Int_Camera", cam_fp_d); sc.collection.objects.link(cam_fp)
cam_fp.location = EYE; cam_fp.rotation_euler = (math.radians(90), 0, math.radians(-90))   # looks along +X (machine front)
bpy.context.view_layer.update(); attach(cam_fp, p_swing)

# sheet data on the objects
root["sheet01"] = json.dumps(SHEET01); root["travel_vmax_m_s"], root["travel_amax_m_s2"] = TRAVEL_VMAX, TRAVEL_AMAX
for g, d in SHEET02.items():
    PIV[g]["part"] = g
    for k, v in d.items(): PIV[g][f"s02_{k}"] = v
    PIV[g]["s09_hinge_parent_frame_m"] = list(SHEET09[g]["hinge"]); PIV[g]["s09_cg_own_frame_m"] = list(SHEET09[g]["cg"])
    PIV[g]["s09_axis"] = SHEET09[g]["axis"]
root["frame_note"] = "sheet 09: O = ground under track centre; +X front, +Y left, +Z up"
JOINT = {"swing": (p_swing, 2, +1), "boom": (p_boom, 1, -1), "arm": (p_stick, 1, -1), "bucket": (p_bucket, 1, -1)}
def to_rot(j, th): return JOINT[j][2] * math.radians(th - REST[j])
for j, (lo, hi, init, vmax, amax) in SHEET03.items():
    p, axis, _ = JOINT[j]
    p["min_deg"], p["max_deg"], p["init_deg"], p["vmax_deg_s"], p["amax_deg_s2"], p["rest_deg"] = lo, hi, init, vmax, amax, REST[j]
    p.rotation_mode = 'XYZ'
    c = p.constraints.new('LIMIT_ROTATION'); c.owner_space = 'LOCAL'
    a, b = sorted((to_rot(j, lo), to_rot(j, hi)))
    setattr(c, "use_limit_" + "xyz"[axis], True); setattr(c, "min_" + "xyz"[axis], a); setattr(c, "max_" + "xyz"[axis], b)

# =====================  DEMO ANIMATION (sheet 03 limits)  =====================
def profile(d, v, a):
    if d <= 0: return 0.0, (lambda t: 0.0)
    ta = v / a; da = 0.5 * a * ta * ta
    if 2 * da >= d:
        ta = math.sqrt(d / a); T = 2 * ta
        return T, (lambda t: 0.5*a*t*t if t <= ta else d - 0.5*a*(T-t)**2)
    tc = (d - 2*da) / v; T = 2*ta + tc
    return T, (lambda t: 0.5*a*t*t if t < ta else (da + v*(t-ta) if t < ta+tc else d - 0.5*a*(T-t)**2))
segs = []
for j in ("boom", "arm", "bucket", "swing"):
    lo, hi, init, vmax, amax = SHEET03[j]
    segs += [(j, a, b, vmax, amax) for a, b in ((init, hi), (hi, lo), (lo, init))]
segs += [("travel", 0.0, TRAVEL_DIST, TRAVEL_VMAX, TRAVEL_AMAX), ("travel", TRAVEL_DIST, 0.0, TRAVEL_VMAX, TRAVEL_AMAX)]
state = {j: SHEET03[j][2] for j in SHEET03}; state["travel"] = 0.0
frames, events = [dict(state)], []
for ch, a, b, v, acc in segs:
    T, f = profile(abs(b - a), v, acc); n = max(1, round(T * FPS)); s = 1 if b >= a else -1
    for i in range(1, n + 1):
        state[ch] = a + s * f(min(T, i / FPS)) if i < n else b; frames.append(dict(state))
    events.append((len(frames), f"{ch}_{a:g}_to_{b:g}"))
    for _ in range(round(PAUSE * FPS)): frames.append(dict(state))
sc.frame_start, sc.frame_end, sc.render.fps = 1, len(frames), FPS
for i, st in enumerate(frames, start=1):
    for j, (p, axis, _) in JOINT.items():
        e = [0, 0, 0]; e[axis] = to_rot(j, st[j]); p.rotation_euler = e; p.keyframe_insert("rotation_euler", frame=i)
    root.location.x = st["travel"]; root.keyframe_insert("location", frame=i)

# =====================  SCENE  =====================
bpy.ops.mesh.primitive_plane_add(size=80, location=(6, 0, 0)); g = bpy.context.active_object; g.name = "Ground"
gm = bpy.data.materials.new("Ground_Mat"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.34, 0.24, 1)
g.data.materials.append(gm)
sun = bpy.data.lights.new("Sun", 'SUN'); sun.energy = 4.0
so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (math.radians(50), math.radians(10), math.radians(35)); sc.collection.objects.link(so)
w_ = sc.world or bpy.data.worlds.new("World"); sc.world = w_; w_.use_nodes = True
w_.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.74, 0.9, 1)
cd = bpy.data.cameras.new("Camera"); cd.lens = 40
cam = bpy.data.objects.new("Camera", cd); sc.collection.objects.link(cam); cam.location = (14, -16, 8)
aim = bpy.data.objects.new("CamTarget", None); aim.location = (1.5, 0, 2.5); sc.collection.objects.link(aim)
tc = cam.constraints.new('TRACK_TO'); tc.target, tc.track_axis, tc.up_axis = aim, 'TRACK_NEGATIVE_Z', 'UP_Y'
sc.camera = cam; sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x, sc.render.resolution_y = 1280, 720

bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/Excavator_CAT320.blend")

# =====================  REPORT: sheet vs. model  =====================
def bb(names):
    V = np.concatenate([NEW[N(n)] for n in names]); return V.max(0) - V.min(0)
lw = bb(LOWER); uw = bb(UPPER + PINS["upper"])
def gap(a_names, b_names):        # smallest vertex-to-vertex distance between two link groups (rest pose)
    A = np.concatenate([NEW[N(n)] for n in a_names]); B = np.concatenate([NEW[N(n)] for n in b_names]); m = 1e9
    for i in range(0, len(A), 500): m = min(m, float(np.sqrt(((A[i:i+500, None, :] - B[None, :, :]) ** 2).sum(2)).min()))
    return round(m, 3)
report = {
    "lower_LxWxH": [round(float(x), 3) for x in lw], "lower_sheet": [4.45, 2.98, 0.90],
    "upper_LxWxH": [round(float(x), 3) for x in uw], "upper_sheet": [4.80, 2.70, 2.50],
    "boom_pin_to_pin_m": round(float(xz(E1 - B1)), 3), "boom_sheet": 5.7,
    "stick_pin_to_pin_m": round(float(xz(K1 - E1)), 3), "stick_sheet": 2.9,
    "elbow_boom_tip_short_of_pin_before_m": round(float(elbow_gap_before), 3),
    "gap_boom_to_stick_min_m": gap(["Arm_Long_01", "Arm_Long_02"], ["Arm_Short"]),
    "gap_stick_to_bucket_min_m": gap(["Arm_Short", "Arm_Bucket"], ["Bucket"]),
    "boom_hinge_world": [round(float(v), 3) for v in B1], "boom_hinge_sheet": [0.75, "y free", 1.9],
    "swing_hinge_world": [0.0, 0.0, Z_UP], "swing_hinge_sheet": [0, 0, 1.3],
    "track_centre_xy": [round(float((NEW[N("Tracs")].max(0)[i] + NEW[N("Tracs")].min(0)[i]) / 2), 3) for i in (0, 1)],
    "cg_world_rest_pose": {g: [round(float(v), 3) for v in p] for g, p in cg_world.items()},
    "cg_upper_world_z": round(float(cg_world["upper"][2]), 3), "cg_upper_world_z_sheet": 2.45,
    "bucket_LxW": [round(float(bb(["Bucket"])[0]), 3), round(float(bb(["Bucket"])[1]), 3)], "bucket_sheet": [1.57, 0.95],
    "boom_WxH_scale": [round(float(sw_b), 3), round(st_b, 3)], "stick_WxH_scale": [round(float(sw_s), 3), round(st_s, 3)],
    "total_mass_kg": sum(d["mass"] for d in SHEET02.values()),
    "model_rest_deg": REST, "frames": len(frames), "seconds": round(len(frames) / FPS, 1),
}
json.dump(report, open(f"{OUT}/report.json", "w"), indent=1, ensure_ascii=False)
print("REPORT", json.dumps(report, ensure_ascii=False))

# =====================  STILLS (optional)  =====================
if RENDER:
    pick = {"initial": 1}
    for fr, lab in events:
        if lab.startswith(("boom_25_to_75", ARM_SWEEP, "bucket_45_to_-34", "swing_0_to_180")): pick[lab] = fr
        if lab.startswith("travel_0"): pick["travel_end"] = fr
    for lab, fr in pick.items():
        sc.frame_set(fr); sc.render.filepath = f"{OUT}/{lab}.png"; bpy.ops.render.render(write_still=True)
    # first-person stills (operator's eye), glass made see-through
    _g = bpy.data.materials["Glass"].node_tree.nodes["Principled BSDF"]; _g.inputs["Alpha"].default_value = 0.12
    sc.camera = cam_fp
    for lab, fr in (("fp_initial", 1), ("fp_" + [l for f, l in events if l.startswith(ARM_SWEEP)][0], pick[ARM_SWEEP])):
        sc.frame_set(fr); sc.render.filepath = f"{OUT}/{lab}.png"; bpy.ops.render.render(write_still=True)
    _g.inputs["Alpha"].default_value = 1.0; sc.camera = cam
    # close-ups of the boom/stick elbow joint (initial pose and a fully curled stick)
    _lens = cam.data.lens; cam.data.lens = 55
    for lab, fr in (("elbow_initial", 1), ("elbow_stick_min", pick[ARM_SWEEP])):
        sc.frame_set(fr); bpy.context.view_layer.update()
        E_w = p_stick.matrix_world.translation.copy()
        aim.location = E_w; cam.location = E_w + Vector((3.5, -8.0, 1.0))
        sc.render.filepath = f"{OUT}/{lab}.png"; bpy.ops.render.render(write_still=True)
    cam.data.lens = _lens; cam.location = (14, -16, 8); aim.location = (1.5, 0, 2.5)

# =====================  WEB EXPORT (rest pose, no animation)  =====================
for p in (p_swing, p_boom, p_stick, p_bucket, root):
    p.animation_data_clear()
    for c in list(p.constraints): p.constraints.remove(c)
    p.rotation_euler = (0, 0, 0)
root.location = (0, 0, 0)
sc.frame_set(1); bpy.context.view_layer.update()
def collect(o, interior):
    if o.name.startswith("Int_") and not interior: return
    yield o
    for c in o.children: yield from collect(c, interior)
def export(path, interior):
    bpy.ops.object.select_all(action='DESELECT')
    for o in collect(root, interior): o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_animations=False,
                              export_extras=True, export_yup=True, export_apply=False)
glb3 = f"{OUT}/web/excavator_3rd.glb"          # 3rd person: exterior only
export(glb3, interior=False)
# 1st person: + cab interior (seat, joysticks, travel levers, dash, monitor, eye point), see-through windows
_gm = bpy.data.materials["Glass"]; _gb = _gm.node_tree.nodes["Principled BSDF"]
_gb.inputs["Alpha"].default_value = 0.12
try: _gm.surface_render_method = 'BLENDED'
except Exception: pass
try: _gm.blend_method = 'BLEND'
except Exception: pass
glb1 = f"{OUT}/web/excavator_1st.glb"
export(glb1, interior=True)
to_js = lambda v: [round(float(x), 4) for x in v]
params = dict(
    sheet01=SHEET01, sheet02=SHEET02,
    sheet03={j: dict(min=v[0], max=v[1], init=v[2], vmax=v[3], amax=v[4]) for j, v in SHEET03.items()},
    travel=dict(vmax=TRAVEL_VMAX, amax=TRAVEL_AMAX),
    rest_deg=REST,
    cylinders={n[-2:]: dict(a="Cyl%s_A" % n[-2:], b="Cyl%s_B" % n[-2:], L=i["L"]) for n, i in cyl_info.items()},
    # sheet 09: support polygon is centred on the origin O (track centre / roller-centre midpoint)
    support=dict(cx=0.0, cy=0.0, length=SHEET01["roller_center_dist_m"], gauge=SHEET01["track_gauge_m"]),
    sheet09={g: dict(hinge=list(d["hinge"]), cg=list(d["cg"]), axis=d["axis"]) for g, d in SHEET09.items()},
    payload=dict(min_kg=PAYLOAD["min_kg"], max_kg=PAYLOAD["max_kg"], parent=PAYLOAD["parent"], cg=list(PAYLOAD["cg"]), node="CoM_payload"),
    com_nodes={g: "CoM_" + g for g in cg_world},
    frame=dict(origin="O = ground under track centre / roller-centre midpoint", x="machine front", y="machine left", z="up"),
    firstperson=dict(eye="Int_Eye", joyL="Int_JoyL", joyR="Int_JoyR", levL="Int_LevL", levR="Int_LevR", eye_pos_blender=list(EYE)),
    coordinate_note="glTF is Y-up: gltf(x,y,z) = blender(x, z, -y)  (so machine-left +Y = glTF -Z)",
)
b64f = lambda p: base64.b64encode(open(p, "rb").read()).decode()
with open(f"{OUT}/web/model_data.js", "w", encoding="utf-8") as f:
    f.write("window.EXCAVATOR_PARAMS=" + json.dumps(params, ensure_ascii=False) + ";\n")
    f.write("window.EXCAVATOR_GLB_3RD_BASE64=\"" + b64f(glb3) + "\";\n")
    f.write("window.EXCAVATOR_GLB_1ST_BASE64=\"" + b64f(glb1) + "\";\n")
print("WEB OK", os.path.getsize(glb3), os.path.getsize(glb1), "bytes (3rd / 1st person glb)")
