#!/usr/bin/env python3
"""Lint a visual-decode analysis markdown file.

Checks required sections, term-card fields, evidence, parameters, confidence,
and bare vague adjectives. Exit code 1 when errors are found; warnings alone
exit 0 unless --strict is used.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = [
    "一句话判断",
    "拆解",
    "术语卡",
    "复现配方",
    "需求翻译卡",
    "自检",
]

RECOMMENDED_SECTIONS = [
    "置信度与不可见项",
]

TERM_FIELDS = {
    "一句话": "一句话",
    "证据": "证据",
    "作用": "作用",
    "参数 / 做法": "参数做法",
    "参数/做法": "参数做法",
    "参数": "参数",
    "做法": "做法",
    "怎么说": "怎么说",
    "易混": "易混",
    "置信度": "置信度",
}

VAGUE_WORDS = [
    "高级", "大气", "有质感", "氛围感", "电影感", "科技感", "治愈",
    "呼吸感", "年轻感", "复古", "赛博", "极简", "温柔", "力量感",
    "松弛感", "故事感", "仪式感", "未来感", "干净", "热闹", "安静",
    "贵", "便宜", "专业", "可信", "可爱", "酷", "甜", "野", "精致",
    "粗糙", "自然", "真实", "梦幻", "孤独", "拥挤", "秩序", "混乱",
]

CONCRETE_WORDS = [
    "饱和", "留白", "对比", "色温", "颜色", "字体", "字重", "圆角",
    "阴影", "间距", "网格", "景深", "光圈", "焦距", "帧率", "镜头",
    "硬切", "叠化", "转场", "颗粒", "光晕", "色板", "材质", "构图",
    "景别", "运镜", "缓动", "时长", "毫秒", "像素", "栏", "层级",
    "字号", "行高", "比例", "暖", "冷", "青", "橙", "蓝", "灰",
    "黑", "白", "侧光", "逆光", "柔光", "硬光", "低调", "高调",
    "浅景深", "广角", "长焦", "手持", "固定", "推", "拉", "摇",
    "窗光", "自然光", "环境声",
]

REGION_WORDS = [
    "首屏", "画面", "区域", "左上", "右上", "左下", "右下", "背景",
    "前景", "主体", "页", "屏", "按钮", "卡片", "第", "行", "列",
    "左侧", "右侧", "中间", "中心", "边缘", "顶部", "底部", "时间码",
]

PARAM_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:%|px|pt|dp|rpx|rem|em|mm|cm|m|s|ms|fps|K|k|Hz|dB|LUFS|倍|个|种|档|级|栏|秒|分钟|次|字|行|色))"
    r"|(f/\d+(?:\.\d+)?)"
    r"|(\d{1,2}:\d{2})"
    r"|(#[0-9A-Fa-f]{3,8})"
    r"|(rgba?\([^)]*\))",
)

TIMECODE_RE = re.compile(r"\b\d{1,2}:\d{2}\b")


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "_preamble"
    sections[current] = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def parse_cards(section: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in section.splitlines():
        if line.startswith("### "):
            if current is not None:
                cards.append(current)
            current = {"title": line[4:].strip(), "raw": ""}
            continue
        if current is None:
            continue
        current["raw"] += line + "\n"
        match = re.match(r"^\s*[-*]\s*\*\*(.+?)\*\*\s*[:：]\s*(.*)$", line)
        if match:
            raw_key = match.group(1).strip()
            key = TERM_FIELDS.get(raw_key)
            if key:
                current[key] = match.group(2).strip()
            else:
                current[raw_key] = match.group(2).strip()
    if current is not None:
        cards.append(current)
    return cards


def has_concrete(text: str) -> bool:
    if PARAM_RE.search(text):
        return True
    return any(word in text for word in CONCRETE_WORDS)


def has_region(text: str) -> bool:
    if TIMECODE_RE.search(text):
        return True
    return any(word in text for word in REGION_WORDS)


def lint(path: Path, strict: bool) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"[error] cannot read as UTF-8: {path}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"[error] not found: {path}", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    sections = parse_sections(text)

    for name in REQUIRED_SECTIONS:
        if name not in sections:
            errors.append(f"missing section: ## {name}")
        elif len(sections[name].strip()) < 10:
            errors.append(f"empty section: ## {name}")

    for name in RECOMMENDED_SECTIONS:
        if name not in sections:
            warnings.append(f"missing recommended section: ## {name}")

    order = [name for name in sections if name in REQUIRED_SECTIONS]
    expected = [name for name in REQUIRED_SECTIONS if name in order]
    if order != expected:
        warnings.append("section order differs from the template")

    decomposition = sections.get("拆解", "")
    for level in ("L1", "L2", "L3", "L4", "L5"):
        if level not in decomposition:
            warnings.append(f"拆解 section does not mention {level}")

    recipe = sections.get("复现配方", "")
    if recipe and "最省力的 20%" not in recipe:
        warnings.append("复现配方 does not include 最省力的 20%")
    if recipe and "成本分档" not in recipe:
        warnings.append("复现配方 does not include 成本分档")

    brief = sections.get("需求翻译卡", "")
    for version in ("对 AI", "对设计师", "对自己"):
        if version not in brief:
            warnings.append(f"需求翻译卡 does not include {version}")

    cards = parse_cards(sections.get("术语卡", ""))
    if len(cards) < 3:
        errors.append(f"term cards: found {len(cards)}, need at least 3")
    if len(cards) > 7:
        errors.append(f"term cards: found {len(cards)}, R-04 caps at 7; move extras to the appendix")

    for index, card in enumerate(cards, start=1):
        title = card.get("title", f"card-{index}")
        label = f"term {index:02d} ({title})"
        if "（" not in title and "(" not in title:
            warnings.append(f"{label}: title has no English name in parentheses")

        for key in ("一句话", "证据", "作用", "参数做法", "怎么说", "易混"):
            if not card.get(key):
                if key in {"证据", "参数做法", "怎么说"}:
                    errors.append(f"{label}: missing field **{key}**")
                else:
                    warnings.append(f"{label}: missing field **{key}**")

        evidence = card.get("证据", "")
        if evidence and not has_region(evidence):
            warnings.append(f"{label}: evidence has no timecode / region marker")

        parameters = card.get("参数做法") or card.get("参数") or card.get("做法") or ""
        if parameters and not has_concrete(parameters):
            warnings.append(f"{label}: parameters have no number / unit / concrete method")

        how = card.get("怎么说", "")
        if how and len(how.strip("「」\"' ")) < 8:
            warnings.append(f"{label}: **怎么说** is too short to be paste-ready")

        confidence = card.get("置信度", "")
        if not confidence:
            warnings.append(f"{label}: missing **置信度**")
        elif not any(word in confidence for word in ("高", "中", "低")):
            warnings.append(f"{label}: **置信度** does not say 高 / 中 / 低")

    # Bare vague adjectives: skip headings, tables, quotes, checklist sections.
    skip_sections = {"自检", "置信度与不可见项", "术语卡"}
    for section_name, body in sections.items():
        if section_name in skip_sections:
            continue
        for line_number, line in enumerate(body.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "|", ">", "```")):
                continue
            if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                continue
            # A goal line is allowed to stay a feeling; the parameters below it
            # are what the lint checks.
            if re.match(r"^\s*(【目标】|目标\s*[:：]|\*\*目标\*\*)", stripped):
                continue
            for word in VAGUE_WORDS:
                if word not in stripped:
                    continue
                if has_concrete(stripped):
                    continue
                warnings.append(
                    f"{section_name} line {line_number}: bare vague word 「{word}」; "
                    "translate it into observable features or parameters"
                )

    for message in errors:
        print(f"[error] {message}")
    for message in warnings:
        print(f"[warn] {message}")

    if errors:
        print(f"[fail] {len(cards)} terms, {len(errors)} errors, {len(warnings)} warnings")
        return 1
    if strict and warnings:
        print(f"[fail] strict mode: {len(cards)} terms, {len(errors)} errors, {len(warnings)} warnings")
        return 1
    print(f"[ok] {len(cards)} terms, {len(errors)} errors, {len(warnings)} warnings")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint a visual-decode markdown output.")
    parser.add_argument("file", help="markdown file to lint")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()
    raise SystemExit(lint(Path(args.file).expanduser(), args.strict))


if __name__ == "__main__":
    main()
