# 6페이지용 "위험 단계" 그림(위에서 본 트랙 + 받치는 영역 + 무게가 실리는 점) 생성
import math, os
from PIL import Image, ImageDraw, ImageFont
OUT = os.path.dirname(os.path.abspath(__file__))
B = lambda s: ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', s)
R = lambda s: ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', s)
INK = (40, 40, 40, 255)
cards = [('안전', (46, 139, 87), 0.0, '점이 안쪽 깊숙이', '넉넉히 버팁니다'),
         ('주의', (217, 119, 6), 0.78, '점이 가장자리 가까이', '경계까지 0.35 m 이내(임시)'),
         ('전복 위험', (192, 57, 43), 1.5, '점이 영역 밖으로', '넘어집니다')]
CW, CH, G = 520, 600, 40
img = Image.new('RGBA', (CW * 3 + G * 2, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(img)

def dash(p, q):
    n = int(math.dist(p, q) // 16)
    for i in range(0, n, 2):
        a = (p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n)
        b = (p[0] + (q[0] - p[0]) * (i + 1) / n, p[1] + (q[1] - p[1]) * (i + 1) / n)
        d.line([a, b], fill=(46, 139, 87, 255), width=4)

def center_text(cx, y, s, f):
    tb = d.textbbox((0, 0), s, font=f); d.text((cx - (tb[2] - tb[0]) // 2, y - tb[1]), s, font=f, fill=INK)

for k, (t, c, px, l1, l2) in enumerate(cards):
    x0 = k * (CW + G); cx, cy, hw, hh = x0 + CW // 2, 300, 130, 110
    d.rounded_rectangle([x0, 0, x0 + CW, CH], radius=28, fill=(255, 255, 255, 255), outline=c + (255,), width=6)
    tb = d.textbbox((0, 0), t, font=B(44)); w = tb[2] - tb[0]
    d.rounded_rectangle([cx - w // 2 - 30, 28, cx + w // 2 + 30, 108], radius=20, fill=c + (255,))
    d.text((cx - w // 2, 48 - tb[1]), t, font=B(44), fill=(255, 255, 255, 255))
    d.rectangle([cx - hw, cy - hh, cx + hw, cy + hh], fill=(232, 245, 233, 255))
    for sx in (-1, 1):  # 트랙(가운데 선 = 받치는 영역 경계)
        tx = cx + sx * hw
        d.rectangle([tx - 18, cy - hh, tx + 18, cy + hh], fill=(70, 70, 70, 255))
        for yy in range(cy - hh, cy + hh, 18): d.line([(tx - 18, yy), (tx + 18, yy)], fill=(110, 110, 110, 255), width=2)
    pts = [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    for i in range(4): dash(pts[i], pts[(i + 1) % 4])
    X, Y, r = cx + px * hw, cy, 22
    d.ellipse([X - r - 6, Y - r - 6, X + r + 6, Y + r + 6], fill=(255, 255, 255, 255))
    d.ellipse([X - r, Y - r, X + r, Y + r], fill=c + (255,), outline=INK, width=4)
    d.line([(X - 10, Y), (X + 10, Y)], fill=(255, 255, 255, 255), width=4); d.line([(X, Y - 10), (X, Y + 10)], fill=(255, 255, 255, 255), width=4)
    center_text(cx, 452, l1, B(34)); center_text(cx, 508, l2, R(30))
img.save(os.path.join(OUT, '06_위험단계_3카드.png'))

L = Image.new('RGBA', (CW * 3 + G * 2, 90), (0, 0, 0, 0)); e = ImageDraw.Draw(L); x = 10
for sw, txt in [('track', '트랙(땅에 닿는 부분)'), ('area', '장비를 받치는 영역'), ('dot', '무게가 실리는 점')]:
    if sw == 'track': e.rectangle([x, 25, x + 30, 65], fill=(70, 70, 70, 255))
    elif sw == 'area': e.rectangle([x, 25, x + 40, 65], fill=(232, 245, 233, 255), outline=(46, 139, 87, 255), width=3)
    else: e.ellipse([x, 25, x + 40, 65], fill=(60, 60, 60, 255))
    e.text((x + 56, 22), txt, font=R(32), fill=INK); x += 56 + e.textbbox((0, 0), txt, font=R(32))[2] + 60
L.save(os.path.join(OUT, '06_위험단계_범례.png'))
