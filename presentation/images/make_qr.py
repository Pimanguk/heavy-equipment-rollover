# 시뮬레이터·휴대폰 대본 QR 이미지 생성 (주소가 바뀌면 SITE만 고치고 다시 실행)
import os, qrcode
from PIL import Image, ImageDraw, ImageFont
SITE = 'https://pimanguk.github.io/heavy-equipment-rollover/'
HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda f: os.path.join(HERE, f)

def qr(url, size):
    q = qrcode.QRCode(border=4, error_correction=qrcode.constants.ERROR_CORRECT_M); q.add_data(url); q.make()
    return q.make_image().convert('L').resize((size, size), Image.NEAREST)

base = qr(SITE, 1060)
base.convert('RGB').save(P('qr_simulator.png'))
for name, rgb in (('qr_simulator_투명_검정.png', (0, 0, 0)), ('qr_simulator_투명_흰색.png', (255, 255, 255))):
    a = base.point(lambda v: 255 if v < 128 else 0)          # 검은 칸만 남기고 배경은 투명
    im = Image.new('RGBA', base.size, rgb + (0,)); im.putalpha(a); im.save(P(name))

card = Image.new('RGB', (1140, 1280), (255, 194, 14)); d = ImageDraw.Draw(card)
card.paste(base.convert('RGB'), (40, 40))
B = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 60); R = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 30)
for txt, f, cy in (('시뮬레이터 직접 해 보기', B, 1160), (SITE.replace('https://', '').rstrip('/'), R, 1232)):
    l, t, r, b = d.textbbox((0, 0), txt, font=f); d.text(((1140 - (r - l)) // 2 - l, cy - (b + t) // 2), txt, font=f, fill=(25, 25, 25))
card.save(P('qr_simulator_card.png'))

qr(SITE + 'web/script.html', 492).save(P('qr_발표대본_폰.png'))

if __name__ == '__main__':
    import zxingcpp                                            # 생성한 QR이 실제로 새 주소로 읽히는지 확인
    for f, want in (('qr_simulator.png', SITE), ('qr_simulator_card.png', SITE), ('qr_simulator_투명_검정.png', SITE),
                    ('qr_simulator_투명_흰색.png', SITE), ('qr_발표대본_폰.png', SITE + 'web/script.html')):
        im = Image.open(P(f))
        if im.mode == 'RGBA':                                  # 투명 QR은 대비되는 배경에 얹어서 읽는다
            bg = Image.new('RGBA', im.size, (255, 255, 255, 255) if '검정' in f else (0, 0, 0, 255)); bg.alpha_composite(im); im = bg
        got = zxingcpp.read_barcodes(im)[0].text
        assert got == want, (f, got); print('OK', f, got)
