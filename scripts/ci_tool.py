#!/usr/bin/env python3
"""宋词词牌检索、创作约束准备与格律校验工具。仅使用 Python 标准库。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CIPU_PATH = ASSETS / "qinding-cipu.json"
RHYME_PATH = ASSETS / "cilin-zhengyun.json"
UNIHAN_PATH = ASSETS / "unihan-readings.json"

# 用户未指定体式时采用的大众常用默认体式。只列出与《御定词谱》正体不同的词牌；
# 未列出的词牌继续回退到《御定词谱》标记的正体。
POPULAR_DEFAULT_VARIANTS = {
    "临江仙": "格八",
    "水调歌头": "格三",
    "念奴娇": "格二",
    "望江南": "格二",
    "忆江南": "格二",
    "南乡子": "格六",
    "江城子": "格五",
    "声声慢": "格十三",
}

PUNCT_RE = re.compile(r"[\s，。！？；：、,.!?;:·—…‘’“”\"'（）()《》〈〉【】\[\]{}]+")
SPLIT_RE = re.compile(r"[\r\n，。！？；：,.!?;:]+")
RHYME_SERIES_RE = re.compile(r"^(rhyme-\d+)(?:-cilin-\d+)?$")
ASCII_RHYME_RE = re.compile(r"^[a-zA-ZüÜvV]+[1-5]?$|^[a-zA-ZüÜvV]+$")
TONE_MARKS = {
    **{c: 1 for c in "āēīōūǖ"},
    **{c: 2 for c in "áéíóúǘ"},
    **{c: 3 for c in "ǎěǐǒǔǚ"},
    **{c: 4 for c in "àèìòùǜ"},
}
DIACRITIC_BASE = str.maketrans({
    **{c: "a" for c in "āáǎà"},
    **{c: "e" for c in "ēéěè"},
    **{c: "i" for c in "īíǐì"},
    **{c: "o" for c in "ōóǒò"},
    **{c: "u" for c in "ūúǔù"},
    **{c: "v" for c in "ǖǘǚǜüÜ"},
})


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"缺少数据文件：{path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_all() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return load_json(CIPU_PATH), load_json(RHYME_PATH), load_json(UNIHAN_PATH)


def plain_chars(text: str) -> str:
    return PUNCT_RE.sub("", text)


def split_lines(text: str) -> list[str]:
    return [plain_chars(x) for x in SPLIT_RE.split(text) if plain_chars(x)]


def reduplication_indexes(text: str, max_unit_length: int = 4) -> set[int]:
    """标记叠字及相邻叠词位置，例如“悠悠”“江山江山”。"""
    marked: set[int] = set()
    for unit_length in range(1, max_unit_length + 1):
        for start in range(0, len(text) - unit_length * 2 + 1):
            unit = text[start:start + unit_length]
            if unit and text[start + unit_length:start + unit_length * 2] == unit:
                marked.update(range(start, start + unit_length * 2))
    return marked


def tone_symbol(tone: str) -> str:
    return {"level": "平", "oblique": "仄", "either": "中"}.get(tone, "?")


def rhyme_series(position: dict[str, Any]) -> str | None:
    raw = position.get("rhyme")
    if not raw:
        return None
    match = RHYME_SERIES_RE.match(raw)
    return match.group(1) if match else raw


CN_DIGITS = "零一二三四五六七八九"


def chinese_number(value: int) -> str:
    if value < 10:
        return CN_DIGITS[value]
    if value < 20:
        return "十" + (CN_DIGITS[value % 10] if value % 10 else "")
    if value < 100:
        return CN_DIGITS[value // 10] + "十" + (CN_DIGITS[value % 10] if value % 10 else "")
    return str(value)


def parse_chinese_number(value: str) -> int | None:
    digits = {char: index for index, char in enumerate(CN_DIGITS)}
    total = current = 0
    for char in value:
        if char in digits:
            current = digits[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def variant_label(index: int, variant: dict[str, Any]) -> str:
    if index == 1 and variant.get("is_primary"):
        return "正体"
    return f"格{chinese_number(index)}"


def find_cipai(cipu: dict[str, Any], name: str) -> dict[str, Any]:
    canonical = [item for item in cipu["cipai"] if item["name"] == name]
    if canonical:
        return canonical[0]
    matches = []
    for item in cipu["cipai"]:
        names = {item.get("name_traditional"), *item.get("aliases", [])}
        if name in names:
            matches.append(item)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        options = "、".join(sorted({item["name"] for item in matches}))
        raise SystemExit(f"词牌名或别名“{name}”存在歧义，请改用规范名：{options}")
    available = "、".join(sorted(item["name"] for item in cipu["cipai"]))
    raise SystemExit(f"未收录词牌“{name}”。可用词牌：{available}")


def section_line_counts(introduction: str, stanza_count: int, total_lines: int) -> list[int]:
    number = r"([零一二三四五六七八九十百]+)"
    if stanza_count == 2:
        equal = re.search(rf"前后段各{number}句", introduction)
        if equal and (count := parse_chinese_number(equal.group(1))):
            if 0 < count < total_lines:
                return [count, total_lines - count]
        split = re.search(rf"前段{number}句.*?后段{number}句", introduction)
        if split:
            counts = [parse_chinese_number(split.group(1)), parse_chinese_number(split.group(2))]
            if all(counts) and 0 < int(counts[0]) < total_lines:
                return [int(counts[0]), total_lines - int(counts[0])]
    if stanza_count == 3:
        split = re.search(rf"前段{number}句.*?中段{number}句.*?后段{number}句", introduction)
        if split:
            counts = [parse_chinese_number(split.group(i)) for i in range(1, 4)]
            if all(counts) and sum(counts) == total_lines:
                return [int(x) for x in counts]
    base, extra = divmod(total_lines, max(stanza_count, 1))
    return [base + (1 if index < extra else 0) for index in range(max(stanza_count, 1))]


def normalize_pattern(
    cipai_node: dict[str, Any],
    variant_node: dict[str, Any],
    variant_index: int,
    rhyme_data: dict[str, Any] | None = None,
    unihan_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    encoding = variant_node["tonal_pattern"]["original_encoding"]
    groups: list[list[dict[str, Any]]] = [[]]
    positions: list[dict[str, Any]] = []
    absolute_position = 0
    tone_map = {"0": "level", "1": "oblique", "2": "either", "3": "either"}

    def finish_line(punctuation: str) -> None:
        nonlocal positions
        if positions:
            groups[-1].append({"positions": positions, "punctuation": punctuation})
            positions = []

    for token in encoding:
        if token in tone_map or token.isalpha():
            absolute_position += 1
            if token.isalpha():
                tone = "level" if token.islower() else "oblique"
                positions.append({"tone": tone, "rhymeTone": tone, "_absolutePosition": absolute_position})
            else:
                positions.append({"tone": tone_map[token], "_absolutePosition": absolute_position})
        elif token in "，。":
            finish_line(token)
        elif token == "|":
            if positions and positions[-1].get("rhymeTone"):
                finish_line("")
        elif token == "、":
            continue
    finish_line("")
    groups = [group for group in groups if group]
    flat_lines = [line for group in groups for line in group]

    rhyme_metadata = {int(item["position"]): item for item in variant_node.get("rhymes", [])}
    series_number = 0
    last_rhyme_tone: str | None = None
    current_series_candidates: set[str] | None = None
    series_group_sets: dict[str, list[set[str]]] = defaultdict(list)
    for line in flat_lines:
        last = line["positions"][-1]
        if last.get("rhymeTone"):
            tone = last["rhymeTone"]
            meta = rhyme_metadata.get(last["_absolutePosition"], {})
            example_char = meta.get("example_char")
            candidates: set[str] = set()
            if example_char and rhyme_data and unihan_data:
                readings = cilin_readings(example_char, rhyme_data["characters"], unihan_data["characters"])
                candidates = {item["rhymeGroup"] for item in readings if item["tone"] == tone}
            starts_new = last_rhyme_tone != tone
            if not starts_new and current_series_candidates and candidates and not (current_series_candidates & candidates):
                starts_new = True
            if starts_new:
                series_number += 1
                current_series_candidates = set(candidates) if candidates else None
            elif candidates:
                current_series_candidates = candidates if current_series_candidates is None else current_series_candidates & candidates
            last_rhyme_tone = tone
            series = f"rhyme-{series_number}"
            last["rhyme"] = series
            if candidates:
                series_group_sets[series].append(candidates)
        for position in line["positions"]:
            position.pop("_absolutePosition", None)

    suggestions: dict[str, list[str]] = {}
    for series, candidate_sets in series_group_sets.items():
        common = set.intersection(*candidate_sets) if candidate_sets else set()
        if common:
            suggestions[series] = sorted(common)

    stanza_count = max(int(variant_node.get("stanza_count") or 1), 1)
    counts = section_line_counts(variant_node.get("introduction", ""), stanza_count, len(flat_lines))
    section_names = {
        1: [variant_node.get("stanza_type") or "单调"],
        2: ["上阕", "下阕"],
        3: ["前段", "中段", "后段"],
    }.get(stanza_count, [f"第{chinese_number(i)}段" for i in range(1, stanza_count + 1)])
    sections = []
    offset = 0
    for section_index, count in enumerate(counts, start=1):
        section_lines = flat_lines[offset:offset + count]
        offset += count
        for line_index, line in enumerate(section_lines, start=1):
            line["id"] = f"line-{section_index}-{line_index}"
        sections.append({"id": f"stanza-{section_index}", "name": section_names[section_index - 1], "lines": section_lines})
    if offset < len(flat_lines):
        sections[-1]["lines"].extend(flat_lines[offset:])

    example_text = variant_node.get("example", {}).get("continuous", "")
    example_lines = split_lines(example_text)
    quality = variant_node.get("validation", {})
    return {
        "id": f"cipai-{cipai_node['id']}-variant-{variant_node['variant_id']}",
        "name": cipai_node["name"],
        "aliases": cipai_node.get("aliases", []),
        "variant": variant_label(variant_index, variant_node),
        "variantIndex": variant_index,
        "isPrimary": bool(variant_node.get("is_primary")),
        "source": variant_node.get("source", {}),
        "dataVersion": "2026-08-13.full-qinding-cipu",
        "reviewStatus": "validated" if quality.get("is_valid") else "source-warning",
        "example": {"author": variant_node.get("author"), "lines": example_lines, "simplifiedLines": example_lines},
        "description": variant_node.get("description") or cipai_node.get("description", ""),
        "specification": variant_node.get("introduction", ""),
        "sourceValidation": quality,
        "suggestedRhymeGroups": suggestions,
        "sections": sections,
    }


def select_pattern(
    cipu: dict[str, Any],
    name: str,
    variant: str | None,
    rhyme_data: dict[str, Any] | None = None,
    unihan_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cipai_node = find_cipai(cipu, name)
    variants = cipai_node["variants"]

    def matches(requested: str) -> list[tuple[int, dict[str, Any]]]:
        result = []
        for index, item in enumerate(variants, start=1):
            labels = {
                variant_label(index, item),
                f"格{chinese_number(index)}",
                str(item.get("variant_id", "")),
                f"cipai-{cipai_node['id']}-variant-{item.get('variant_id')}",
            }
            if item.get("is_primary"):
                labels.add("正体")
            if item.get("author"):
                labels.add(item["author"])
            if requested in labels:
                result.append((index, item))
        return result

    selected: tuple[int, dict[str, Any]] | None = None
    if variant:
        exact = matches(variant)
        if len(exact) > 1:
            options = "、".join(f"格{chinese_number(index)}({item.get('author', '无名氏')})" for index, item in exact)
            raise SystemExit(f"“{cipai_node['name']}”中“{variant}”对应多个体式，请改用：{options}")
        if not exact:
            options = "、".join(variant_label(index, item) for index, item in enumerate(variants, start=1))
            raise SystemExit(f"“{cipai_node['name']}”没有“{variant}”。可用变体：{options}")
        selected = exact[0]
    else:
        popular_variant = POPULAR_DEFAULT_VARIANTS.get(name) or POPULAR_DEFAULT_VARIANTS.get(cipai_node["name"])
        if popular_variant:
            popular = matches(popular_variant)
            if len(popular) == 1:
                selected = popular[0]
        if selected is None:
            primary = [(index, item) for index, item in enumerate(variants, start=1) if item.get("is_primary")]
            selected = primary[0] if primary else (1, variants[0])

    return normalize_pattern(cipai_node, selected[1], selected[0], rhyme_data, unihan_data)


def template_rows(pattern: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in pattern["sections"]:
        for line in section["lines"]:
            positions = line["positions"]
            last = positions[-1]
            rows.append(
                {
                    "section": section["name"],
                    "line_id": line["id"],
                    "length": len(positions),
                    "tones": "".join(tone_symbol(x.get("tone", "either")) for x in positions),
                    "rhyme_series": rhyme_series(last),
                    "rhyme_tone": last.get("rhymeTone"),
                    "punctuation": line.get("punctuation", ""),
                }
            )
    return rows


def traditional_candidates(char: str, unihan_chars: dict[str, Any]) -> set[str]:
    candidates = {char}
    info = unihan_chars.get(char, {})
    candidates.update(info.get("traditionalVariants", []))
    candidates.update(info.get("simplifiedVariants", []))
    return {x for x in candidates if len(x) == 1}


def cilin_readings(char: str, rhyme_chars: dict[str, Any], unihan_chars: dict[str, Any]) -> list[dict[str, Any]]:
    readings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in traditional_candidates(char, unihan_chars):
        for item in rhyme_chars.get(candidate, []):
            key = (item.get("tone", ""), item.get("rhymeGroup", ""), item.get("section", ""))
            if key not in seen:
                readings.append({**item, "matchedCharacter": candidate})
                seen.add(key)
    return readings


def pinyin_tone(pinyin: str) -> str | None:
    for c in pinyin:
        if c in TONE_MARKS:
            return "level" if TONE_MARKS[c] in (1, 2) else "oblique"
    match = re.search(r"([1-5])$", pinyin)
    if match:
        number = int(match.group(1))
        if number in (1, 2):
            return "level"
        if number in (3, 4):
            return "oblique"
    return None


def modern_tones(char: str, unihan_chars: dict[str, Any]) -> set[str]:
    info = unihan_chars.get(char, {})
    values = info.get("mandarin", []) + info.get("hanyuPinyin", []) + info.get("xhc1983", [])
    return {tone for value in values if (tone := pinyin_tone(value))}


def pinyin_final(pinyin: str) -> str:
    value = re.sub(r"[1-5]$", "", pinyin.lower()).translate(DIACRITIC_BASE)
    value = value.replace("u:", "v")
    match = re.search(r"(iang|uang|iong|ang|eng|ing|ong|iao|ian|uan|uai|uei|ui|uen|un|ai|ei|ao|ou|an|en|in|ia|ie|ua|uo|ve|er|a|o|e|i|u|v)$", value)
    return match.group(1) if match else value


def modern_finals(char: str, unihan_chars: dict[str, Any]) -> set[str]:
    info = unihan_chars.get(char, {})
    values = info.get("mandarin", []) + info.get("hanyuPinyin", []) + info.get("xhc1983", [])
    return {pinyin_final(x) for x in values if x}


def required_rhyme_tones(pattern: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for section in pattern["sections"]:
        for line in section["lines"]:
            last = line["positions"][-1]
            series = rhyme_series(last)
            if series and last.get("rhymeTone"):
                result[series].add(last["rhymeTone"])
    return dict(result)


def template_rhyme_groups(pattern: dict[str, Any]) -> dict[str, list[str]]:
    """提取谱例中各韵系的《词林正韵》韵部，供未指定韵脚时参考。"""
    if pattern.get("suggestedRhymeGroups"):
        return pattern["suggestedRhymeGroups"]
    result: dict[str, set[str]] = defaultdict(set)
    for section in pattern["sections"]:
        for line in section["lines"]:
            raw = line["positions"][-1].get("rhyme")
            if not raw:
                continue
            match = re.match(r"^(rhyme-\d+)-(cilin-\d+)$", raw)
            if match:
                result[match.group(1)].add(match.group(2))
    return {series: sorted(groups) for series, groups in result.items()}


def group_indexes(rhyme_data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[tuple[str, str]]]]:
    groups: dict[str, dict[str, Any]] = {}
    sections: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for group in rhyme_data["groups"]:
        groups[group["id"]] = group
        groups[group["name"]] = group
        for section in group["sections"]:
            sections[section["name"]].append((group["id"], section["tone"]))
    return groups, sections


def parse_rhyme_constraint(
    spec: str | None,
    rhyme_data: dict[str, Any],
    unihan_data: dict[str, Any],
) -> dict[str, Any]:
    if not spec:
        return {"mode": "unspecified", "raw": None, "allowed_groups": [], "allowed_characters": [], "modern_final": None}
    value = spec.strip()
    groups, sections = group_indexes(rhyme_data)
    if value in groups:
        group = groups[value]
        return {"mode": "group", "raw": value, "allowed_groups": [group["id"]], "allowed_characters": [], "modern_final": None}
    if value in sections:
        return {
            "mode": "section",
            "raw": value,
            "allowed_groups": sorted({group_id for group_id, _ in sections[value]}),
            "allowed_characters": [],
            "modern_final": None,
            "section_tones": sorted({tone for _, tone in sections[value]}),
        }
    compact = re.sub(r"[、，,；;\s/]+", "", value)
    if ASCII_RHYME_RE.fullmatch(value):
        return {
            "mode": "modern-final",
            "raw": value,
            "allowed_groups": [],
            "allowed_characters": [],
            "modern_final": pinyin_final(value),
        }
    characters = list(dict.fromkeys(compact))
    allowed_groups: set[str] = set()
    per_character: dict[str, list[str]] = {}
    for char in characters:
        readings = cilin_readings(char, rhyme_data["characters"], unihan_data["characters"])
        char_groups = sorted({x["rhymeGroup"] for x in readings})
        per_character[char] = char_groups
        allowed_groups.update(char_groups)
    return {
        "mode": "characters",
        "raw": value,
        "allowed_groups": sorted(allowed_groups),
        "allowed_characters": characters,
        "modern_final": None,
        "character_groups": per_character,
    }


def rhyme_bank(rhyme_data: dict[str, Any], group_id: str, tone: str | None, limit: int) -> list[dict[str, Any]]:
    group = next((g for g in rhyme_data["groups"] if g["id"] == group_id), None)
    if not group:
        return []
    result: list[dict[str, Any]] = []
    for section in group["sections"]:
        if tone and section["tone"] != tone:
            continue
        result.append(
            {
                "section": section["name"],
                "tone": section["tone"],
                "characters": section["characters"][:limit],
            }
        )
    return result


def prepare(args: argparse.Namespace) -> None:
    cipu, rhyme_data, unihan_data = load_all()
    pattern = select_pattern(cipu, args.cipai, args.variant, rhyme_data, unihan_data)
    constraint = parse_rhyme_constraint(args.rhyme, rhyme_data, unihan_data)
    tones = required_rhyme_tones(pattern)
    suggested_groups = template_rhyme_groups(pattern)
    banks: dict[str, list[dict[str, Any]]] = {}
    compatibility_issues: list[dict[str, Any]] = []
    for series, series_tones in tones.items():
        banks[series] = []
        group_ids = constraint["allowed_groups"] or suggested_groups.get(series, [])
        for group_id in group_ids[:4]:
            for tone in sorted(series_tones):
                entries = rhyme_bank(rhyme_data, group_id, tone, args.bank_limit)
                banks[series].append({"group": group_id, "entries": entries})
                if not entries:
                    compatibility_issues.append({"series": series, "group": group_id, "requiredTone": tone, "message": "该韵部没有所需声调的韵字"})
        if constraint["mode"] == "characters":
            usable = []
            for char in constraint["allowed_characters"]:
                char_tones = {x["tone"] for x in cilin_readings(char, rhyme_data["characters"], unihan_data["characters"])}
                if char_tones & series_tones:
                    usable.append(char)
            if not usable:
                compatibility_issues.append({"series": series, "requiredTones": sorted(series_tones), "characters": constraint["allowed_characters"], "message": "指定韵脚字没有满足该韵系声调要求的候选"})
    payload = {
        "request": {"cipai": args.cipai, "variant": pattern["variant"], "theme": args.theme, "poet": args.poet, "rhyme": args.rhyme},
        "pattern": {
            "id": pattern["id"],
            "name": pattern["name"],
            "variant": pattern["variant"],
            "specification": pattern["specification"],
            "exampleAuthor": pattern.get("example", {}).get("author"),
            "exampleLines": pattern.get("example", {}).get("simplifiedLines") or pattern.get("example", {}).get("lines", []),
            "sourceValidation": pattern.get("sourceValidation", {}),
            "rows": template_rows(pattern),
        },
        "rhymeConstraint": constraint,
        "suggestedRhymeGroups": suggested_groups,
        "requiredRhymeTones": {k: sorted(v) for k, v in tones.items()},
        "rhymeBanks": banks,
        "compatibilityIssues": compatibility_issues,
        "generationChecklist": [
            "先按行数、每句字数和平仄骨架拟句，再润色意象与章法",
            "同一 rhyme_series 的句末字须落在同一《词林正韵》韵部",
            "除叠字、叠词外尽量避免重复用字，尤其不得重复使用同一韵脚字",
            "平韵、仄韵按 rhyme_tone 分别满足；中位可平可仄",
            "主题须形成起承转合，避免只堆砌关键词",
            "模仿指定词人的意象、句法、语气与用典密度，不照抄名句",
            "生成后运行 validate，未通过则逐字修改并复验",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def list_patterns(args: argparse.Namespace) -> None:
    cipu = load_json(CIPU_PATH)
    by_name: dict[str, list[str]] = {}
    for item in cipu["cipai"]:
        labels = [variant_label(index, variant) for index, variant in enumerate(item["variants"], start=1)]
        by_name[item["name"]] = labels
    if args.query:
        matched = {}
        for item in cipu["cipai"]:
            names = [item["name"], item.get("name_traditional"), *item.get("aliases", [])]
            if any(name and args.query in name for name in names):
                matched[item["name"]] = by_name[item["name"]]
        by_name = matched
    print(json.dumps(by_name, ensure_ascii=False, indent=2))


def lookup_rhyme(args: argparse.Namespace) -> None:
    rhyme_data, unihan_data = load_json(RHYME_PATH), load_json(UNIHAN_PATH)
    constraint = parse_rhyme_constraint(args.rhyme, rhyme_data, unihan_data)
    payload: dict[str, Any] = {"constraint": constraint, "banks": {}}
    for group_id in constraint["allowed_groups"]:
        payload["banks"][group_id] = rhyme_bank(rhyme_data, group_id, args.tone, args.limit)
    if constraint["mode"] == "modern-final":
        final = constraint["modern_final"]
        matches = []
        for char in rhyme_data["characters"]:
            if final in modern_finals(char, unihan_data["characters"]):
                matches.append(char)
            if len(matches) >= args.limit:
                break
        payload["modernFinalCandidates"] = matches
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def validate(args: argparse.Namespace) -> None:
    cipu, rhyme_data, unihan_data = load_all()
    pattern = select_pattern(cipu, args.cipai, args.variant, rhyme_data, unihan_data)
    text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    lines = split_lines(text)
    rows = template_rows(pattern)
    constraint = parse_rhyme_constraint(args.rhyme, rhyme_data, unihan_data)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    if len(lines) != len(rows):
        errors.append({"type": "line_count", "expected": len(rows), "actual": len(lines), "message": "句数与词谱不符"})

    series_endings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pattern_lines = [line for section in pattern["sections"] for line in section["lines"]]
    for index, (actual, row, line_spec) in enumerate(zip(lines, rows, pattern_lines), start=1):
        line_check: dict[str, Any] = {"line": index, "text": actual, "expectedLength": row["length"], "expectedTones": row["tones"], "issues": []}
        if len(actual) != row["length"]:
            issue = {"type": "length", "line": index, "expected": row["length"], "actual": len(actual)}
            errors.append(issue)
            line_check["issues"].append(issue)
        for pos_index, (char, pos_spec) in enumerate(zip(actual, line_spec["positions"]), start=1):
            required = pos_spec.get("tone", "either")
            if required == "either":
                continue
            readings = cilin_readings(char, rhyme_data["characters"], unihan_data["characters"])
            tones = {x["tone"] for x in readings}
            source = "词林正韵"
            if not tones:
                tones = modern_tones(char, unihan_data["characters"])
                source = "现代普通话回退"
            if not tones:
                warning = {"type": "unknown_tone", "line": index, "position": pos_index, "char": char}
                warnings.append(warning)
                line_check["issues"].append(warning)
            elif required not in tones:
                issue = {"type": "tone", "line": index, "position": pos_index, "char": char, "expected": tone_symbol(required), "actual": [tone_symbol(x) for x in sorted(tones)], "source": source}
                errors.append(issue)
                line_check["issues"].append(issue)
            elif len(tones) > 1:
                warning = {"type": "ambiguous_tone", "line": index, "position": pos_index, "char": char, "readings": [tone_symbol(x) for x in sorted(tones)]}
                warnings.append(warning)
                line_check["issues"].append(warning)
        last_spec = line_spec["positions"][-1]
        series = rhyme_series(last_spec)
        if series and actual:
            char = actual[-1]
            readings = cilin_readings(char, rhyme_data["characters"], unihan_data["characters"])
            series_endings[series].append(
                {
                    "line": index,
                    "char": char,
                    "groups": sorted({x["rhymeGroup"] for x in readings if not last_spec.get("rhymeTone") or x["tone"] == last_spec.get("rhymeTone")}),
                    "requiredTone": last_spec.get("rhymeTone"),
                    "modernFinals": sorted(modern_finals(char, unihan_data["characters"])),
                    "reduplicationExempt": len(actual) - 1 in reduplication_indexes(actual),
                }
            )
        checks.append(line_check)

    for series, endings in series_endings.items():
        known_sets = [set(x["groups"]) for x in endings if x["groups"]]
        common = set.intersection(*known_sets) if known_sets else set()
        if len(known_sets) != len(endings):
            errors.append({"type": "unknown_rhyme", "series": series, "endings": endings, "message": "部分韵脚无法在《词林正韵》中定位"})
        elif not common:
            errors.append({"type": "rhyme_group", "series": series, "endings": endings, "message": "同一韵系的句末字不在同一韵部"})
        allowed_groups = set(constraint["allowed_groups"])
        if allowed_groups and common and not (common & allowed_groups):
            errors.append({"type": "specified_rhyme_group", "series": series, "commonGroups": sorted(common), "allowedGroups": sorted(allowed_groups)})
        if constraint["mode"] == "characters":
            allowed_chars = set(constraint["allowed_characters"])
            wrong = [x for x in endings if x["char"] not in allowed_chars]
            if wrong:
                errors.append({"type": "specified_end_characters", "series": series, "allowedCharacters": sorted(allowed_chars), "actual": wrong})
        if constraint["mode"] == "modern-final":
            expected_final = constraint["modern_final"]
            wrong = [x for x in endings if expected_final not in x["modernFinals"]]
            if wrong:
                errors.append({"type": "modern_final", "series": series, "expected": expected_final, "actual": wrong})

    for series, endings in series_endings.items():
        repeated_endings: dict[str, list[int]] = defaultdict(list)
        for ending in endings:
            if not ending.get("reduplicationExempt"):
                repeated_endings[ending["char"]].append(ending["line"])
        for char, line_numbers in repeated_endings.items():
            if len(line_numbers) > 1:
                warnings.append(
                    {
                        "type": "repeated_rhyme_character",
                        "series": series,
                        "char": char,
                        "lines": line_numbers,
                        "message": "同一韵脚字重复使用；除明确叠字、叠词外应换用同韵部其他字",
                    }
                )

    repeated_characters: dict[str, list[dict[str, int]]] = defaultdict(list)
    for line_number, line_text in enumerate(lines, start=1):
        exempt_indexes = reduplication_indexes(line_text)
        for position, char in enumerate(line_text, start=1):
            if position - 1 not in exempt_indexes:
                repeated_characters[char].append({"line": line_number, "position": position})
    for char, occurrences in repeated_characters.items():
        if len(occurrences) > 1:
            warnings.append(
                {
                    "type": "repeated_character",
                    "char": char,
                    "occurrences": occurrences,
                    "message": "正文用字重复；若非必要虚词、叠字或叠词，建议换字润色",
                }
            )

    result = {
        "passed": not errors,
        "pattern": {"name": pattern["name"], "variant": pattern["variant"], "specification": pattern["specification"]},
        "summary": {"errors": len(errors), "warnings": len(warnings), "checkedLines": min(len(lines), len(rows)), "expectedLines": len(rows)},
        "errors": errors,
        "warnings": warnings,
        "lineChecks": checks,
        "rhymeEndings": series_endings,
        "note": "本工具确定性校验字数、平仄、押韵并提示重复用字；主题贴合度、词人风格和语义质量仍需人工或模型复核。",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="宋词词牌准备与格律校验")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出收录词牌和变体")
    p_list.add_argument("--query", help="按词牌名筛选")
    p_list.set_defaults(func=list_patterns)

    p_prepare = sub.add_parser("prepare", help="生成创作约束包")
    p_prepare.add_argument("--cipai", required=True, help="词牌名")
    p_prepare.add_argument("--variant", help="变体名或模板 ID；省略时采用大众常用体式（如临江仙格八），其余回退正体")
    p_prepare.add_argument("--theme", required=True, help="主题")
    p_prepare.add_argument("--poet", required=True, help="拟仿词人")
    p_prepare.add_argument("--rhyme", help="韵部、韵目、指定韵脚字或现代拼音韵母")
    p_prepare.add_argument("--bank-limit", type=int, default=80, help="每个韵目最多展示的候选字数")
    p_prepare.set_defaults(func=prepare)

    p_rhyme = sub.add_parser("rhyme", help="查询韵部或韵脚候选")
    p_rhyme.add_argument("--rhyme", required=True, help="韵部、韵目、韵脚字或现代拼音韵母")
    p_rhyme.add_argument("--tone", choices=["level", "oblique"], help="只看平声或仄声")
    p_rhyme.add_argument("--limit", type=int, default=120)
    p_rhyme.set_defaults(func=lookup_rhyme)

    p_validate = sub.add_parser("validate", help="校验一首词")
    p_validate.add_argument("--cipai", required=True)
    p_validate.add_argument("--variant")
    source = p_validate.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="词正文")
    source.add_argument("--file", help="UTF-8 文本文件")
    p_validate.add_argument("--rhyme", help="与 prepare 相同的韵脚约束")
    p_validate.set_defaults(func=validate)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
