# 시뮬레이션·시각화 구조 설계 (sim-visual-architect)

작성 2026-11-06. 기준 코드: `physics.py`(덩어리 무게중심 h·cx 모델 + 미끄러짐), `viz3d.py`(Plotly 3D, 3인칭 고정), `app.py`(Streamlit 1.67).
범위: 해커톤 2일. 과설계 금지. 판정은 physics 하나, 화면은 physics가 준 숫자만 그린다.

---

## 0. 지금 코드에서 바꿔야 할 것 (요약)

| 현재 | 문제 | 조치 |
|---|---|---|
| `physics.evaluate`가 미끄러짐(tanθ>μ)도 판정, `GROUND` 마찰표 | CLAUDE.md 제외 범위 위반 | 미끄러짐·μ·`GROUND` 삭제. 판정은 전복만 |
| 무게중심 = 장비 덩어리(h, cx) + 짐 1개 | 5개 구성요소·자세 조건 미충족 | `kinematics.py` 신설, physics는 5개 질점 합성 |
| 3인칭 카메라만, 배경 없음 | 절대 조건 1 미충족 | 렌더러 교체(아래 1절) |
| 평면 경사만 | 요철 변수 없음 | `terrain.py` 신설(3절) |
| `slope_rotation`이 viz3d 안에 있음 | 좌표 변환이 화면 모듈에 묶여 있음 | physics로 옮김(판정과 화면이 같은 R을 씀) |

`viz3d.py`의 "중력선이 월드에서 연직" 자체 검사는 그대로 살린다(4절의 핵심 일치 검사).

---

## 1. 구현 방식 비교와 추천

### 비교

| 기준 | (a) Plotly 유지 | (b) three.js + Streamlit iframe | (c) 기타: pydeck / stpyvista |
|---|---|---|---|
| 1인칭/3인칭 전환 | 흉내만 가능. `scene.camera`의 eye/center/up만 있고 FOV 조절 없음, eye는 데이터 정규화 좌표라 운전석 위치 맞추기 번거로움. 마우스로 돌리면 center 기준 궤도 회전이라 1인칭 느낌이 깨짐 [1][2] | `PerspectiveCamera` 두 대(운전석·외부)를 버튼으로 전환. FOV·near 평면 직접 지정. 외부는 `OrbitControls` | pydeck `FirstPersonView`는 있으나 지도 좌표 중심이라 기계 메시 다루기 불편. stpyvista는 VTK 의존성이 무거워 Cloud 빌드 위험 |
| 2D 배경판 | 공식 기능 없음. 투명 scene 배경 + `layout.images`(paper 좌표)를 뒤에 까는 방법은 **미확인**(스파이크 필요) | 캔버스 `alpha:true` + CSS `background-image`(완전 2D, 카메라와 무관) 또는 `scene.background` 텍스처. 둘 다 기본 기능 | 해당 없음 |
| 요철 지형 | `go.Surface`로 쉬움 | `PlaneGeometry` 정점 z 갱신, 160×160 격자 문제없음 | - |
| 성능 | 메시 수 적어 충분. 슬라이더마다 전체 figure 재전송 | 지형 2.5만 정점 수준이면 가벼움. 슬라이더마다 iframe 재생성되므로 three.js 파일은 **브라우저 캐시되는 정적 파일**로 받아야 함(인라인 2.1 MB를 매번 보내면 느림) | - |
| 2일 난이도 | 낮음(이미 동작) | 중간. JS 300줄 안팎. 팀에 웹 경험자 필요 | 높음 |
| 배포·오프라인 | 이미 Cloud 동작. 오프라인 OK | 정적 파일 서빙(`server.enableStaticServing=true`, `./static/` → `app/static/…`)이 저장소 파일이면 Cloud에서도 제공됨 [3]. CDN 없이 저장소에 three.js를 넣으면 로컬 오프라인 데모 가능. **Cloud에서 iframe 안 상대경로가 정적 파일을 찾는지는 미확인 → 스파이크 1번 항목** | stpyvista는 Cloud 미확인 |

