// 발표 PPT 5개 디자인 버전 생성: node build.js
const pptxgen = require("pptxgenjs");
const path = require("path");
const SLIDES = require("./content");

const Y = "FFC20E", K = "111111", W = "FFFFFF";
const FONT = "Malgun Gothic";
const A = (f) => path.join(__dirname, "assets", f);

// ---------- 테마 5종 ----------
const THEMES = [
  { file: "발표_v1_위험경고.pptx", label: "위험 경고",
    bg: K, text: W, muted: "B5B5B5", card: "1F1F1F", cardText: W, accent: Y, onAccent: K,
    darkBg: K, darkText: W, frame: Y, decor: "hazardTag", titleDecor: "hazardBlock" },
  { file: "발표_v2_안전표지.pptx", label: "안전 표지",
    bg: W, text: K, muted: "5A5A5A", card: "F1F1F1", cardText: K, accent: Y, onAccent: K,
    darkBg: K, darkText: W, frame: K, decor: "signTriangle", titleDecor: "bigSign" },
  { file: "발표_v3_노랑현장.pptx", label: "노랑 현장",
    bg: Y, text: K, muted: "3A3A3A", card: K, cardText: W, accent: K, onAccent: Y, cardAccent: Y,
    darkBg: Y, darkText: K, frame: K, decor: "blackDot", titleDecor: "bigBang" },
  { file: "발표_v4_산업다크.pptx", label: "산업 다크",
    bg: "262626", text: W, muted: "BDBDBD", card: "333333", cardText: W, accent: Y, onAccent: K,
    darkBg: "1A1A1A", darkText: W, frame: Y, decor: "yellowSquare", titleDecor: "hazardHalf" },
  { file: "발표_v5_안전테이프.pptx", label: "안전 테이프",
    bg: "F3F3F3", text: K, muted: "555555", card: W, cardText: K, accent: Y, onAccent: K, shadow: true,
    darkBg: K, darkText: W, frame: K, decor: "tape", titleDecor: "tapeCross" },
];

// ---------- 공통 그리기 도구 ----------
function hazard(slide, pres, x, y, w, h) {   // 노랑·검정 사선 경고 무늬 (도형만 사용)
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: K }, line: { color: K }, objectName: "hazard-bg" });
  const s = Math.min(h * 0.7, 0.42);
  for (let i = 0; x + i * 2 * s + s <= x + w + 0.001; i++)
    slide.addShape(pres.shapes.PARALLELOGRAM, { x: x + i * 2 * s, y, w: s * 1.4, h,
      fill: { color: Y }, line: { color: Y, width: 0 }, objectName: "hazard-stripe" });
}
const card = (slide, pres, T, x, y, w, h, fill) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x, y, w, h, rectRadius: 0.08, fill: { color: fill || T.card }, line: { color: fill || T.card, width: 0 },
  shadow: T.shadow ? { type: "outer", color: "000000", opacity: 0.18, blur: 6, offset: 2, angle: 90 } : undefined,
  objectName: "card" });
const txt = (slide, text, o) => slide.addText(text, Object.assign({ isTextBox: true, fontFace: FONT, margin: 0, valign: "top" }, o));
const badge = (slide, pres, x, y, d, fill, color, glyph) => {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: "badge" });
  txt(slide, glyph, { x, y, w: d, h: d, fontSize: d * 26, bold: true, color, align: "center", valign: "middle" });
};

