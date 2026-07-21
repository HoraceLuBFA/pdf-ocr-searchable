#!/usr/bin/env python3
"""pdf_to_md.py — 把带文字层的 PDF 转成层级化 Markdown（纯标准库，无第三方依赖）。

原理：pdftotext -bbox-layout 给出每行文本的坐标与行高；
- 行高显著大于正文中位数 → 标题候选，配合中文书籍章节正则定级
- 页眉页脚：顶/底部区域跨页重复的文本与纯页码，剔除
- 段落：poppler 的 block 分组即段落，块内各行按中英文规则拼接
"""
import argparse, re, statistics, subprocess, sys, tempfile, os
from collections import Counter
from xml.etree import ElementTree as ET

CN_NUM = r"[0-9一二三四五六七八九十百千〇○零两]+"
RX_BU    = re.compile(rf"^第{CN_NUM}[部编卷篇]")
RX_ZHANG = re.compile(rf"^第{CN_NUM}[章讲]")
RX_JIE   = re.compile(rf"^(第{CN_NUM}节|[0-9]+\.[0-9]+(\.[0-9]+)?\s)")
RX_MATTER = re.compile(r"^(序言?|前言|导言|导论|引言|绪论|目录|结语|后记|跋|附录[一二三0-9]*|参考文献|索引|致谢|译后记|译者序|中译本序[言]?|作者简介)$")
RX_PAGENO = re.compile(r"^[·•\-—\s]*[0-9]{1,4}[·•\-—\s]*$")
RX_BARE  = re.compile(rf"^第{CN_NUM}[部编卷篇章讲]$")

def strip_ns(tag): return tag.rsplit('}', 1)[-1]

def join_words(words):
    out = []
    for w in words:
        if out and out[-1] and w:
            a, b = out[-1][-1], w[0]
            if (a.isascii() and (a.isalnum() or a in ',;:.)]%')) and \
               (b.isascii() and (b.isalnum() or b in '([')):
                out.append(' ')
        out.append(w)
    return ''.join(out)

def parse_pdf(pdf):
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tf:
        xml_path = tf.name
    try:
        subprocess.run(["pdftotext", "-bbox-layout", pdf, xml_path],
                       check=True, capture_output=True)
        lines, npages, page_h = [], 0, 800.0
        blk_id = 0
        for _, el in ET.iterparse(xml_path):
            t = strip_ns(el.tag)
            if t == "page":
                npages += 1
                page_h = float(el.get("height", 800))
                for blk in el:
                    if strip_ns(blk.tag) != "flow": continue
                    for block in blk:
                        blk_id += 1
                        for line in block:
                            h_line = float(line.get("yMax")) - float(line.get("yMin"))
                            ws = [(float(w.get("xMin")), float(w.get("xMax")),
                                   w.text or "") for w in line]
                            # 行内边码：原书页边码常被 OCR 并进相邻行。CJK 整行会合并成
                            # 单个词条，行内真数字都在词条内部——所以「独立的纯数字词 +
                            # 与邻词间距 >0.6 行高（约两倍空格宽）」即可判为边码剔除
                            if len(ws) >= 2:
                                di = set()
                                for j, (_, _, t2) in enumerate(ws):
                                    if re.fullmatch(r"[0-9]{1,4}", t2.strip()):
                                        gl = ws[j][0] - ws[j-1][1] if j else float("inf")
                                        gr = ws[j+1][0] - ws[j][1] if j < len(ws)-1 else float("inf")
                                        if min(gl, gr) > 0.6 * h_line: di.add(j)
                                ws = [w for j, w in enumerate(ws) if j not in di]
                            text = join_words([w[2] for w in ws]).strip()
                            if not text: continue
                            lines.append(dict(
                                text=text, page=npages, blk=blk_id, h=h_line,
                                xMin=float(line.get("xMin")),
                                yMin=float(line.get("yMin")), yMax=float(line.get("yMax")),
                                page_h=page_h))
                el.clear()
        return lines, npages
    finally:
        os.unlink(xml_path)

