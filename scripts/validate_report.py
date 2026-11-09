#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asset-trace 自检闸门校验器（Step 4.5 机械项）
用法：python3 validate_report.py <报告.md> [报告2.md ...]
对每份报告校验：
  1.  行数闭合：核对表含基线全集（法人 F1–F12 / 自然人 N1–N9），行数 = 基线 + 启用扩展项（E1–E17）+ 启用 C 层项（C1–C9）
  1b. 无 ID 行：核对表数据行数须等于可解析的带 ID 行数（v1.6.3，堵「加行凑数」）
  2.  ✅ 完整性：每个 ✅ 行的「来源/说明」列非空且含日期（YYYY-MM-DD / YYYYMMDD / YYYY年M月D日）
  3.  统计闭合：核验状态统计行数字 = 核对表逐行实际计数（容许数字后带「条/项/个」）
  4.  ⛔ 双向对应性（v1.6.3）：
      · 调查令清单挂有行 ID → 严格模式：每个 ⛔ 行须被清单引用；清单引用的 ID 须存在且状态为 ⛔
      · 清单未挂 ID → 兼容模式：回退关键词匹配，并提示补 ID 列
输出逐项 PASS/FAIL，任一 FAIL 退出码 1（不得交付）。
局限：仅判机械项；日期语义（出生日期≠查询日）、来源可信度仍需模型自检与人工判断。
"""
import re
import sys
from pathlib import Path

__version__ = "1.7.0"

BASELINE = {"F": [f"F{i}" for i in range(1, 13)], "N": [f"N{i}" for i in range(1, 10)]}
STATUS = ["✅", "❗", "⏳", "⛔"]
DATE_PAT = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{8}")
# v1.6.3：容许数字后带量词（条/项/个）与全角分隔符
_QTY = r"(?:条|项|个)?"
STAT_PAT = re.compile(
    rf"✅\s*(\d+)\s*{_QTY}\s*[｜|]\s*❗\s*(\d+)\s*{_QTY}\s*[｜|]\s*⏳\s*(\d+)\s*{_QTY}\s*[｜|]\s*⛔\s*(\d+)\s*{_QTY}"
)
ID_PAT = re.compile(r"\b([FNCE]\d{1,2})\b")          # v1.7：新增 C 层专属编号 C1–C9
C_RANGE = (1, 9)


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
        if not m or not st:
            continue
        rows.append({"id": m.group(1), "status": st, "cells": cells, "line": ln.strip()})
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

    # —— 1. 行数闭合 ——
    ids = [r["id"] for r in rows]
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
    c_ids_in_tbl = sorted({i for i in ids if i.startswith("C")}, key=lambda x: int(x[1:]))
    # v1.7：C 层启用项按独立编号段计入行数（C 段不是扩展项，也不是基线）
    expect = (
        (12 if "F" in baseline_hits else 0)
        + (9 if "N" in baseline_hits else 0)
        + len(ext_ids)
        + len(c_ids_in_tbl)
    )
    if len(rows) != expect:
        issues.append(
            f"行数不闭合：实际 {len(rows)} 行 ≠ 基线{baseline_hits}+扩展 {len(ext_ids)}+C层 {len(c_ids_in_tbl)}，应为 {expect} 行"
        )
    bad_ext = [i for i in ext_ids if not (1 <= int(i[1:]) <= 17)]  # v1.6 扩展项扩至 E1–E17
    if bad_ext:
        issues.append(f"扩展编号越界（应为 E1–E17）：{bad_ext}")
    bad_c = [i for i in c_ids_in_tbl if not (C_RANGE[0] <= int(i[1:]) <= C_RANGE[1])]
    if bad_c:
        issues.append(f"C 层编号越界（应为 C1–C9）：{bad_c}")

    # —— 1b. 无 ID 行检测（v1.6.3：堵「加行凑数」）——
    if span:
        data_rows, in_table, seen_header = 0, False, False
        for ln in text.splitlines()[span[0]: span[1]]:
            s = ln.strip()
            if not s.startswith("|"):
                in_table, seen_header = False, False
                continue
            cells = split_row(s)
            if set("".join(cells).replace("|", "").strip()) <= {"-", " ", ":"}:
                continue  # 分隔行
            if not in_table:
                in_table, seen_header = True, True
                continue  # 表头
            data_rows += 1
        if data_rows != len(rows):
            issues.append(
                f"核对表存在 {data_rows - len(rows)} 行无合规 ID（表内数据行 {data_rows} ≠ 可解析行 {len(rows)}）"
            )

    # —— 2. ✅ 完整性（来源+日期；行级日期 或 表级「查询日」声明 二者取其一）——
    lines = text.splitlines()
    seg = "\n".join(lines[span[0]: span[1]]) if span else ""
    table_date = None
    if g := re.search(r"查询日\**\s*[：:]?\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})", seg):
        table_date = g.group(1)
    for r in rows:
        if r["status"] != "✅":
            continue
        tail = r["cells"][-1]
        if not DATE_PAT.search(tail) and not table_date:
            issues.append(f"✅ 行 {r['id']} 无行级查询日，且核对表无表级「查询日」声明")

    # —— 3. 统计闭合 ——
    m = None
    for ln in seg.splitlines():
        if "状态统计" in ln or STAT_PAT.search(ln):
            if g := STAT_PAT.search(ln):
                m = [int(x) for x in g.groups()]
                break
    actual = [sum(1 for r in rows if r["status"] == s) for s in STATUS]
    if not m:
        issues.append("未找到核验状态统计行（✅ N ｜ ❗ N ｜ ⏳ N ｜ ⛔ N）")
    elif m != actual:
        issues.append(f"统计不符：声明 ✅{m[0]}/❗{m[1]}/⏳{m[2]}/⛔{m[3]}，逐行实计 ✅{actual[0]}/❗{actual[1]}/⏳{actual[2]}/⛔{actual[3]}")
    else:
        notes.append(f"统计闭合 ✅{actual[0]}/❗{actual[1]}/⏳{actual[2]}/⛔{actual[3]}（{len(rows)} 行）")

    # —— 4. ⛔ 双向对应性（v1.6.3）——
    c_rows = [r for r in rows if r["status"] == "⛔"]
    if c_rows:
        order = find_section(text, ["调查令"], after=span[1] if span else 0)
        if not order:
            issues.append(f"存在 {len(c_rows)} 个 ⛔，但未找到「调查令」章节")
        else:
            c_ids = {r["id"] for r in c_rows}
            row_status = {r["id"]: r["status"] for r in rows}
            # 只在表格行与列表项里取 ID，避免章节内散文误命中（如"详见 F5"）
            order_ids = set()
            for ln in order.splitlines():
                s = ln.strip()
                if s.startswith("|") or re.match(r"^[-*+]\s|^\d+[.、)]", s):
                    order_ids |= set(ID_PAT.findall(s))
            if order_ids:
                # 严格模式：按「关联 ⛔ 行 ID」双向配对（v1.6.3 模板要求）
                for i in sorted(c_ids):
                    if i not in order_ids:
                        issues.append(f"⛔ 行 {i} 未在调查令清单中被引用（双向校验缺失）")
                for i in sorted(order_ids - set(row_status)):
                    issues.append(f"调查令清单引用了核对表中不存在的行 {i}")
                for i in sorted(order_ids - c_ids):
                    if i in row_status:
                        issues.append(f"调查令清单引用了非 ⛔ 行 {i}（核对表状态 {row_status[i]}）")
                if not (order_ids ^ c_ids):
                    notes.append(f"⛔ 双向配对闭合（{len(c_ids)} 个 ⛔ ↔ 调查令 {len(order_ids)} 项）")
            else:
                # 兼容模式：旧报告未挂 ID，回退关键词匹配
                notes.append("调查令清单未挂 ⛔ 行 ID，已回退关键词匹配（建议按 v1.6.3 模板补「关联 ⛔ 行 ID」列）")
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
            print("  PASS 机械校验全部通过")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