// 내용 슬라이드 제목 옆 장식 (테마별 모티프)
function contentDecor(slide, pres, T) {
  switch (T.decor) {
    case "hazardTag": hazard(slide, pres, 8.45, 0.47, 1.05, 0.3); break;
    case "signTriangle":
      slide.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 0.5, y: 0.38, w: 0.62, h: 0.55, fill: { color: Y }, line: { color: K, width: 2 }, objectName: "sign" });
      txt(slide, "!", { x: 0.5, y: 0.52, w: 0.62, h: 0.4, fontSize: 18, bold: true, color: K, align: "center" }); break;
    case "blackDot": badge(slide, pres, 0.5, 0.45, 0.42, K, Y, "!"); break;
    case "yellowSquare": slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 0.5, w: 0.26, h: 0.26, fill: { color: Y }, line: { color: Y }, objectName: "marker" }); break;
    case "tape": slide.addShape(pres.shapes.RECTANGLE, { x: 0.35, y: 0.32, w: 9.3, h: 0.72, rotate: -0.8, fill: { color: K }, line: { color: K }, objectName: "tape" }); break;
  }
}
const titleX = (T) => (["signTriangle", "blackDot"].includes(T.decor) ? 1.25 : T.decor === "yellowSquare" ? 0.95 : 0.5);

function defineLayouts(pres, T) {
  pres.defineSlideMaster({ title: "CONTENT", background: { color: T.bg },
    objects: [
      { text: { text: "CAT 320 경사지 전복 위험 시뮬레이터", options: { x: 0.5, y: 5.22, w: 5, h: 0.25, fontFace: FONT, fontSize: 9, color: T.muted } } },
      { placeholder: { options: { name: "title", type: "title", x: titleX(T), y: 0.35, w: 9.5 - titleX(T) - (T.decor === "hazardTag" ? 1.2 : 0), h: 0.65,
          fontFace: FONT, fontSize: 24, bold: true, color: T.decor === "tape" ? Y : T.text, align: T.decor === "tape" ? "center" : "left", valign: "middle", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.25, fontFace: FONT, fontSize: 9, color: T.muted, align: "right" } });
  pres.defineSlideMaster({ title: "DARK", background: { color: T.darkBg },
    objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 1.55, w: 6.4, h: 1.3,
      fontFace: FONT, fontSize: 34, bold: true, color: T.darkText, align: "left", valign: "top", margin: 0 }, text: "" } }] });
}

// ---------- 슬라이드 종류별 구성 ----------
function addTitleSlide(pres, T, s) {
  const slide = pres.addSlide({ masterName: "DARK", sectionTitle: "도입" });
  switch (T.titleDecor) {
    case "hazardBlock": hazard(slide, pres, 0.5, 4.55, 3.2, 0.45); break;
    case "bigSign":
      slide.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 6.9, y: 1.3, w: 2.6, h: 2.3, fill: { color: Y }, line: { color: W, width: 4 }, objectName: "sign" });
      txt(slide, "!", { x: 6.9, y: 1.95, w: 2.6, h: 1.5, fontSize: 80, bold: true, color: K, align: "center", valign: "middle" }); break;
    case "bigBang": badge(slide, pres, 7.0, 1.4, 2.3, K, Y, "!"); break;
    case "hazardHalf": hazard(slide, pres, 7.1, 0, 2.9, 5.625); break;
    case "tapeCross":
      slide.addShape(pres.shapes.RECTANGLE, { x: 5.6, y: 3.9, w: 5.2, h: 0.55, rotate: -14, fill: { color: Y }, line: { color: Y }, objectName: "tape" });
      txt(slide, "CAUTION · 주의 · CAUTION", { x: 5.7, y: 3.95, w: 5.0, h: 0.45, rotate: -14, fontSize: 16, bold: true, color: K, align: "center", valign: "middle" }); break;
  }
  txt(slide, s.kicker, { x: 0.5, y: 1.05, w: 6.3, h: 0.35, fontSize: 13, bold: true, color: T.darkBg === Y ? K : Y });
  slide.addText(s.title, { placeholder: "title" });
  txt(slide, s.sub, { x: 0.5, y: 3.0, w: 6.3, h: 0.5, fontSize: 18, color: T.darkText });
  slide.addNotes(s.notes);
}