def classify(lines, npages):
    body = [l["h"] for l in lines if len(l["text"]) >= 10]
    body_h = statistics.median(body) if body else 12.0
    blk_size = Counter(l["blk"] for l in lines)

    # 书眉/页脚：顶/底 12% 区域内出现 ≥3 次的同一文本（章节名书眉每章只重复十几次，
    # 按页数比例设阈会漏）；纯页码同区域直接删
    zone = lambda l: l["yMin"] < 0.12 * l["page_h"] or l["yMax"] > 0.88 * l["page_h"]
    freq = Counter(l["text"] for l in lines if zone(l))
    drop = {t for t, c in freq.items() if c >= 3}

    kept = []
    for l in lines:
        t = l["text"]
        if zone(l) and (t in drop or RX_PAGENO.match(t)): continue
        if RX_PAGENO.match(t) and len(t) <= 6: continue  # 边栏页码（如原书边码）
        raw = 0  # 0=正文
        big = l["h"] > 1.15 * body_h
        # 含句读的是句子不是标题（真标题可含 ？：、，但几乎不含 。；，）
        sentence = ("。" in t) or ("；" in t) or ("，" in t)
        digits = sum(c.isdigit() for c in t) / len(t)
        if len(t) <= 30 and not sentence and digits < 0.4:
            if RX_BU.match(t): raw = 10
            elif RX_ZHANG.match(t) or RX_MATTER.match(t): raw = 20
            elif RX_JIE.match(t): raw = 30
            elif big and blk_size[l["blk"]] <= 3:
                # 仅行高触发的标题必须是独立小块——前言等字号偏大的整段正文不算
                raw = 25 if l["h"] > 1.4 * body_h else 35
        l["raw"] = raw
        kept.append(l)

    # 目录页降级：单页 ≥3 个部/章级候选（正文章首页最多 部+章 =2），
    # 或 ≥5 个任意正则候选（1.1/1.2 密集的教材式目录），整页归正文
    hi_cnt, all_cnt = Counter(), Counter()
    for l in kept:
        if l["raw"] in (10, 20): hi_cnt[l["page"]] += 1
        if l["raw"] in (10, 20, 30): all_cnt[l["page"]] += 1
    toc_pages = {p for p in all_cnt if hi_cnt[p] >= 3 or all_cnt[p] >= 5}
    for l in kept:
        if l["page"] in toc_pages and l["raw"]:
            l["raw"] = 0

    # 去重：同一标题（忽略尾部页码/点线/空白）保留首次出现——目录页已降级，
    # 此时的重复是书末注释区按章排的小节头，降为正文，免得与正文章标题混淆
    seen = set()
    for l in kept:
        if l["raw"] in (10, 20, 30):
            key = re.sub(r"[0-9•⋯·…\.\s:：]+$", "", l["text"])
            key = re.sub(r"\s+", "", key)
            if key in seen: l["raw"] = 0
            else:
                seen.add(key)
                # 「第三章意识能被…」同时登记裸前缀「第三章」——
                # 书末注释区按章排的裸章号小节头借此一并去重
                m = re.match(rf"第{CN_NUM}[章讲部编卷篇]", key)
                if m: seen.add(m.group(0))

    # 出现过的 raw 档位按序压缩成 1..n 级标题
    raws = sorted({l["raw"] for l in kept if l["raw"]})
    order = {r: i + 1 for i, r in enumerate(raws)}
    for l in kept:
        l["lv"] = min(order.get(l["raw"], 0), 6)

    # 段首缩进检测：每页栏左缘 = 该页正文行 xMin 的众数（奇偶页边距不同须分页算），
    # 行首右移 >0.8 行高即段首。全书缩进行占比 ≥5% 才启用缩进分段
    col = {}
    for l in kept:
        if len(l["text"]) >= 10:
            col.setdefault(l["page"], Counter())[round(l["xMin"])] += 1
    page_left = {p: c.most_common(1)[0][0] for p, c in col.items()}
    n_body = n_ind = 0
    for l in kept:
        left = page_left.get(l["page"], round(l["xMin"]))
        l["ind"] = (l["xMin"] - left) > 0.8 * body_h
        if not l["lv"] and len(l["text"]) >= 10:
            n_body += 1; n_ind += l["ind"]
    indent_mode = n_body > 0 and n_ind / n_body >= 0.05
    return kept, body_h, indent_mode

TERM = "。！？…”\"'.!?;"  # 段末终止符

def render(lines, indent_mode):
    out, stats = [], Counter()
    cur_blk, buf = None, []
    def flush():
        nonlocal buf
        if buf:
            out.append(join_words(buf))
            out.append("")
            stats["para"] += 1
            buf = []
    i = 0
    while i < len(lines):
        l = lines[i]
        if l["lv"]:
            flush()
            # 折行长标题合并：同块同级连续大字行；或裸章号（如「第三章」）
            # 紧跟同页的标题行（章号与题名常排成两个块）
            title = [l["text"]]
            while i + 1 < len(lines) and lines[i+1]["lv"] and (
                    (lines[i+1]["lv"] == l["lv"] and lines[i+1]["blk"] == l["blk"])
                    or (len(title) == 1 and RX_BARE.match(title[0])
                        and lines[i+1]["page"] == l["page"])):
                i += 1; title.append(lines[i]["text"])
            out.append("#" * l["lv"] + " " + join_words(title))
            out.append("")
            stats[f"h{l['lv']}"] += 1
        else:
            # 扫描件的换行是排版换行不是段落边界：缩进模式下只在段首缩进行断段
            # （跨块、跨页一律续接）；无缩进版式则退回块边界断段，但块末句子
            # 未收尾（无终止符）时与下块续接
            if indent_mode:
                if l["ind"]: flush()
            else:
                if cur_blk is not None and l["blk"] != cur_blk \
                   and buf and buf[-1] and buf[-1][-1] in TERM:
                    flush()
            buf.append(l["text"])
            cur_blk = l["blk"]
        i += 1
    flush()
    return "\n".join(out).rstrip() + "\n", stats

# 熔进词条内部的边码（几何法够不到）：句读后紧跟 1-3 位数字再跟汉字，
# 且该汉字不是计量/引用单位（「，3个」「，361页」「20世纪」是真内容，须保留）
UNITS = set("年月日页个种次条项款倍度分秒米克吨元角人天号版部卷篇章节世纪位名家股倍")
RX_FUSED = re.compile(r"([。，；：！？”])([0-9]{1,3})([一-龥])")

def clean_fused_pagenos(md):
    n = 0
    def sub(m):
        nonlocal n
        if m.group(3) in UNITS: return m.group(0)
        n += 1
        return m.group(1) + m.group(3)
    return RX_FUSED.sub(sub, md), n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    lines, npages = parse_pdf(a.pdf)
    if not lines:
        print(f"无文字层可提取: {a.pdf}", file=sys.stderr); sys.exit(1)
    kept, body_h, indent_mode = classify(lines, npages)
    md, stats = render(kept, indent_mode)
    md, n_fused = clean_fused_pagenos(md)
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(md)
    hs = " ".join(f"{k}:{v}" for k, v in sorted(stats.items()) if k.startswith("h"))
    mode = "缩进分段" if indent_mode else "块分段"
    print(f"{npages} 页 → {len(md)} 字符, 段落 {stats['para']}({mode}), 标题[{hs or '无'}], 正文行高中位数 {body_h:.1f}")

if __name__ == "__main__":
    main()
