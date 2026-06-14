const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "BuildSight Team";
pres.title = "BuildSight";

const C = {
  navy: "1B365D",
  orange: "E87A2A",
  light: "F5F7FA",
  white: "FFFFFF",
  dark: "1E293B",
  muted: "64748B",
  green: "10B981",
};

// ══════════ SLIDE 1: COVER ══════════
let s1 = pres.addSlide();
s1.background = { color: C.navy };
s1.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.04, fill: { color: C.orange } });
s1.addShape(pres.shapes.RECTANGLE, { x: 8.5, y: 0, w: 1.5, h: 5.625, fill: { color: "2C5F8A", transparency: 30 } });
s1.addText("BuildSight", { x: 0.8, y: 1.0, w: 7, h: 0.9, fontSize: 52, fontFace: "Arial", bold: true, color: C.white, margin: 0 });
s1.addText("家装智能自动报价系统", { x: 0.8, y: 1.9, w: 7, h: 0.6, fontSize: 28, fontFace: "Arial", color: "85C1E9", margin: 0 });
s1.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 2.65, w: 1.5, h: 0.04, fill: { color: C.orange } });
s1.addText("CAD图纸 + 效果图 → 双线独立处理 → AI融合报价", { x: 0.8, y: 3.0, w: 7, h: 0.4, fontSize: 14, fontFace: "Arial", color: C.muted, margin: 0 });
s1.addText("2026.06", { x: 0.8, y: 4.8, w: 3, h: 0.3, fontSize: 12, fontFace: "Arial", color: C.muted, margin: 0 });

// ══════════ SLIDE 2: 背景 ══════════
let s2 = pres.addSlide();
s2.background = { color: C.light };
s2.addText("传统报价 vs 智能报价", { x: 0.6, y: 0.3, w: 8, h: 0.6, fontSize: 28, fontFace: "Arial", bold: true, color: C.navy, margin: 0 });
s2.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.85, w: 1.2, h: 0.04, fill: { color: C.orange } });

s2.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.3, w: 4.3, h: 3.0, fill: { color: C.white }, shadow: { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.06 } });
s2.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.3, w: 4.3, h: 0.5, fill: { color: "EF4444", transparency: 15 } });
s2.addText("传统方式", { x: 0.6, y: 1.3, w: 4.3, h: 0.5, fontSize: 16, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
["人工现场量房 → 手绘草图", "逐房测量面积 → Excel录入", "效果图与报价单材质脱节", "多部门反复沟通 → 3~5天"].forEach((t, i) => {
  s2.addText("✗", { x: 0.8, y: 2.0 + i * 0.55, w: 0.3, h: 0.4, fontSize: 12, color: "EF4444", valign: "middle", margin: 0 });
  s2.addText(t, { x: 1.15, y: 2.0 + i * 0.55, w: 3.5, h: 0.4, fontSize: 12, fontFace: "Arial", color: C.dark, valign: "middle", margin: 0 });
});

s2.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.3, w: 4.3, h: 3.0, fill: { color: C.white }, shadow: { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.06 } });
s2.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.3, w: 4.3, h: 0.5, fill: { color: C.green, transparency: 15 } });
s2.addText("BuildSight", { x: 5.1, y: 1.3, w: 4.3, h: 0.5, fontSize: 16, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
["CAD图纸独立解析 → 秒级出量", "效果图独立AI识别 → 秒级出材质", "双线数据自动融合 → 一键报价", "全流程自动化 → 分钟级出单"].forEach((t, i) => {
  s2.addText("✓", { x: 5.3, y: 2.0 + i * 0.55, w: 0.3, h: 0.4, fontSize: 12, color: C.green, valign: "middle", margin: 0 });
  s2.addText(t, { x: 5.65, y: 2.0 + i * 0.55, w: 3.5, h: 0.4, fontSize: 12, fontFace: "Arial", color: C.dark, valign: "middle", margin: 0 });
});

s2.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.55, w: 8.8, h: 0.55, fill: { color: C.orange } });
s2.addText("⏱ 从接手需求到演示交付：仅用数天完成全系统开发", { x: 0.6, y: 4.55, w: 8.8, h: 0.55, fontSize: 16, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });

// ══════════ SLIDE 3: 真实案例 - 双线流程 ══════════
let s3 = pres.addSlide();
s3.background = { color: C.navy };
s3.addText("真实案例：双线独立处理 → 融合报价", { x: 0.6, y: 0.25, w: 9, h: 0.5, fontSize: 22, fontFace: "Arial", bold: true, color: C.white, margin: 0 });
s3.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.0, h: 0.04, fill: { color: C.orange } });

