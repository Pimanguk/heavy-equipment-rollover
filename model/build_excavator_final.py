"""CAT 320 excavator: Excavator.blend + spreadsheet tabs 01 / 02 / 03  ->  .blend, .glb (web), params.

Usage (Blender 4.x / 5.x):
  blender -b download/Excavator.blend --python build_excavator_final.py -- <out_dir> [--render]

Outputs in <out_dir>:
  Excavator_CAT320.blend   rigged + limits + sheet properties + demo animation
  web/excavator.glb        rest pose, no animation (hierarchy + anchors + CoM nodes)
  web/model_data.js        glb as base64 + params, for web/index.html (works from file://)
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
SHEET03 = {
    "bucket": (-110,  45,   0, 25.0, 55.0),
    "arm":    (-130,  30, -55, 20.0, 45.0),
    "boom":   ( -20,  75,  25, 12.0, 25.0),
    "swing":  (-180, 180,   0, 67.5, 30.0),
}
TRAVEL_VMAX = SHEET01["travel_max_kmh"] / 3.6
TRAVEL_AMAX = 1.0
TRAVEL_DIST, FPS, PAUSE = 8.0, 24, 0.5
PIN_SCALE, CYL_RADIUS_SCALE = 1.6, 1.7

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
STICK = ["Arm_Short"]
BUCKET = ["Bucket", "Arm_Bucket"]
PINS = {"upper": ["Axle_01", "Axle_02"], "boom": ["Axle_03", "Axle_04", "Axle_05"],
        "stick": ["Axle_06", "Axle_08"], "bucket": ["Axle_07", "Axle_09"]}

# key points (original)
S0 = ctr("Turn_Base"); S0 = np.array([S0[0], S0[1], 0.0])          # swing axis, ground level
Z_RING = W[N("Turn_Base")][:, 2].max()                              # top of lower body (orig)
B0, E0, K0 = ctr("Axle_02"), ctr("Axle_05"), ctr("Axle_08")         # boom foot / elbow / bucket pin
phi = lambda a, b: math.atan2((b - a)[2], (b - a)[0])
phi_b, phi_s = phi(B0, E0), phi(E0, K0)
REST = {"boom": math.degrees(phi_b), "arm": math.degrees(phi_s - phi_b), "bucket": 0.0, "swing": 0.0}
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
Z_UP = SHEET02["lower"]["height"]                                   # new height of slew ring

def basis(ph):
    return np.array([math.cos(ph), 0, math.sin(ph)]), np.array([-math.sin(ph), 0, math.cos(ph)])

def link_A(ph, sl, sw, st):
    u, v = basis(ph); y = np.array([0, 1.0, 0])
    return sl * np.outer(u, u) + st * np.outer(v, v) + sw * np.outer(y, y)

def perp_extent(arrs, origin, ph):
    u, v = basis(ph); P = (np.concatenate(arrs) - origin) @ v
    return P.max() - P.min()

boom_arrs = [W[N(n)] for n in BOOM]; stick_arrs = [W[N(n)] for n in STICK]
sl_b = SHEET01["boom_length_m"] / np.linalg.norm(E0 - B0)
sw_b = SHEET02["boom"]["width"] / ext(boom_arrs, 1)
st_b = float(np.clip(SHEET02["boom"]["height"] / perp_extent(boom_arrs, B0, phi_b), 1.0, 3.0))
sl_s = SHEET01["stick_length_m"] / np.linalg.norm(K0 - E0)
sw_s = SHEET02["stick"]["width"] / ext(stick_arrs, 1)
st_s = float(np.clip(SHEET02["stick"]["height"] / perp_extent(stick_arrs, E0, phi_s), 1.0, 3.0))
bk = W[N("Bucket")]
A_k = np.diag([SHEET02["bucket"]["length"] / ext([bk], 0), SHEET02["bucket"]["width"] / ext([bk], 1), 0.0])
A_k[2, 2] = A_k[1, 1]
A_b, A_s = link_A(phi_b, sl_b, sw_b, st_b), link_A(phi_s, sl_s, sw_s, st_s)

# group transforms (original world point(s) -> new world point(s))
def G_lower(P): return np.array([S0[0], S0[1], 0]) + (P - S0) * np.array([sx_l, sy_l, sz_l])
def G_upper(P): return np.array([S0[0], S0[1], Z_UP]) + (P - np.array([S0[0], S0[1], Z_RING])) * su
B1 = G_upper(B0)
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
for grp, names in PINS.items():                  # pins: move with group, keep round, scale about own centre
    for n in names:
        c0 = ctr(n); c1 = GROUPS[grp](c0)
        NEW[N(n)] = c1 + (W[N(n)] - c0) * np.array([PIN_SCALE, SW[grp], PIN_SCALE])

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
CYL["Cylinder_03"] = (c3v, ("stick", e3), ("bucket", ctr("Axle_07")))
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
MEMBERS = {"lower": LOWER, "upper": UPPER + PINS["upper"], "boom": BOOM + PINS["boom"],
           "stick": STICK + PINS["stick"], "bucket": BUCKET + PINS["bucket"]}
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

# centres of mass (bbox centre of each part, rides with the part)
com_nodes = {}
for g, names in MEMBERS.items():
    V = np.concatenate([NEW[N(n)] for n in names]); cm = (V.max(0) + V.min(0)) / 2
    e = empty(f"CoM_{g}", cm, PIV[g], 0.2, 'SPHERE'); e["mass_kg"] = SHEET02[g]["mass"]
    com_nodes[g] = e
bpy.context.view_layer.update()

# sheet data on the objects
root["sheet01"] = json.dumps(SHEET01); root["travel_vmax_m_s"], root["travel_amax_m_s2"] = TRAVEL_VMAX, TRAVEL_AMAX
for g, d in SHEET02.items():
    PIV[g]["part"] = g
    for k, v in d.items(): PIV[g][f"s02_{k}"] = v
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
report = {
    "lower_LxWxH": [round(float(x), 3) for x in lw], "lower_sheet": [4.45, 2.98, 0.90],
    "upper_LxWxH": [round(float(x), 3) for x in uw], "upper_sheet": [4.80, 2.70, 2.50],
    "boom_pin_to_pin_m": round(float(np.linalg.norm(E1 - B1)), 3), "boom_sheet": 5.7,
    "stick_pin_to_pin_m": round(float(np.linalg.norm(K1 - E1)), 3), "stick_sheet": 2.9,
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
        if lab.startswith(("boom_25_to_75", "arm_30_to_-130", "bucket_45_to_-110", "swing_0_to_180")): pick[lab] = fr
        if lab.startswith("travel_0"): pick["travel_end"] = fr
    for lab, fr in pick.items():
        sc.frame_set(fr); sc.render.filepath = f"{OUT}/{lab}.png"; bpy.ops.render.render(write_still=True)

# =====================  WEB EXPORT (rest pose, no animation)  =====================
for p in (p_swing, p_boom, p_stick, p_bucket, root):
    p.animation_data_clear()
    for c in list(p.constraints): p.constraints.remove(c)
    p.rotation_euler = (0, 0, 0)
root.location = (0, 0, 0)
sc.frame_set(1); bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
def collect(o):
    yield o
    for c in o.children: yield from collect(c)
for o in collect(root): o.select_set(True)
glb = f"{OUT}/web/excavator.glb"
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True, export_animations=False,
                          export_extras=True, export_yup=True, export_apply=False)
to_js = lambda v: [round(float(x), 4) for x in v]
params = dict(
    sheet01=SHEET01, sheet02=SHEET02,
    sheet03={j: dict(min=v[0], max=v[1], init=v[2], vmax=v[3], amax=v[4]) for j, v in SHEET03.items()},
    travel=dict(vmax=TRAVEL_VMAX, amax=TRAVEL_AMAX),
    rest_deg=REST,
    cylinders={n[-2:]: dict(a="Cyl%s_A" % n[-2:], b="Cyl%s_B" % n[-2:], L=i["L"]) for n, i in cyl_info.items()},
    support=dict(cx=float((NEW[N("Tracs")].max(0)[0] + NEW[N("Tracs")].min(0)[0]) / 2),
                 cy=float((NEW[N("Tracs")].max(0)[1] + NEW[N("Tracs")].min(0)[1]) / 2),
                 length=SHEET01["roller_center_dist_m"], gauge=SHEET01["track_gauge_m"]),
    coordinate_note="glTF is Y-up: gltf(x,y,z) = blender(x, z, -y)",
)
with open(f"{OUT}/web/model_data.js", "w", encoding="utf-8") as f:
    f.write("window.EXCAVATOR_PARAMS=" + json.dumps(params, ensure_ascii=False) + ";\n")
    f.write("window.EXCAVATOR_GLB_BASE64=\"" + base64.b64encode(open(glb, "rb").read()).decode() + "\";\n")
print("WEB OK", os.path.getsize(glb), "bytes glb")
