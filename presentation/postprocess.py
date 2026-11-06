"""pptx 후처리: (1) 한글이 단어 중간에서 줄바꿈되지 않게 문단마다 eaLnBrk="0"
(2) ZIP 안의 폴더 항목 제거(클라우드 열기 오류 방지). 사용: python postprocess.py deck.pptx"""
import re, sys, zipfile, os, tempfile, shutil

TARGET = re.compile(r"ppt/(slides|slideLayouts|slideMasters)/[^/]+\.xml$")

def fix_xml(x):
    x = x.replace('lang="en-US"', 'lang="ko-KR"')                            # 한글 줄바꿈 규칙을 쓰도록 언어 지정
    # 주의: <a:ea charset>를 129로 바꾸면 PowerPoint가 파일을 손상으로 판단해 열지 못한다(실측). 건드리지 말 것.
    x = re.sub(r"<a:pPr(?![^>]*eaLnBrk)", '<a:pPr eaLnBrk="0"', x)          # 기존 pPr에 속성 추가
    return re.sub(r"<a:p>(?!<a:pPr)", '<a:p><a:pPr eaLnBrk="0"/>', x)        # pPr 없는 문단에 추가

def main(path):
    fd, tmp = tempfile.mkstemp(suffix=".pptx", dir=os.path.dirname(path)); os.close(fd)
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.endswith("/"):
                continue
            data = zin.read(item.filename)
            if TARGET.match(item.filename):
                data = fix_xml(data.decode("utf-8")).encode("utf-8")
            # 원본 ZipInfo 재사용 금지: 데이터 디스크립터 플래그 등이 남아 CRC가 어긋난다
            zout.writestr(zipfile.ZipInfo(item.filename, item.date_time), data, compress_type=zipfile.ZIP_DEFLATED)
    shutil.move(tmp, path)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
    # 자체 검사
    t = fix_xml('<a:p><a:r/></a:p><a:p><a:pPr algn="l"/></a:p><a:p><a:pPr eaLnBrk="0"/></a:p>')
    assert t.count('eaLnBrk="0"') == 3 and 'eaLnBrk="0" eaLnBrk' not in t, t