// ── LEFT TRACK: CAD ──
s3.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 1.0, w: 4.5, h: 0.35, fill: { color: C.orange } });
s3.addText("🔵 线路一：CAD图纸 → 解析工程量", { x: 0.4, y: 1.0, w: 4.5, h: 0.35, fontSize: 11, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });

const cadData = [
  ["阳光房", "111.9㎡", "墙面+地面+顶面"],
  ["休闲阳台", "14.6㎡", "墙面+地面"],
  ["客厅", "14.6㎡", "墙面+地面+顶面"],
  ["次卧×2", "28.5㎡", "墙面+地面+顶面"],
  ["主卧", "13.9㎡", "墙面+地面+顶面"],
  ["客餐厅", "13.9㎡", "墙面+地面+顶面"],
  ["厨房", "13.6㎡", "墙面+地面+防水"],
  ["卫生间×3", "21.8㎡", "墙面+地面+防水"],
  ["... 共106个空间", "总面积997㎡", ""],
];

// table header
s3.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 1.38, w: 4.5, h: 0.25, fill: { color: "2C5F8A" } });
s3.addText("空间", { x: 0.4, y: 1.38, w: 1.2, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s3.addText("面积", { x: 1.6, y: 1.38, w: 0.8, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s3.addText("施工范围", { x: 2.4, y: 1.38, w: 2.5, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });

cadData.forEach((row, i) => {
  const y = 1.63 + i * 0.23;
  const isLast = i === cadData.length - 1;
  if (!isLast) {
    s3.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 4.5, h: 0.23, fill: { color: i % 2 === 0 ? "F8FAFC" : "FFFFFF" } });
    s3.addText(row[0], { x: 0.45, y, w: 1.15, h: 0.23, fontSize: 8, fontFace: "Arial", color: C.dark, valign: "middle", margin: 0 });
    s3.addText(row[1], { x: 1.6, y, w: 0.8, h: 0.23, fontSize: 8, fontFace: "Arial", color: C.navy, bold: true, align: "center", valign: "middle", margin: 0 });
    s3.addText(row[2], { x: 2.4, y, w: 2.4, h: 0.23, fontSize: 7, fontFace: "Arial", color: C.muted, valign: "middle", margin: 0 });
  } else {
    s3.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 4.5, h: 0.25, fill: { color: C.orange, transparency: 40 } });
    s3.addText(row[0], { x: 0.45, y, w: 2, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, valign: "middle", margin: 0 });
    s3.addText(row[1], { x: 2, y, w: 2.4, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, valign: "middle", margin: 0 });
  }
});

// ── RIGHT TRACK: IMAGE ──
s3.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.0, w: 4.5, h: 0.35, fill: { color: C.orange } });
s3.addText("🟢 线路二：效果图 → AI识别材质", { x: 5.1, y: 1.0, w: 4.5, h: 0.35, fontSize: 11, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });

