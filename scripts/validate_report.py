#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asset-trace 自检闸门校验器（Step 4.5 机械四项）
用法：python3 validate_report.py <报告.md> [报告2.md ...]
对每份报告校验：
  1. 行数闭合：核对表含基线全集（法人 F1–F12 / 自然人 N1–N9），行数 = 基线 + 启用扩展项
  2. ✅ 完整性：每个 ✅ 行的「来源/说明」列非空且含日期（YYYY-MM-DD / YYYYMMDD / YYYY年M月D日）
  3. 统计闭合：核验状态统计行数字 = 核对表逐行实际计数
  4. ⛔ 对应性：每个 ⛔ 行都能在「调查令」相关章节找到关键词命中（无孤儿）
输出逐项 PASS/FAIL，任一 FAIL 退出码 1（不得交付）。
局限：仅判机械项；日期语义（出生日期≠查询日）、来源可信度仍需模型自检与人工判断。
"""
import re
import sys
from pathlib import Path

BASELINE = {"F": [f"F{i}" for i in range(1, 13)], "N": [f"N{i}" for i in range(1, 10)]}
STATUS = ["✅", "❗", "⏳", "⛔"]
DATE_PAT = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{8}")
STAT_PAT = re.compile(
    r"✅\s*(\d+)\s*(?:条|项|个)?\s*[｜|]\s*❗\s*(\d+)\s*(?:条|项|个)?\s*[｜|]\s*"
    r"⏳\s*(\d+)\s*(?:条|项|个)?\s*[｜|]\s*⛔\s*(\d+)\s*(?:条|项|个)?"
)
# 表级「查询日」声明：容忍 Markdown 加粗、冒号等非数字分隔（如 **表级查询日**：2026-10-22）
TABLE_DATE_PAT = re.compile(r"查询日[^0-9\n|]{0,12}(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})")
ID_PAT = re.compile(r"\b([FN]\d{1,2}|E\d{1,2})\b")


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_checklist(text):
    """返回 (rows, section_start, section_end)。row = dict(id, status, cells)"""
    rows = []
    span = None
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if "查全度核对表" in ln and ln.startswith("#"):
            span = [i, len(lines)]
            for j in range(i + 1, len(lines)):
                if ln2 := lines[j]:
                    if ln2.startswith("#") and j > i + 1:
                        span[1] = j
                        break
            break
    if not span:
        return rows, None
    for ln in lines[span[0] + 1: span[1]]:
        if not ln.strip().startswith("|"):
            continue
        cells = split_row(ln)
        if len(cells) < 3 or set(cells[0]) <= {"-", " ", ":"}:
            continue  # 分隔行
        joined = "|".join(cells)
        m = ID_PAT.search(cells[0]) or ID_PAT.search(joined[:12])
        st = next(
            (
                s
                for c in cells[1:4]
                for s in STATUS
                if s in c
            ),
            None,
        )
        if not st:
            continue
        # 无 F/N/E 编号的行（C 层 ⛔ 汇总行、B 层待人工汇总行）同样入表：
        # 参与状态统计与 ⛔/调查令对应性校验，但不计入「基线 + E 扩展」行数闭合。
        rows.append({"id": m.group(1) if m else "", "status": st, "cells": cells, "line": ln.strip()})
    return rows, span


def find_section(text, keywords, after=None):
    """找标题含任一关键词的章节全文；after=仅考虑某行之后"""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if after is not None and i < after:
            continue
        if ln.startswith("#") and any(k in ln for k in keywords):
            start = i
            break
    if start is None:
        return None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("#") and j > start + 1:
            return "\n".join(lines[start:j])
    return "\n".join(lines[start:])


def validate(path):
    text = Path(path).read_text(encoding="utf-8")
    issues, notes = [], []
    rows, span = parse_checklist(text)
    if not rows:
        return [f"未找到「查全度核对表」表格或无有效行"], notes
    lines = text.splitlines()
    seg = "\n".join(lines[span[0]: span[1]]) if span else ""

    # —— 1. 行数闭合 ——（闭合只算有基线/E 编号的行；无编号的 C 层汇总行不占基线）
    id_rows = [r for r in rows if r["id"]]
    ids = [r["id"] for r in id_rows]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        issues.append(f"基线 ID 重复：{sorted(dup)}")
    prefixes = {i[0] for i in ids if i[0] in "FN"}
    baseline_hits = []
    for p in ("F", "N"):
        got = {i for i in ids if i.startswith(p)}
        if len(got) >= 6:  # 该主体类型
            baseline_hits.append(p)
            missing = [b for b in BASELINE[p] if b not in got]
            if missing:
                issues.append(f"基线缺项：{missing}")
    if not baseline_hits:
        issues.append("无法识别基线类型（F/N 行均不足 6 条）")
    ext_ids = sorted({i for i in ids if i.startswith("E")}, key=lambda x: int(x[1:]))
    # 扩展行 = 非基线行（E 编号扩展项 + 无编号的 C 层/B 层汇总行）
    base_set = set()
    for p in baseline_hits:
        base_set |= set(BASELINE[p])
    extra_rows = [r for r in rows if r["id"] not in base_set]
    expect = len(base_set) + len(extra_rows)
    if len(rows) != expect:
        issues.append(f"行数不闭合：实际 {len(rows)} 行 ≠ 基线{baseline_hits}+扩展 {expect} 行")
    # 报告自报的「行数自检」与实际表格交叉核对（防自报数字造假）
    mrow = re.search(r"核对表\s*(\d+)\s*行", seg)
    mbase = re.search(r"基线\s*(\d+)", seg)
    mext = re.search(r"扩展(?:项)?\s*(\d+)", seg)
    if mrow and int(mrow.group(1)) != len(rows):
        issues.append(f"自报行数不符：声明 {mrow.group(1)} 行，实计 {len(rows)} 行")
    if mbase and int(mbase.group(1)) != len(base_set):
        issues.append(f"自报基线数不符：声明 {mbase.group(1)}，实为 {len(base_set)}")
    if mext and int(mext.group(1)) != len(extra_rows):
        issues.append(f"自报扩展数不符：声明 {mext.group(1)}，实为 {len(extra_rows)}")
    bad_ext = [i for i in ext_ids if not (1 <= int(i[1:]) <= 17)]  # v1.6 扩展项扩至 E1–E17
    if bad_ext:
        issues.append(f"扩展编号越界（应为 E1–E17）：{bad_ext}")

    # —— 2. ✅ 完整性（来源+日期；行级日期 或 表级「查询日」声明 二者取其一）——
    table_date = None
    if g := TABLE_DATE_PAT.search(seg):
        table_date = g.group(1)
    for r in rows:
        if r["status"] != "✅":
            continue
        tail = r["cells"][-1]
        if not DATE_PAT.search(tail) and not table_date:
            issues.append(f"✅ 行 {r['id']} 无行级查询日，且核对表无表级「查询日」声明")

    # —— 3. 统计闭合 ——
    # 统计行按输出模板落在「六、核验与免责」章节（核对表之后），故在核对表之后的全文中查找；
    # 若核对表章节内自带统计行则优先采用。
    def find_stat(scope_text):
        for ln in scope_text.splitlines():
            if "状态统计" in ln or STAT_PAT.search(ln):
                if g := STAT_PAT.search(ln):
                    return [int(x) for x in g.groups()]
        return None

    m = find_stat(seg) or find_stat("\n".join(lines[span[1]:] if span else lines))
    actual = [sum(1 for r in rows if r["status"] == s) for s in STATUS]
    if not m:
        issues.append("未找到核验状态统计行（✅ N ｜ ❗ N ｜ ⏳ N ｜ ⛔ N）")
    elif m != actual:
        issues.append(f"统计不符：声明 ✅{m[0]}/❗{m[1]}/⏳{m[2]}/⛔{m[3]}，逐行实计 ✅{actual[0]}/❗{actual[1]}/⏳{actual[2]}/⛔{actual[3]}")
    else:
        notes.append(f"统计闭合 ✅{actual[0]}/❗{actual[1]}/⏳{actual[2]}/⛔{actual[3]}（{len(rows)} 行）")

    # —— 4. ⛔ 对应性 ——
    c_rows = [r for r in rows if r["status"] == "⛔"]
    if c_rows:
        order = find_section(text, ["调查令"], after=span[1] if span else 0)
        if not order:
            issues.append(f"存在 {len(c_rows)} 个 ⛔，但未找到「调查令」章节")
        else:
            for r in c_rows:
                name = r["cells"][1] if len(r["cells"]) > 1 else ""
                kws = [w for w in re.split(r"[/（(，,、\s]+", name) if len(w) >= 2]
                if not any(k in order for k in kws):
                    issues.append(f"⛔ 行 {r['id']}（{name}）在调查令清单中无对应项（孤儿）")
    return issues, notes


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    any_fail = False
    for p in sys.argv[1:]:
        issues, notes = validate(p)
        print(f"\n== {Path(p).name} ==")
        for n in notes:
            print(f"  · {n}")
        if issues:
            any_fail = True
            for i in issues:
                print(f"  FAIL {i}")
        else:
            print("  PASS 四项机械校验全部通过")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