참고 사실:
- three.js 최신 0.187.0은 `build/`에 min 파일이 없고 `three.module.js`(659 KB)가 `three.core.js`(1.47 MB)를 import한다. 두 파일을 함께 `static/`에 둔다. `OrbitControls.js`는 `'three'`를 import하므로 importmap으로 연결한다 [4].
- `st.components.v1.html`은 1.56부터 deprecated, 대체는 `st.iframe`(1.56 신규, URL 또는 raw HTML) [5][6]. 현재 고정 버전 1.67에서 둘 다 쓸 수 있는지 스파이크에서 확인하고, `st.iframe`이 되면 그쪽을 쓴다. `components.html`은 JS 실행·동일 출처 접근이 허용된 iframe이다 [5].
- 반환값이 필요 없게 설계한다: 카메라 전환은 iframe 안 버튼으로 처리해 Streamlit 재실행을 일으키지 않는다. 입력은 전부 Streamlit 사이드바.

### 추천

**(b) three.js + 정적 파일 서빙**을 주 렌더러로 한다. 절대 조건(2D 배경판, 1인칭/3인칭)을 기본 기능으로 맞출 수 있는 유일한 후보다.
단, **1일차 오전 11시 go/no-go 스파이크**로 Cloud에서 정적 파일 로딩을 확인하고, 실패하면 (a) Plotly로 후퇴한다(5절). Plotly 후퇴 시 1인칭은 "운전석 위치 eye + 붐 방향 center" 고정 시점으로 흉내, 배경은 앱 레이아웃에서 그림 위에 차트를 겹치는 수준으로 타협.

정적 파일 로딩이 Cloud에서 안 되면 2순위: jsDelivr CDN(온라인 전용, 오프라인 데모는 로컬 `streamlit run`으로). 3순위: 인라인(느리지만 동작).

---

## 2. 모듈 구조와 인터페이스

```
kinematics.py   자세 → 5개 구성요소 질점 위치, 링크 점, 운전석 시점   (numpy만)
terrain.py      경사+요철 높이맵(시드 고정), 접지 영역 국부 평면 적합 (numpy만)
physics.py      합성 CoG, 전복 판정, 한계 경사, 몬테카를로, evaluate() 단일 진입점
render.py       evaluate() 결과 dict → three.js용 JSON + HTML 문자열
static/         three.module.js, three.core.js, OrbitControls.js, scene.js, bg_*.jpg
app.py          Streamlit UI. physics.evaluate() 호출 → render.html() 표시
viz3d.py        Plotly 후퇴안. 같은 결과 dict를 받아 그린다(후퇴 시에만 유지)
```

의존 방향: `app → physics → (kinematics, terrain)`, `app → render`. render는 physics 함수를 호출하지 않고 **결과 dict만** 받는다.

좌표계(기존 유지): 장비 기준 x 앞, y 왼쪽, z 위, 원점 = 하부 주행체 접지면 중심. 월드 z = 연직 위.

### kinematics.py

```python
GEOM = dict(                    # 보정 노브. 출처 태그 필수
    boom_len=5.7, arm_len=2.9,  # [추정] CAT 320 붐 5.7 m·암 2.9 m 사양 — 사양서 원문 확인 전까지 추정
    bucket_len=1.4,             # [추정]
    boom_foot=(0.15, 0.3, 1.9), # 상부 회전체 기준 붐 풋 핀 (x, y, z) [추정]
    cab_eye=(0.6, 0.7, 2.9),    # 운전석 눈 위치 [추정]
    upper_cog=(-0.9, 0.0, 1.5), # 상부 회전체+카운터웨이트 질점 [추정]
    lower_cog=(0.0, 0.0, 0.45), # 하부 주행체 질점 [추정]
)
POSE_KEYS = ("swing", "boom", "arm", "bucket")   # deg

def link_points(pose: dict, geom=GEOM) -> np.ndarray:
    """(4,3) 장비 좌표: 붐 풋, 암 핀, 버킷 핀, 버킷 끝.
    붐각=수평 기준, 암각=붐 기준 상대, 버킷각=암 기준 상대. 선회 평면에서 2D 체인을 풀고 z축으로 swing 회전."""

def component_cogs(pose: dict, geom=GEOM) -> dict[str, np.ndarray]:
    """{'boom','arm','upper','lower','bucket'} → (3,) 장비 좌표 질점.
    붐·암·버킷 = 각 링크 중점(근사, ponytail: 실제 질량 분포는 반영 안 함). upper는 swing 회전, lower는 고정."""

def cab_view(pose: dict, geom=GEOM) -> tuple[np.ndarray, np.ndarray]:
    """(눈 위치, 바라보는 점) 장비 좌표. 1인칭 카메라용. 바라보는 방향 = 선회 방향 수평."""
```

