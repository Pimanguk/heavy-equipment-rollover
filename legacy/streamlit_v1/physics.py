"""중장비 경사지 전복·미끄러짐 판정 — 정적 안정성 모델 + 몬테카를로.

좌표계(장비 기준): x 앞, y 왼쪽, z 위. 지지 다각형 = 접지 길이 L × 궤간 B 직사각형.
heading = 장비 정면 기준 '오르막 방향' 각도 (0 = 오르막을 바라봄, 90 = 오르막이 왼쪽 = 옆경사).
무게중심을 중력 방향으로 경사면에 투영해 지지 다각형 밖이면 전복, tanθ > μ 이면 미끄러짐.
"""
import numpy as np

# 제원. CAT 320: M·L·B는 Cat 공식 사양서(롱 언더캐리지, 22,500 kg / 롤러 중심거리 3,650 mm / 궤간 2,380 mm).
# h(무게중심 높이)·cx(앞뒤 위치)는 사양서에 없는 추정값 — 보정 노브. 나머지 장비는 일반 범위 추정값.
EQUIPMENT = {
    "CAT 320 (굴착기 20t급)": dict(M=22500, L=3.65, B=2.38, h=1.20, cx=-0.30),
    "미니굴착기 3t급": dict(M=3000, L=1.60, B=1.30, h=0.60, cx=-0.10),
    "휠로더 15t급": dict(M=15000, L=3.00, B=2.20, h=1.30, cx=0.00),
}

# 트랙 견인계수 (Caterpillar Performance Handbook 표 기준값 — 원문 확인 권장)
GROUND = {
    "단단한 흙(건조)": 0.90, "점토(젖음)": 0.70, "느슨한 흙": 0.60, "채석장": 0.55,
    "자갈길": 0.50, "콘크리트": 0.45, "모래(건조)": 0.30, "다져진 눈": 0.27, "얼음": 0.12,
}

# 불확실성(보정 노브): 경사 측정+지면 요철+동적 흔들림, 방향 오차, 마찰·하중·무게중심 편차
NOISE = dict(slope_deg=2.0, heading_deg=5.0, mu_rel=0.15, load_rel=0.10, h_rel=0.05)
# 판정 기준(보정 노브): 위험 확률 < SAFE 안전, < CAUTION 주의, 그 이상 위험
SAFE, CAUTION = 0.01, 0.05


def cog_projection(eq, load, reach, load_h, swing_deg, slope_deg, heading_deg):
    """합성 무게중심 (xc, yc, zc)와 중력 방향으로 경사면에 내린 투영점 (px, py)."""
    M, h, cx = eq["M"], eq["h"], eq["cx"]
    sw, hd = np.radians(swing_deg), np.radians(heading_deg)
    t = np.tan(np.radians(slope_deg))
    Mt = M + load
    xc = (M * cx + load * reach * np.cos(sw)) / Mt
    yc = load * reach * np.sin(sw) / Mt
    zc = (M * h + load * load_h) / Mt
    return xc, yc, zc, xc - zc * t * np.cos(hd), yc - zc * t * np.sin(hd)  # 내리막 쪽으로 이동


def evaluate(eq, load, reach, load_h, swing_deg, slope_deg, heading_deg, mu):
    """배열 브로드캐스트 가능. (전복여부, 미끄러짐여부, 안정여유[m]) 반환."""
    *_, px, py = cog_projection(eq, load, reach, load_h, swing_deg, slope_deg, heading_deg)
    margin = np.minimum(eq["L"] / 2 - np.abs(px), eq["B"] / 2 - np.abs(py))
    return margin < 0, np.tan(np.radians(slope_deg)) > mu, margin


def critical_slope(eq, load, reach, load_h, swing_deg, heading_deg):
    """결정론적 전복 한계 경사각[°] (이분법). 평지에서 이미 넘어가면 0."""
    lo, hi = 0.0, 89.0
    if evaluate(eq, load, reach, load_h, swing_deg, lo, heading_deg, 1)[2] < 0:
        return 0.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if evaluate(eq, load, reach, load_h, swing_deg, mid, heading_deg, 1)[2] < 0:
            hi = mid
        else:
            lo = mid
    return lo


def monte_carlo(eq, load, reach, load_h, swing_deg, slope_deg, heading_deg, mu, n=5000, seed=0):
    """입력 불확실성을 반영한 전복·미끄러짐·전체 위험 확률."""
    r = np.random.default_rng(seed)
    e = dict(eq, h=eq["h"] * r.normal(1, NOISE["h_rel"], n))
    tip, slide, _ = evaluate(
        e,
        np.clip(load * r.normal(1, NOISE["load_rel"], n), 0, None),
        reach, load_h, swing_deg,
        np.clip(slope_deg + r.normal(0, NOISE["slope_deg"], n), 0, 89),
        heading_deg + r.normal(0, NOISE["heading_deg"], n),
        np.clip(mu * r.normal(1, NOISE["mu_rel"], n), 0.01, None),
    )
    return dict(p_tip=tip.mean(), p_slide=slide.mean(), p_any=(tip | slide).mean())


def verdict(p):
    return "안전" if p < SAFE else "주의" if p < CAUTION else "위험"


if __name__ == "__main__":
    eq = dict(M=10000, L=3.0, B=2.0, h=1.0, cx=0.0)
    # 검증 1: 무부하·무게중심 중앙·옆경사 → 해석해 atan((B/2)/h) = 45°
    assert abs(critical_slope(eq, 0, 0, 0, 0, 90) - 45.0) < 1e-6
    # 검증 2: 정면 경사 → atan((L/2)/h)
    assert abs(critical_slope(eq, 0, 0, 0, 0, 0) - np.degrees(np.arctan(1.5))) < 1e-6
    # 검증 3: 미끄러짐 경계 tanθ = μ (μ=0.5 → 26.57°)
    assert not evaluate(eq, 0, 0, 0, 0, 26.0, 0, 0.5)[1] and evaluate(eq, 0, 0, 0, 0, 26.7, 0, 0.5)[1]
    # 검증 4: 짐을 내리막 쪽(오른쪽, swing -90)에 들면 한계각 감소, 오르막 쪽이면 증가
    base = critical_slope(eq, 0, 0, 0, 0, 90)
    assert critical_slope(eq, 2000, 4, 1, -90, 90) < base < critical_slope(eq, 2000, 4, 1, 90, 90)
    # 검증 5: 확률은 경사가 커질수록 증가
    ps = [monte_carlo(eq, 0, 0, 0, 0, s, 90, 0.9)["p_any"] for s in (20, 40, 50)]
    assert ps[0] <= ps[1] <= ps[2] and ps[2] > 0.5, ps
    print("all checks passed")