// Image result table
s3.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.38, w: 4.5, h: 0.25, fill: { color: "2C5F8A" } });
s3.addText("识别字段", { x: 5.1, y: 1.38, w: 1.1, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s3.addText("AI识别结果", { x: 6.2, y: 1.38, w: 1.6, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s3.addText("说明", { x: 7.8, y: 1.38, w: 1.8, h: 0.25, fontSize: 8, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });

const imgResults = [
  ["空间类型", "客厅", "匹配CAD客厅"],
  ["墙面材质", "乳胶漆", "白色/浅色系"],
  ["地面材质", "瓷砖", "浅灰色地砖"],
  ["顶面材质", "石膏板吊顶", "客厅标准吊顶"],
  ["装修风格", "现代简约", "主流家装风格"],
  ["——", "——", "——"],
  ["模型", "qwen2.5vl:latest", "50%准确率（需人工修正）"],
  ["耗时", "1.2秒/张", "GPU推理"],
];
imgResults.forEach((row, i) => {
  const y = 1.63 + i * 0.23;
  const bg = i % 2 === 0 ? "F8FAFC" : "FFFFFF";
  s3.addShape(pres.shapes.RECTANGLE, { x: 5.1, y, w: 4.5, h: 0.23, fill: { color: bg } });
  s3.addText(row[0], { x: 5.15, y, w: 1.05, h: 0.23, fontSize: 8, fontFace: "Arial", color: C.dark, valign: "middle", margin: 0 });
  s3.addText(row[1], { x: 6.2, y, w: 1.5, h: 0.23, fontSize: 8, fontFace: "Arial", bold: true, color: C.navy, align: "center", valign: "middle", margin: 0 });
  s3.addText(row[2], { x: 7.8, y, w: 1.7, h: 0.23, fontSize: 7, fontFace: "Arial", color: C.muted, valign: "middle", margin: 0 });
});

// ── MERGE ARROW ──
s3.addText("⬇", { x: 4.3, y: 3.8, w: 1.4, h: 0.35, fontSize: 20, color: C.orange, align: "center", valign: "middle", margin: 0 });

// ── BOTTOM: FUSION RESULT ──
s3.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 4.15, w: 9.2, h: 0.35, fill: { color: C.green } });
s3.addText("🔗 数据融合：CAD工程量 + AI识别材质 → 自动关联匹配 → 一键生成报价", { x: 0.4, y: 4.15, w: 9.2, h: 0.35, fontSize: 11, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });

s3.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 4.5, w: 9.2, h: 0.9, fill: { color: "2C5F8A", transparency: 30 } });
const lines = [
  ["基础报价（CAD工程量 × 单价）", "¥9,348,596"],
  ["材质差价（AI识别 → 自动调价）", "+ ¥14,959"],
  ["管理费 + 税金 + 损耗", "+ ¥1,040,810"],
  ["💰 最终报价总额", "¥10,404,365"],
];
lines.forEach((row, i) => {
  const y = 4.55 + i * 0.2;
  const bold = i === 3;
  s3.addText(row[0], { x: 0.6, y, w: 5, h: 0.2, fontSize: 9, fontFace: "Arial", bold, color: bold ? C.orange : "CBD5E1", valign: "middle", margin: 0 });
  s3.addText(row[1], { x: 5.6, y, w: 3.8, h: 0.2, fontSize: 9, fontFace: "Arial", bold, color: bold ? C.orange : "CBD5E1", align: "right", valign: "middle", margin: 0 });
});

// ══════════ SLIDE 4: 大模型应用 ══════════
let s4 = pres.addSlide();
s4.background = { color: C.light };
s4.addText("大模型两个核心应用", { x: 0.6, y: 0.3, w: 8, h: 0.6, fontSize: 28, fontFace: "Arial", bold: true, color: C.navy, margin: 0 });
s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.85, w: 1.2, h: 0.04, fill: { color: C.orange } });

s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.3, w: 8.8, h: 0.35, fill: { color: C.orange } });
s4.addText("应用一：大模型解析CAD图纸 —— 替代人工量房算量", { x: 0.6, y: 1.3, w: 8.8, h: 0.35, fontSize: 13, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.7, w: 4.3, h: 1.5, fill: { color: C.white }, shadow: { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.06 } });
s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.7, w: 0.06, h: 1.5, fill: { color: "EF4444" } });
s4.addText("传统：人工测量", { x: 0.85, y: 1.75, w: 3.9, h: 0.25, fontSize: 12, fontFace: "Arial", bold: true, color: "EF4444", margin: 0 });
s4.addText("CAD打开图纸 → 逐房测量面积 → 手写记录 → Excel录入 → 人工核对，一套房3~5天", { x: 0.85, y: 2.0, w: 3.9, h: 1.0, fontSize: 10, fontFace: "Arial", color: C.muted, margin: 0, lineSpacingMultiple: 1.3 });

s4.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.7, w: 4.3, h: 1.5, fill: { color: C.white }, shadow: { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.06 } });
s4.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.7, w: 0.06, h: 1.5, fill: { color: C.green } });
s4.addText("BuildSight：AI自动解析", { x: 5.35, y: 1.75, w: 3.9, h: 0.25, fontSize: 12, fontFace: "Arial", bold: true, color: C.green, margin: 0 });
s4.addText("上传DXF → 秒级输出106个空间面积/周长/扣减 → 零人工干预", { x: 5.35, y: 2.0, w: 3.9, h: 1.0, fontSize: 10, fontFace: "Arial", color: C.muted, margin: 0, lineSpacingMultiple: 1.3 });

s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.5, w: 8.8, h: 0.35, fill: { color: "2C5F8A" } });
s4.addText("应用二：大模型识别效果图 —— 替代人工辨别材质", { x: 0.6, y: 3.5, w: 8.8, h: 0.35, fontSize: 13, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.9, w: 4.3, h: 1.5, fill: { color: C.white }, shadow: { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.06 } });
s4.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.9, w: 0.06, h: 1.5, fill: { color: "EF4444" } });
s4.addText("传统：肉眼辨别", { x: 0.85, y: 3.95, w: 3.9, h: 0.25, fontSize: 12, fontFace: "Arial", bold: true, color: "EF4444", margin: 0 });
s4.addText("看效果图猜材质 → 手动查材料表 → 逐项录入报价单，容易看错、漏项", { x: 0.85, y: 4.2, w: 3.9, h: 1.0, fontSize: 10, fontFace: "Arial", color: C.muted, margin: 0, lineSpacingMultiple: 1.3 });