### terrain.py

```python
def heightmap(size=30.0, n=121, slope_deg=0.0, slope_dir_deg=0.0,
              rough_amp=0.0, rough_wavelength=3.0, seed=0) -> dict:
    """{'x': (n,), 'y': (n,), 'z': (n,n) ndarray, 'seed': int}. 월드 좌표.
    z = 평면 경사 + 저주파 요철(무작위 위상 코사인 8개 합, 진폭 rough_amp m). 같은 seed → 같은 지형."""

def local_plane(tm: dict, x0: float, y0: float, yaw_deg: float, L: float, B: float) -> dict:
    """장비 접지 직사각형(L×B, yaw 회전) 안 격자점에 z = a·x + b·y + c 최소제곱 적합.
    반환 {'slope_deg', 'heading_deg'(장비 기준 오르막 방향), 'z0'(중심 높이), 'rms'(적합 잔차 m)}."""

def local_slope_samples(tm, yaw_deg, L, B, n=200, seed=0) -> np.ndarray:
    """작업 구역 안 무작위 위치 n곳의 local_plane 결과 (n,2)[slope, heading]. 몬테카를로 입력."""
```

### physics.py

```python
MASS = dict(boom=1800, arm=900, bucket=850, upper=10450, lower=8500)  # [추정] 합 22,500 kg = [공식] 운전중량에 맞춤. 배분은 보정 노브
L_TRACK, B_GAUGE = 3.65, 2.38                                          # [공식] CAT 320
NOISE = dict(slope_deg=1.0, heading_deg=5.0, mass_rel=0.05, payload_rel=0.10)  # [추정] 보정 노브
SAFE, CAUTION = 0.01, 0.05

def slope_rotation(slope_deg, heading_deg) -> np.ndarray:   # viz3d에서 이동. (3,3) 장비→월드
def combined_cog(cogs: dict, masses: dict, payload_kg=0.0) -> tuple[np.ndarray, float]:
    """Σ mᵢ rᵢ / Σ mᵢ. 적재 하중은 버킷 질점에 더한다. (r(3,), M_total)."""
def tip_margin(r, slope_deg, heading_deg, L=L_TRACK, B=B_GAUGE) -> tuple[px, py, margin]:
    """기존 cog_projection 식 유지: 중력 방향 투영점과 직사각형까지의 최소 여유[m]. 배열 브로드캐스트."""
def critical_slope(r, heading_deg, ...) -> float:            # 이분법, 기존 유지
def monte_carlo(state: dict, slope_samples: np.ndarray | None, n=5000, seed=0) -> dict:
    """{'p_tip', 'margin_p05'}. 요철이 있으면 slope_samples에서 뽑고, 없으면 NOISE 정규분포."""
def evaluate(state: dict) -> dict:                           # app·render가 부르는 유일한 함수
```

입력 `state` (app이 만든다):
```python
{"pose": {"swing": -90, "boom": 30, "arm": -60, "bucket": -30},
 "payload_kg": 1500, "masses": MASS, "g": 9.81,
 "terrain": {"slope_deg": 20, "slope_dir_deg": 0, "rough_amp": 0.15, "seed": 0},
 "machine_yaw_deg": 90, "camera": "third"}         # camera는 render만 읽음
```