function body(pres, T, s, section) {
  const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  contentDecor(slide, pres, T);
  slide.addText(s.title, { placeholder: "title" });
  slide.addNotes(s.notes);
  return slide;
}
const hl = (T) => T.cardAccent || T.accent;   // 카드 위 강조색
const hlText = (T) => (T.card === W || T.card === "F1F1F1" ? K : hl(T));   // 밝은 카드 위 강조 글자는 검정(노랑은 대비 부족)

function build(T) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "CAT 320 경사지 전복 위험 시뮬레이터 — " + T.label;
  pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
  defineLayouts(pres, T);
  const secs = { stats: "문제", gap: "문제", flow: "해결", parts: "해결", image: "해결", table: "신뢰성", compare: "신뢰성", verify: "신뢰성", ai: "AI", close: "마무리" };
  let lastSec = null;
  const sec = (name) => { if (name !== lastSec) { pres.addSection({ title: name }); lastSec = name; } return name; };

  for (const s of SLIDES) {
    if (s.type === "title") { sec("도입"); addTitleSlide(pres, T, s); continue; }
    if (s.type === "close") { sec("마무리"); addClose(pres, T, s); continue; }
    const slide = body(pres, T, s, sec(secs[s.type]));
    ({ stats, gap, flow, parts, image, table, compare, verify, ai })[s.type](slide, pres, T, s);
  }
  return pres.writeFile({ fileName: path.join(__dirname, T.file) })
    .then((f) => { require("child_process").execFileSync("python", [path.join(__dirname, "postprocess.py"), f], { stdio: "inherit" }); return f; });
}