s4.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 3.9, w: 4.3, h: 1.5, fill: { color: C.white }, shadow: { type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.06 } });
s4.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 3.9, w: 0.06, h: 1.5, fill: { color: C.green } });
s4.addText("BuildSight：AI自动识别", { x: 5.35, y: 3.95, w: 3.9, h: 0.25, fontSize: 12, fontFace: "Arial", bold: true, color: C.green, margin: 0 });
s4.addText("上传效果图 → AI识别墙面/地面/顶面材质 → 1.2秒出结果（GPU），系统测试46项通过", { x: 5.35, y: 4.2, w: 3.9, h: 1.0, fontSize: 10, fontFace: "Arial", color: C.muted, margin: 0, lineSpacingMultiple: 1.3 });

// ══════════ SLIDE 5: 成果 ══════════
let s5 = pres.addSlide();
s5.background = { color: C.navy };
s5.addText("项目成果", { x: 0.6, y: 0.3, w: 8, h: 0.6, fontSize: 28, fontFace: "Arial", bold: true, color: C.white, margin: 0 });
s5.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.85, w: 1.2, h: 0.04, fill: { color: C.orange } });

[{ num: "106", label: "单张图纸\n解析空间数", color: C.orange },
 { num: "997㎡", label: "全屋\n总面积", color: "2C5F8A" },
 { num: "50%", label: "AI材质\n识别准确率\n（需人工修正）", color: C.green },
 { num: "¥1,040万", label: "融合报价\n总金额", color: "2C5F8A" },
].forEach((s, i) => {
  const x = 0.5 + i * 2.35;
  s5.addShape(pres.shapes.RECTANGLE, { x, y: 1.2, w: 2.1, h: 1.8, fill: { color: "2C5F8A", transparency: 40 } });
  s5.addShape(pres.shapes.RECTANGLE, { x, y: 1.2, w: 2.1, h: 0.04, fill: { color: s.color } });
  s5.addText(s.num, { x, y: 1.4, w: 2.1, h: 0.8, fontSize: 30, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
  s5.addText(s.label, { x, y: 2.2, w: 2.1, h: 0.6, fontSize: 11, fontFace: "Arial", color: "94A3B8", align: "center", margin: 0, lineSpacingMultiple: 1.2 });
});

["📄 CAD图纸 + 效果图 → 双线独立处理 → 融合报价", "🤖 大模型两个核心应用：解析CAD + 识别图片", "⚡ 数天内从0到1完成全系统开发交付", "🔒 系统稳定运行，零崩溃、零超时"].forEach((a, i) => {
  s5.addText(a, { x: 1, y: 3.3 + i * 0.5, w: 8, h: 0.4, fontSize: 13, fontFace: "Arial", color: "CBD5E1", valign: "middle", margin: 0 });
});

// ══════════ SLIDE 6: 结尾 ══════════
let s6 = pres.addSlide();
s6.background = { color: C.navy };
s6.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.04, fill: { color: C.orange } });
s6.addText("谢谢", { x: 0, y: 1.5, w: 10, h: 1.0, fontSize: 48, fontFace: "Arial", bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
s6.addText("BuildSight · 家装智能自动报价系统", { x: 0, y: 2.6, w: 10, h: 0.5, fontSize: 18, fontFace: "Arial", color: "85C1E9", align: "center", margin: 0 });
s6.addShape(pres.shapes.RECTANGLE, { x: 4, y: 3.3, w: 2, h: 0.04, fill: { color: C.orange } });
s6.addText("CAD图纸 + 效果图 → 双线独立处理 → AI融合报价", { x: 0, y: 3.6, w: 10, h: 0.4, fontSize: 13, fontFace: "Arial", color: C.muted, align: "center", margin: 0 });
s6.addText("数天内完成 · 从0到1 · 全链路交付", { x: 0, y: 4.1, w: 10, h: 0.3, fontSize: 12, fontFace: "Arial", color: "94A3B8", align: "center", margin: 0 });

pres.writeFile({ fileName: "/home/sd317/BuildSight_从0到1.pptx" })
  .then(() => console.log("✅ Done"))
  .catch(err => console.error("❌", err));