출력 `result` (render·app이 읽는 전부, 월드 좌표 변환까지 physics가 끝낸다):
```python
{"parts": {"boom": {"pos_world": [x,y,z], "mass": 1800}, ...},   # 5개
 "links_world": [[x,y,z]]*4, "cab_world": {"eye": [...], "target": [...]},
 "cog_world": [x,y,z], "proj_world": [x,y,z],                    # 중력선 두 끝점
 "support_world": [[x,y,z]]*4,                                    # 접지 직사각형
 "R": 3x3 list, "origin_world": [x,y,z],
 "local": {"slope_deg", "heading_deg", "rms"},
 "margin_m": float, "tip": bool, "critical_slope_deg": float,
 "p_tip": float, "verdict": "안전|주의|위험",
 "stab_moment_kNm": M_total*g*margin/1000,
 "terrain": {"x": [...], "y": [...], "z": [[...]]}}               # render용, 소수 2자리로 줄여 JSON 크기 절약
```
render는 이 dict를 `json.dumps` 해서 `<script>const DATA=…</script>`로 넣고 `static/scene.js`가 그린다. 장비 박스 형상(트랙·차체 크기)은 render 쪽 근사지만 **위치·회전은 전부 result에서** 온다.

```python
# render.py
def html(result: dict, camera: str = "third", bg: str = "bg_site.jpg", height=600) -> str
# app.py
st.iframe(render.html(res, cam), height=620)   # 1.67에서 안 되면 components.html
```

### 중력 g에 대해 (정직하게)
정적 전복 판정에서 g는 투영점 위치를 바꾸지 않는다(모든 항에 g가 곱해져 약분됨). 따라서 g를 바꿔도 전복 여부·한계 경사는 같고, 바뀌는 것은 복원 모멘트 크기(`stab_moment_kNm`)뿐이다. 화면에 이 점을 표시한다. g가 판정에 영향을 주게 하려면 수평 가속도 a(선회 정지·주행 흔들림, [추정] 보정 노브)를 넣어 유효 중력 방향을 atan(a/g)만큼 기울이는 한 줄을 추가할 수 있다. 넣을지는 매니저 결정(동역학 확장이라 범위 경계).

---

## 3. 요철 지형: 높이맵 → 국부 평면 적합

방식: `heightmap`으로 경사면 + 저주파 요철을 만들고, 장비 접지 직사각형 안 격자점(0.25 m 격자면 약 15×10=150점)에 `np.linalg.lstsq`로 평면을 적합해 국부 경사·방향을 얻는다. 법선 n = (−a, −b, 1)/‖·‖ → slope = acos(n_z), 오르막 방향 = atan2(b, a) − 장비 yaw.

타당성:
- **맞는 점**: 트랙은 길고 단단해 파장이 트랙 길이(3.65 m)보다 짧은 요철은 평균화된다. 최소제곱 평면은 이 평균화를 단순하게 표현한다. 요철 파장을 3 m 이상으로 두면 "트랙 아래 국부 기울기의 분산"(CLAUDE.md 변수 정의)과 그대로 맞는다.
- **한계(ponytail)**: 실제 강체 트랙은 가장 높은 점들에 얹히므로(볼록 껍질 접촉) 최소제곱 평면보다 더 기울 수 있고, 지지 직사각형도 줄어든다. 최소제곱은 이를 과소평가한다. 개선안: 네 모서리 근방 최대 높이로 평면을 잡는 "상위점 평면"(코드 5줄). 해커톤에선 최소제곱 + 적합 잔차 `rms`를 화면에 표시하고, rms가 크면 "요철이 커서 모델 신뢰도 낮음" 경고.
- 침하 제외 조건과 충돌 없음: 지면은 강체로 보고 높이만 쓴다.
- 몬테카를로: 요철을 매번 새로 만들지 않고, 같은 지형에서 장비 위치를 무작위로 n곳 옮겨 국부 평면 분포를 얻는다(`local_slope_samples`). "이 현장 아무 데나 세웠을 때 전복 확률"이라는 설명이 된다. 200곳 × 150점 lstsq는 수십 ms.
- 성능: 121×121 높이맵 생성·JSON 전달 모두 가볍다. 요철 생성에 scipy 불필요(코사인 합).
- 시각적 주의: 렌더에서 장비는 적합 평면(R, z0)에 놓이므로 요철 봉우리가 트랙을 뚫고 보일 수 있다. 정상 동작이며 캡션으로 설명.

---

## 4. 테스트 (각 모듈 `python 모듈.py` assert)

