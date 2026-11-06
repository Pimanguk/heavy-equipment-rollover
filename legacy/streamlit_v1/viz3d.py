"""경사면 위 장비 3D 장면. 장비 기준 좌표로 그린 뒤 경사만큼 회전해 월드 좌표(z = 연직 위)로 보낸다.
장비 형상 비율은 시각화용 근사이며 판정 계산에는 쓰이지 않는다(판정은 physics.py)."""
import numpy as np
import plotly.graph_objects as go

from physics import cog_projection


def slope_rotation(slope_deg, heading_deg):
    """장비 좌표 → 월드 좌표 회전행렬. 오르막 방향 u가 위로 들리도록 축 a = z × u 기준 회전."""
    hd = np.radians(heading_deg)
    a = np.array([-np.sin(hd), np.cos(hd), 0.0])
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    phi = -np.radians(slope_deg)  # a×u = -z 이므로 음의 회전이 u를 들어 올림
    return np.eye(3) + np.sin(phi) * K + (1 - np.cos(phi)) * K @ K


def _box(R, center, size, yaw_deg, color, name, opacity=1.0):
    d = np.array(size) / 2
    v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) * d
    c, s = np.cos(np.radians(yaw_deg)), np.sin(np.radians(yaw_deg))
    v = (v @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]).T + center) @ R.T
    return go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], alphahull=0, color=color,
                     opacity=opacity, name=name, hoverinfo="name", flatshading=True)


def _line(R, pts, color, name, width=6, dash=None):
    p = np.asarray(pts, float) @ R.T
    return go.Scatter3d(x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="lines", name=name,
                        line=dict(color=color, width=width, dash=dash), hoverinfo="name")


def scene(eq, load, reach, load_h, swing_deg, slope_deg, heading_deg, tipping):
    R = slope_rotation(slope_deg, heading_deg)
    L, B, h = eq["L"], eq["B"], eq["h"]
    xc, yc, zc, px, py = (float(v) for v in cog_projection(eq, load, reach, load_h, swing_deg, slope_deg, heading_deg))
    sw = np.radians(swing_deg)
    tw, th = 0.25 * B, 0.6 * h  # 트랙 폭·높이 (시각화 근사)
    hz = th + 0.4 * h           # 상부 선회체 중심 높이
    tip_pt = np.array([reach * np.cos(sw), reach * np.sin(sw), load_h])
    pivot = np.array([0.4 * np.cos(sw), 0.4 * np.sin(sw), hz + 0.3 * h])
    elbow = (pivot + tip_pt) / 2 + np.array([0, 0, 0.5 * h + 0.15 * reach])

    g = 8.0  # 경사면 크기
    plane = np.array([[-g, -g, 0], [g, -g, 0], [g, g, 0], [-g, g, 0]]) @ R.T
    rect_c = "#d62728" if tipping else "#2ca02c"
    up = np.array([np.cos(np.radians(heading_deg)), np.sin(np.radians(heading_deg)), 0])

    traces = [
        go.Mesh3d(x=plane[:, 0], y=plane[:, 1], z=plane[:, 2], i=[0, 0], j=[1, 2], k=[2, 3],
                  color="#c8b48a", opacity=0.55, name="경사면", hoverinfo="name"),
        _box(R, [0, B / 2, th / 2], [L, tw, th], 0, "#444", "트랙(좌)", 0.45),
        _box(R, [0, -B / 2, th / 2], [L, tw, th], 0, "#444", "트랙(우)", 0.45),
        _box(R, [-0.2 * np.cos(sw), -0.2 * np.sin(sw), hz], [0.8 * L, 0.9 * B, 0.8 * h], swing_deg, "#f2b400", "상부 선회체", 0.35),
        _line(R, [pivot, elbow, tip_pt], "#f2b400", "붐·암", width=12),
        _line(R, [[x, y, 0.02] for x, y in [(-L/2, -B/2), (L/2, -B/2), (L/2, B/2), (-L/2, B/2), (-L/2, -B/2)]],
              rect_c, "지지면(접지 영역)", width=8),
        _line(R, [[xc, yc, zc], [px, py, 0.02]], "#d62728" if tipping else "#1f77b4", "중력선(무게중심→바닥)", width=5, dash="dash"),
        _line(R, [[0, 0, 0.05], list(up * 2.5 + [0, 0, 0.05])], "#7f7f7f", "오르막 방향", width=4),
    ]
    if load > 0:
        traces.append(_box(R, tip_pt - [0, 0, 0.3], [0.6, 0.6, 0.6], swing_deg, "#8c564b", f"짐 {load:.0f} kg"))
    pts = np.array([[xc, yc, zc], [px, py, 0.02]]) @ R.T
    traces.append(go.Scatter3d(x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], mode="markers+text",
                               marker=dict(size=[8, 6], color=["black", rect_c]), text=["무게중심", "투영점"],
                               textposition="top center", name="무게중심", hoverinfo="text"))

    # 카메라: 경사를 옆에서 보도록 월드 오르막 방향에 수직인 수평 방향에서 바라봄
    upw = R @ up
    side = np.array([-upw[1], upw[0]]) / max(np.hypot(upw[0], upw[1]), 1e-9) * 1.9
    side = side @ [[0.94, -0.34], [0.34, 0.94]]  # 약간 비스듬히(20°)
    fig = go.Figure(traces)
    fig.update_layout(
        height=560, margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
        legend=dict(x=0, y=1, bgcolor="rgba(255,255,255,0.7)"),
        scene=dict(aspectmode="data", xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                   camera=dict(eye=dict(x=side[0], y=side[1], z=0.75))),
    )
    return fig


if __name__ == "__main__":
    from physics import EQUIPMENT
    eq = EQUIPMENT["CAT 320 (굴착기 20t급)"]
    for slope, hd in [(0, 0), (20, 90), (30, 45), (25, 180)]:
        R = slope_rotation(slope, hd)
        assert np.allclose(R @ R.T, np.eye(3))
        # 오르막 방향은 위로, 경사면 법선은 연직에서 slope만큼 기운다
        u = R @ [np.cos(np.radians(hd)), np.sin(np.radians(hd)), 0]
        assert np.isclose(u[2], np.sin(np.radians(slope)))
        assert np.isclose((R @ [0, 0, 1])[2], np.cos(np.radians(slope)))
        # 핵심: physics의 투영점은 월드에서 무게중심 바로 아래(중력선이 연직)
        xc, yc, zc, px, py = cog_projection(eq, 1500, 6, 1, -90, slope, hd)
        d = R @ np.array([xc - px, yc - py, zc])
        assert np.allclose(d[:2], 0, atol=1e-9) and d[2] > 0
    scene(eq, 1500, 6, 1, -90, 30, 90, True)
    print("all checks passed")