function stats(slide, pres, T, s) {
  s.stats.forEach((st, i) => {
    const x = 0.5 + i * 3.1;
    card(slide, pres, T, x, 1.3, 2.9, 3.1);
    txt(slide, st.value, { x: x + 0.25, y: 1.6, w: 2.4, h: 0.9, fontSize: 44, bold: true, color: hlText(T) });
    txt(slide, st.label, { x: x + 0.25, y: 2.7, w: 2.4, h: 1.2, fontSize: 13, color: T.cardText });
  });
  card(slide, pres, T, 6.7, 1.3, 2.8, 3.1, T.accent);
  txt(slide, s.caseTitle, { x: 6.95, y: 1.55, w: 2.3, h: 0.4, fontSize: 16, bold: true, color: T.onAccent });
  txt(slide, s.caseText, { x: 6.95, y: 2.05, w: 2.3, h: 2.2, fontSize: 13, color: T.onAccent });
  txt(slide, s.source, { x: 0.5, y: 4.6, w: 9, h: 0.3, fontSize: 10, color: T.muted });
}
function gap(slide, pres, T, s) {
  [[s.left, "✓", 0.5], [s.right, "?", 5.1]].forEach(([c, g, x]) => {
    card(slide, pres, T, x, 1.3, 4.4, 2.45);
    badge(slide, pres, x + 0.3, 1.55, 0.5, hl(T), T.cardAccent ? K : T.onAccent, g);
    txt(slide, c.head, { x: x + 0.95, y: 1.58, w: 3.2, h: 0.45, fontSize: 20, bold: true, color: T.cardText });
    txt(slide, c.body, { x: x + 0.3, y: 2.3, w: 3.85, h: 1.35, fontSize: 14, color: T.cardText });
  });
  card(slide, pres, T, 0.5, 4.05, 9, 0.75, T.accent);
  txt(slide, "→  " + s.bottom, { x: 0.8, y: 4.05, w: 8.4, h: 0.75, fontSize: 16, bold: true, color: T.onAccent, valign: "middle" });
}
function flow(slide, pres, T, s) {
  s.steps.forEach((st, i) => {
    const x = 0.5 + i * 2.35;
    card(slide, pres, T, x, 1.45, 2.0, 3.0);
    badge(slide, pres, x + 0.72, 1.7, 0.56, hl(T), T.cardAccent ? K : T.onAccent, String(i + 1));
    txt(slide, st.head, { x: x + 0.15, y: 2.45, w: 1.7, h: 0.45, fontSize: 17, bold: true, color: T.cardText, align: "center" });
    txt(slide, st.body, { x: x + 0.15, y: 3.0, w: 1.7, h: 1.2, fontSize: 13, color: T.cardText, align: "center" });
    if (i < 3) slide.addShape(pres.shapes.CHEVRON, { x: x + 2.07, y: 2.8, w: 0.22, h: 0.32, fill: { color: T.text }, line: { color: T.text }, objectName: "arrow" });
  });
}
function parts(slide, pres, T, s) {
  slide.addChart(pres.charts.BAR, [{ name: "질량(kg)", labels: s.parts.map((p) => p.name), values: s.parts.map((p) => p.kg) }], {
    x: 0.5, y: 1.25, w: 5.6, h: 3.6, barDir: "bar", chartColors: [T.cardAccent ? K : Y],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", dataLabelColor: T.text, dataLabelFontSize: 12, dataLabelFontFace: FONT,
    catAxisLabelColor: T.text, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 13, valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, catAxisOrientation: "maxMin",
    showTitle: true, title: "부품별 질량 (kg)", titleColor: T.muted, titleFontSize: 12, titleFontFace: FONT });
  card(slide, pres, T, 6.4, 1.3, 3.1, 3.5);
  txt(slide, s.total, { x: 6.65, y: 1.55, w: 2.6, h: 0.6, fontSize: 13, bold: true, color: hlText(T) });
  txt(slide, s.rule, { x: 6.65, y: 2.25, w: 2.6, h: 1.2, fontSize: 16, bold: true, color: T.cardText });
  txt(slide, s.analogy, { x: 6.65, y: 3.6, w: 2.6, h: 1.0, fontSize: 13, color: T.cardText });
}
function image(slide, pres, T, s) {
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 1.2, w: 5.7, h: 3.79, fill: { color: T.frame }, line: { color: T.frame }, objectName: "frame" });
  slide.addImage({ path: A(s.img), x: 0.5, y: 1.25, w: 5.6, h: 3.69, altText: s.title });
  s.points.forEach((p, i) => {
    const y = 1.45 + i * 1.12;
    badge(slide, pres, 6.45, y, 0.42, T.accent, T.onAccent, String(i + 1));
    txt(slide, p, { x: 7.05, y: y - 0.02, w: 2.45, h: 0.95, fontSize: 14, color: T.text });
  });
}
function table(slide, pres, T, s) {
  const rows = s.rows.map((r, i) => r.map((c, j) => ({ text: c, options: {
    bold: i === 0, color: i === 0 ? T.onAccent : (j === 2 && /추정/.test(c) ? (T.cardAccent ? Y : (T.bg === W || T.bg === "F3F3F3" ? "B26B00" : Y)) : T.cardText),
    fill: { color: i === 0 ? T.accent : T.card }, fontFace: FONT, fontSize: 13, valign: "middle" } })));
  slide.addTable(rows, { x: 0.5, y: 1.3, w: 9, colW: [2.7, 3.5, 2.8], rowH: 0.45, border: { type: "solid", color: T.bg, pt: 2 }, margin: 0.08 });
  txt(slide, s.note, { x: 0.5, y: 4.3, w: 9, h: 0.4, fontSize: 13, color: T.muted });
}
function compare(slide, pres, T, s) {
  txt(slide, s.head, { x: 0.5, y: 1.2, w: 5.8, h: 0.35, fontSize: 14, bold: true, color: T.text });
  slide.addChart(pres.charts.BAR, [{ name: "안정 여유(m)", labels: s.bars.map((b) => b.label), values: s.bars.map((b) => b.value) }], {
    x: 0.5, y: 1.6, w: 5.8, h: 3.25, barDir: "col", chartColors: T.cardAccent ? ["7A5A00", K] : ["8C8C8C", Y],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00\" m\"", dataLabelColor: T.text, dataLabelFontSize: 16, dataLabelFontFace: FONT, dataLabelFontBold: true,
    catAxisLabelColor: T.text, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 13, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 0.65,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 80 });
  card(slide, pres, T, 6.6, 1.3, 2.9, 3.5, T.accent);
  txt(slide, "5배", { x: 6.85, y: 1.55, w: 2.4, h: 1.1, fontSize: 54, bold: true, color: T.onAccent });
  txt(slide, s.take, { x: 6.85, y: 2.8, w: 2.4, h: 1.8, fontSize: 15, bold: true, color: T.onAccent });
}
function verify(slide, pres, T, s) {
  [[s.left, 0.5, true], [s.right, 5.1, false]].forEach(([c, x, done]) => {
    card(slide, pres, T, x, 1.3, 4.4, 2.55);
    txt(slide, c.head, { x: x + 0.3, y: 1.5, w: 2.6, h: 0.45, fontSize: 19, bold: true, color: T.cardText });
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 3.05, y: 1.52, w: 1.1, h: 0.38, rectRadius: 0.19,
      fill: { color: done ? hl(T) : T.card }, line: { color: hl(T), width: 1.5 }, objectName: "status" });
    txt(slide, c.status, { x: x + 3.05, y: 1.52, w: 1.1, h: 0.38, fontSize: 12, bold: true, align: "center", valign: "middle",
      color: done ? (T.cardAccent ? K : T.onAccent) : T.cardText });
    txt(slide, c.body, { x: x + 0.3, y: 2.15, w: 3.85, h: 1.6, fontSize: 13, color: T.cardText });
  });
  card(slide, pres, T, 0.5, 4.1, 9, 0.7, T.accent);
  txt(slide, s.pre, { x: 0.8, y: 4.1, w: 8.4, h: 0.7, fontSize: 13, bold: true, color: T.onAccent, valign: "middle" });
}
function ai(slide, pres, T, s) {
  [[s.no, "✕", 0.5, false], [s.yes, "✓", 5.1, true]].forEach(([c, g, x, on]) => {
    card(slide, pres, T, x, 1.3, 4.4, 3.4, on ? T.accent : T.card);
    const fg = on ? T.onAccent : T.cardText;
    badge(slide, pres, x + 0.3, 1.55, 0.55, on ? T.onAccent : hl(T), on ? T.accent : (T.cardAccent ? K : T.onAccent), g);
    txt(slide, c.head, { x: x + 1.0, y: 1.6, w: 3.2, h: 0.45, fontSize: 18, bold: true, color: fg });
    txt(slide, c.items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < c.items.length - 1 } })),
      { x: x + 0.35, y: 2.4, w: 3.8, h: 2.1, fontSize: 15, color: fg, paraSpaceAfter: 10 });
  });
}
function addClose(pres, T, s) {
  const slide = pres.addSlide({ masterName: "DARK", sectionTitle: "마무리" });
  txt(slide, s.title, { x: 0.5, y: 0.45, w: 9, h: 0.7, fontSize: 30, bold: true, color: T.darkText, valign: "middle" });
  const onDarkCard = T.darkBg === Y ? K : "2A2A2A", cText = W, head = Y;
  [["한계", s.limits, 0.5], ["다음 단계", s.next, 5.1]].forEach(([h, items, x]) => {
    card(slide, pres, T, x, 1.4, 4.4, 2.9, onDarkCard);
    txt(slide, h, { x: x + 0.3, y: 1.6, w: 3.8, h: 0.4, fontSize: 18, bold: true, color: head });
    txt(slide, items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
      { x: x + 0.3, y: 2.15, w: 3.85, h: 2.0, fontSize: 14, color: cText, paraSpaceAfter: 6 });
  });
  txt(slide, "직접 해 보기  ·  " + s.link, { x: 0.5, y: 4.6, w: 9, h: 0.4, fontSize: 14, bold: true, color: T.darkText });
  slide.addNotes(s.notes);
}

(async () => {
  const only = process.argv[2];
  for (const T of THEMES) if (!only || T.file.includes(only)) { await build(T); console.log("wrote", T.file); }
})();