**kinematics.py**
- 링크 길이 보존: 임의 자세 20개에서 ‖p1−p0‖=boom_len 등.
- 붐 0°·암 0°·버킷 0°·선회 0° → 버킷 끝 x = 풋 x + 세 링크 합, z = 풋 z (해석해).
- 선회 180° → 붐·암·버킷·상부 질점의 x, y 부호 반전, z 동일. 하부 질점 불변.
- cab_view 바라보는 방향이 선회 방향과 같음.

**terrain.py**
- 같은 seed → 동일 배열, 다른 seed → 다른 배열.
- rough_amp=0이면 local_plane이 입력 slope_deg·방향을 1e-9 안에서 복원(장비 yaw 여러 개).
- rough_amp>0일 때 local_slope_samples의 표준편차 > 0이고 진폭에 따라 증가.

**physics.py** (기존 검증 1·2·4·5 이식, 미끄러짐 검증 3은 삭제)
- 합성 CoG 손계산 일치(질점 2개 예제), 질량 합 = 22,500 kg.
- 무게중심이 축 위에 있을 때 옆경사 한계각 = atan((B/2)/z_c), 앞경사 = atan((L/2 − x_c)/z_c).
- 붐을 내리막 쪽으로 돌리면 한계각 감소, 오르막 쪽이면 증가.
- g=9.81과 g=1.62에서 tip·critical_slope 동일, stab_moment는 g에 비례.
- 몬테카를로 확률이 경사에 대해 단조 증가, seed 고정 시 재현.

**시각-물리 일치 (render.py 자체 검사, 브라우저 없이 dict로 검사)**
- 중력선 연직: `cog_world − proj_world`의 x, y 성분 = 0, z > 0 (기존 viz3d 검사 이식).
- `tip == (proj가 support_world 다각형 밖)`: 월드에서 점-다각형 판정을 다시 해 physics 판정과 일치.
- `support_world` 네 점과 `proj_world`가 같은 평면 위(적합 평면 법선과 직교).
- render가 JSON에 넣는 CoG·투영점·지지면 좌표가 result 값과 바이트 단위로 같음(가공 금지 확인).
- 1인칭 카메라 eye가 상부 회전체 박스 안/위에 있고 target이 선회 방향.
- 수동 1회: 브라우저에서 1인칭/3인칭 전환, 배경 표시, 경사 슬라이더를 한계각 앞뒤로 움직여 색 전환 확인(스크린샷 2장 발표 자료로 재사용).

---

## 5. 2일 작업 분해

역할 가정: 메카트로닉스 R1·R2, AI콘텐츠 C1·C2.

| 시간 | R1 (기구학·물리) | R2 (지형·검증) | C1 (three.js 렌더) | C2 (배경·UI·발표) |
|---|---|---|---|---|
| D1 09–11 | 각 정의·GEOM/MASS 출처 정리 | terrain.heightmap + 자체 검사 | **스파이크**: static/에 three.js 두 파일 + 큐브 1개를 `st.iframe`으로 띄워 **Cloud에 배포해 확인** | 현장 배경 이미지 2–3장 제작(직접 생성, 라이선스 문제없는 것), 화면 스케치 |
| D1 11:00 | **go/no-go**: 스파이크 성공 → (b). 실패 → CDN 시도 30분, 그래도 실패면 (a) Plotly | | | |
| D1 11–13 | kinematics.py + 검사 | local_plane + 검사 | 지형 메시·장비 박스·중력선을 고정 JSON으로 그리기 | app.py 사이드바(자세 4개·하중·경사·요철·g) |
| D1 14–18 | physics 5질점 개편, 미끄러짐 삭제, evaluate() | local_slope_samples + monte_carlo 연결 | 1인칭/3인칭 전환, CSS 배경, 위험 색 | render.html ↔ app 연결 |
| D1 18–20 | **통합**: 실제 evaluate() 결과로 화면 표시, Cloud 재배포 | | | |
| D2 09–12 | ISO 10567 인양 능력표 대비 확인(Validation) 표 | 시각-물리 일치 검사 render 자체 검사 | 버킷 하중 표시, 지지면·투영점 강조 | 위험 지도(기존 heatmap) 자세 기준으로 갱신 |
| D2 13–16 | 보정 노브 조정, 결과 표 | 전체 assert 통과·버그 수정 | 성능·모바일 확인 | 발표 자료·데모 시나리오 3개 |
| D2 16–18 | **동결**. 리허설, Cloud 최종 배포, 오프라인 로컬 실행 확인 | | | |

