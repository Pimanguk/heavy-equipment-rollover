"""중장비 전복 위험 판정 서비스 — 실행: streamlit run app.py"""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from physics import EQUIPMENT, GROUND, critical_slope, monte_carlo, verdict
from viz3d import scene

st.set_page_config(page_title="중장비 전복 위험 판정", layout="wide")
st.title("중장비 경사지 작업 전 전복 위험 판정")
st.caption("작업 전에 장비·하중·경사·노면을 입력하면 전복과 미끄러짐 확률을 계산합니다.")

with st.sidebar:
    st.header("작업 조건")
    eq = dict(EQUIPMENT[st.selectbox("장비", list(EQUIPMENT))])
    with st.expander("제원 직접 수정"):
        eq["M"] = st.number_input("장비 중량 kg", value=float(eq["M"]), step=500.0)
        eq["L"] = st.number_input("접지 길이 L m", value=eq["L"], step=0.05)
        eq["B"] = st.number_input("궤간 B m", value=eq["B"], step=0.05)
        eq["h"] = st.number_input("무게중심 높이 m", value=eq["h"], step=0.05)
        eq["cx"] = st.number_input("무게중심 앞뒤 위치 m", value=eq["cx"], step=0.05)
    slope = st.slider("경사각 °", 0.0, 45.0, 20.0, 0.5)
    heading = st.slider("오르막 방향 ° (0 정면 오르막 · 90 옆경사 · 180 후진 오르막)", 0, 180, 90, 5)
    mu = GROUND[st.selectbox("노면", list(GROUND))]
    st.subheader("들고 있는 짐")
    load = st.number_input("하중 kg", 0.0, 10000.0, 1500.0, 100.0)
    reach = st.slider("장비 중심에서 짐까지 수평거리 m", 0.0, 10.0, 6.0, 0.5)
    load_h = st.slider("짐 높이 m", 0.0, 6.0, 1.0, 0.5)
    swing = st.slider("붐 방향 ° (0 앞 · 90 왼쪽 · -90 오른쪽)", -180, 180, -90, 15)

r = monte_carlo(eq, load, reach, load_h, swing, slope, heading, mu)
crit = critical_slope(eq, load, reach, load_h, swing, heading)
slide_lim = float(np.degrees(np.arctan(mu)))
v = verdict(r["p_any"])

{"안전": st.success, "주의": st.warning, "위험": st.error}[v](
    f"판정: **{v}** · 전체 위험 확률 {r['p_any']:.1%}")
c = st.columns(4)
c[0].metric("전복 확률", f"{r['p_tip']:.1%}")
c[1].metric("미끄러짐 확률", f"{r['p_slide']:.1%}")
c[2].metric("전복 한계 경사", f"{crit:.1f}°", f"{crit - slope:+.1f}° 여유")
c[3].metric("미끄러짐 한계 경사", f"{slide_lim:.1f}°", f"{slide_lim - slope:+.1f}° 여유")

st.subheader("3D로 보기")
st.plotly_chart(scene(eq, load, reach, load_h, swing, slope, heading, tipping=slope > crit), width="stretch")
st.caption("점선(중력선)이 지지면 사각형 안에 떨어지면 안정, 밖으로 나가면 전복입니다. 마우스로 돌리고 휠로 확대하세요. "
           "장비 모양은 시각화용 근사입니다.")


@st.cache_data
def risk_map(eq_items, load, reach, load_h, swing, mu):
    e = dict(eq_items)
    rows = [(h, s, monte_carlo(e, load, reach, load_h, swing, s, h, mu, n=800)["p_any"])
            for h in range(0, 181, 10) for s in range(0, 46)]
    return pd.DataFrame(rows, columns=["오르막 방향°", "경사각°", "위험확률"])


st.subheader("어느 방향·경사까지 안전한가")
df = risk_map(tuple(eq.items()), load, reach, load_h, swing, mu)
heat = alt.Chart(df).mark_rect().encode(
    x="경사각°:O", y="오르막 방향°:O",
    color=alt.Color("위험확률:Q", scale=alt.Scale(scheme="redyellowgreen", reverse=True, domain=[0, 1])),
    tooltip=["오르막 방향°", "경사각°", alt.Tooltip("위험확률:Q", format=".1%")],
)
now = alt.Chart(pd.DataFrame({"경사각°": [round(slope)], "오르막 방향°": [round(heading / 10) * 10]})).mark_point(
    shape="cross", size=300, color="black", filled=True).encode(x="경사각°:O", y="오르막 방향°:O")
st.altair_chart(heat + now, width="stretch")
st.caption("검은 십자 = 현재 조건. 불확실성(경사 측정 ±2°, 마찰 ±15%, 하중 ±10% 등)을 반영한 몬테카를로 결과입니다.")