순서 원칙: 물리(R1·R2)는 화면과 독립으로 먼저 assert를 통과시키고, 렌더(C1)는 D1 오후까지 **고정 JSON 샘플**로 개발해 서로 기다리지 않는다. 계약은 2절의 `result` dict 하나.

### 위험과 대안

| 위험 | 신호 | 대안 |
|---|---|---|
| Cloud iframe 안에서 `app/static/` 경로 로딩 실패 (가장 큼) | 스파이크에서 콘솔 404/모듈 오류 | jsDelivr CDN → 인라인 → Plotly 후퇴 |
| `st.iframe`/`components.html` 동작 차이(1.67) | 스파이크에서 빈 화면 | 다른 쪽 API 사용. 둘 다 안 되면 Plotly |
| 슬라이더마다 iframe 재생성으로 깜빡임·카메라 초기화 | 데모 중 끊김 | 카메라 모드는 state로 넘겨 유지. 정적 파일 캐시로 로딩 단축 |
| 구성요소 질량·치수 근거 부족 | 심사 질문 | 전부 `[추정]` 태그 + 보정 노브 + 운전중량 합만 `[공식]`으로 맞춤. Validation 표에서 오차 공개 |
| g가 판정에 영향 없음 | "중력 바꿔도 결과 같다" 질문 | 2절 설명을 화면 캡션에. 필요 시 수평 가속도 한 줄 추가 |
| JS 담당 막힘 | D1 18시 통합 실패 | D2 오전까지 Plotly 화면으로 데모 가능 상태 유지(viz3d를 result dict로 먼저 맞춰 둠) |

---

## 근거 URL

1. Plotly 3D 카메라(eye/center/up, FOV 항목 없음): https://plotly.com/python/3d-camera-controls/
2. Plotly camera projection(perspective/orthographic): https://plotly.com/python-api-reference/generated/plotly.graph_objects.layout.scene.camera.html
3. Streamlit 정적 파일 서빙(`enableStaticServing`, `app/static/`, Cloud는 저장소 파일 제공): https://docs.streamlit.io/develop/concepts/configuration/serving-static-files
4. three.js 0.187.0 build 파일 목록·크기(min 없음, module.js 659 KB + core.js 1.47 MB): https://unpkg.com/three@0.187.0/build/?meta
5. `st.components.v1.html`(iframe, JS 실행·동일 출처, 1.56 deprecated → `st.iframe`): https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v1.html
6. Streamlit 2026 릴리스 노트(1.56 `st.iframe` 추가): https://docs.streamlit.io/develop/quick-reference/release-notes/2026

미확인 항목: Plotly 투명 배경 + `layout.images` 겹치기, Cloud에서 iframe 상대경로 정적 파일 로딩, `st.iframe`의 raw HTML 높이·스크롤 인자, CAT 320 붐·암 길이 원문.

---

## 매니저에게

**추천안 3줄**
1. 렌더러는 three.js(저장소 `static/`에 넣고 Streamlit 정적 서빙 + `st.iframe`)로 바꿔 2D 배경판·1인칭/3인칭을 기본 기능으로 맞추고, Plotly(viz3d)는 후퇴안으로 남긴다.
2. `kinematics → terrain → physics.evaluate()`가 월드 좌표까지 다 계산한 `result` dict 하나를 계약으로 두고, 화면은 그 dict만 그린다. 미끄러짐 코드는 삭제한다.
3. 요철은 저주파 높이맵 + 접지 영역 최소제곱 평면으로 국부 경사를 구하고, 위치를 옮겨 가며 뽑은 분포를 몬테카를로에 넣는다.

**가장 큰 위험 1개**: Streamlit Community Cloud의 iframe 안에서 `app/static/` three.js 파일이 실제로 로드되는지 확인되지 않았다. 1일차 11시까지 Cloud 배포 스파이크로 판정하고, 실패하면 CDN → Plotly 순으로 바로 후퇴한다.
