#!/usr/bin/env python3
"""宋词词牌检索、创作约束准备与格律校验工具。仅使用 Python 标准库。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
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

SEASONAL_CONTEXTS = {
    "春": [
        {
            "scene": "春日雨霁，柳岸花影新明，游人缓步小桥",
            "theme": "春日雨霁游柳岸，由新花流水写春游清欢与惜时之意",
        },
        {
            "scene": "江南细雨初收，燕子掠过青瓦，远山尚带轻烟",
            "theme": "江南烟雨后倚楼看归燕，以水乡新绿写故园之思",
        },
        {
            "scene": "暮春庭院花落满阶，帘外蜂蝶渐稀，夕阳移过秋千",
            "theme": "暮春独坐庭院，由花事将阑写惜春、流年与淡淡闲愁",
        },
        {
            "scene": "上巳水边草木明媚，曲水映着晴云，游人踏青归晚",
            "theme": "上巳春游临水流觞，以明丽游赏写相逢之乐与清欢",
        },
        {
            "scene": "春夜月上梨花，风动帘栊，远处传来一声归笛",
            "theme": "春夜对月怀远，由梨花疏影与归笛写相思和天涯阻隔",
        },
        {
            "scene": "清明驿路微雨，芳草连天，行人回望旧日故园",
            "theme": "清明雨中行旅，由芳草驿路追忆故人，写羁旅与思乡",
        },
        {
            "scene": "杏花村外新犁水满，燕衔春泥，农人唱晚归来",
            "theme": "杏花春村观农事，以田园新作写村居生意与闲适自得",
        },
        {
            "scene": "长亭外柳丝拂马，春水载舟，薄暮烟霭渐合",
            "theme": "暮春长亭送别，由柳色行舟铺写临歧不舍与别后遥想",
        },
        {
            "scene": "海棠庭院日影迟迟，香篆将尽，独坐人轻展旧笺",
            "theme": "春昼庭院独坐读旧笺，由海棠香篆写相思与旧游",
        },
        {
            "scene": "春江潮平，楼头云开，数点白帆驶向暮色深处",
            "theme": "春日登临江楼，望远帆归去，由江天开阔写远思与澄怀",
        },
    ],
    "夏": [
        {
            "scene": "夏夜雨歇，荷塘风起，月色碎落水面",
            "theme": "夏夜雨后泛舟荷塘，由风荷月影写尘虑暂消与闲适自得",
        },
        {
            "scene": "午后竹院浓阴覆阶，茶烟轻起，远处蝉声时断时续",
            "theme": "盛夏竹院闲居纳凉，以茶烟蝉声写幽居清静与自适",
        },
        {
            "scene": "江楼骤雨初过，长虹横水，夕照照亮远山",
            "theme": "夏日雨霁登临江楼，由骤雨长虹写胸襟开豁与人生感慨",
        },
        {
            "scene": "端午江上鼓声震水，彩舟竞渡，古祠烟树苍茫",
            "theme": "端午临江观竞渡并怀古，由鼓角江山写忠愤与兴亡之思",
        },
        {
            "scene": "水乡莲叶接天，采莲舟穿过花深处，歌声隔浦相应",
            "theme": "江南水乡采莲，以风荷短棹写青春游赏与明快清欢",
        },
        {
            "scene": "夏日长亭绿阴如盖，蝉声催晚，一叶行舟将解缆",
            "theme": "夏暮长亭送别，由蝉声与行舟写离别、羁旅和后会难期",
        },
        {
            "scene": "山寺松风穿殿，泉声落涧，游人倚石听暮钟",
            "theme": "夏日访山寺避暑，以松风泉响写尘虑澄清与超然之意",
        },
        {
            "scene": "雷雨过后大江涨阔，乱云奔走，落日熔金",
            "theme": "夏雨后临大江远眺，以奔云洪波写江山壮阔与豪迈襟怀",
        },
        {
            "scene": "深夜小院萤火穿帘，凉簟无人，银河低垂",
            "theme": "夏夜独坐小院，由流萤凉簟写相思、孤寂与夜长难眠",
        },
        {
            "scene": "晓风吹过瓜田豆架，村童汲水，白鹭落在浅溪",
            "theme": "夏晓乡野观农事，以田园村居写劳作生趣与朴素安宁",
        },
    ],
    "秋": [
        {
            "scene": "秋夜江楼新凉，疏雨收云，雁影横过远天",
            "theme": "秋夜雨霁登临江楼，由雁影新凉写怀远与旷达澄怀",
        },
        {
            "scene": "中秋月满高台，银汉无声，远近人家灯火相望",
            "theme": "中秋登台问月，以清辉天涯写怀远、团圆之愿与旷达襟抱",
        },
        {
            "scene": "重阳山路菊香满袖，登高回首，古城隐入暮云",
            "theme": "重阳登高怀古，由秋山古城写岁月兴亡与江山之感",
        },
        {
            "scene": "秋江芦白，客舟催发，长亭外暮雨连波",
            "theme": "秋暮江亭送别，由芦花暮雨铺写离别、羁旅与客愁",
        },
        {
            "scene": "桂影移过空庭，帘钩微动，砧声从远巷传来",
            "theme": "秋夜空庭独坐，由桂影砧声写相思、雁书与久别怀人",
        },
        {
            "scene": "稻浪翻金，村舍炊烟初起，牧童横笛归来",
            "theme": "秋日乡野观丰收，以田园农事写村居喜悦与闲适情怀",
        },
        {
            "scene": "江南秋雨轻笼石桥，枫叶逐水，乌篷泊在酒旗边",
            "theme": "江南烟雨中泊舟，以小桥枫叶写水乡旧游与淡远乡愁",
        },
        {
            "scene": "枫林暮色渐深，旧游石径无人，远寺钟声隔谷",
            "theme": "秋日重寻旧游，由枫林暮色写物是人非与含蓄怀人",
        },
        {
            "scene": "边城风急，塞草连天，落日照着归雁与戍楼",
            "theme": "秋日登边楼望江山，以塞草落日写壮志、忧国与未酬之愤",
        },
        {
            "scene": "秋夜孤灯照卷，露滴梧桐，窗外长河渐落",
            "theme": "秋夜独坐听梧桐露声，由孤灯长河写流年与人生感慨",
        },
    ],
    "冬": [
        {
            "scene": "冬夜雪霁，疏梅映月，远寺钟声越过寒江",
            "theme": "冬夜雪后踏月访梅，由清寒孤芳写守志与静定",
        },
        {
            "scene": "雪后群山如洗，大江无际，古城楼堞映着斜阳",
            "theme": "冬日登城怀古，以雪山大江写江山兴亡与豪迈襟怀",
        },
        {
            "scene": "岁暮小院围炉煮酒，窗纸映雪，家书压在灯前",
            "theme": "岁暮围炉读家书，由灯火风雪写思乡、亲情与归期",
        },
        {
            "scene": "寒江驿馆外雪压长亭，客马嘶风，行舟没入暮色",
            "theme": "冬日雪中长亭送别，由驿路寒江写离别与羁旅客愁",
        },
        {
            "scene": "寒江月白，独舟系在石矶，远山沉入无声夜色",
            "theme": "冬夜泊舟寒江，以孤月远山写清寂、澄怀与超然自守",
        },
        {
            "scene": "腊梅初放小园，冰痕未解，暗香穿过竹篱",
            "theme": "腊日小园咏梅，以冰姿冷香写孤芳、坚贞与守志",
        },
        {
            "scene": "雪夜重帘低垂，银烛将残，旧衣仍留故人香气",
            "theme": "冬夜对烛怀人，由残更旧物写相思、孤寂与旧梦",
        },
        {
            "scene": "江南小雪初晴，石桥微湿，乌篷船慢过芦汀",
            "theme": "江南小雪后泛舟，以小桥芦汀写水乡清景与淡远旧游",
        },
        {
            "scene": "山村岁晚，柴门犬吠，儿童踏雪送来新酿",
            "theme": "冬日山村闲居，以田园村居写岁晚人情与朴素清欢",
        },
        {
            "scene": "除夕高楼灯火连城，寒星欲曙，远山渐露青痕",
            "theme": "除夕登楼守岁，由万家灯火写怀远、流年与新岁愿景",
        },
    ],
}

CIPAI_RECOMMENDATIONS = [
    {
        "cipai": "念奴娇",
        "keywords": ("怀古", "古战场", "兴亡", "江山", "豪迈", "历史"),
        "reason": "篇幅开阔、句势雄健，适合铺展山河景象与怀古兴亡之感",
    },
    {
        "cipai": "水调歌头",
        "keywords": ("中秋", "明月", "月夜", "问月", "怀远", "天涯", "旷达"),
        "reason": "声情舒展，适合由月色与远景转入怀远和旷达襟抱",
    },
    {
        "cipai": "雨霖铃",
        "keywords": ("送别", "离别", "长亭", "羁旅", "客愁", "旅愁"),
        "reason": "慢词铺叙充分，适合写临别场景、行程推进与层层客愁",
    },
    {
        "cipai": "一剪梅",
        "keywords": ("相思", "闺愁", "雁书", "红笺", "独坐", "怀人"),
        "reason": "回环婉转，适合细写相思、独处与景物触情",
    },
    {
        "cipai": "卜算子",
        "keywords": ("咏梅", "梅花", "访梅", "孤芳", "坚贞", "守志", "咏物"),
        "reason": "篇制凝练，适合托物寄意并突出孤高自守的精神",
    },
    {
        "cipai": "蝶恋花",
        "keywords": ("惜春", "伤春", "暮春", "花事", "春愁", "春游"),
        "reason": "情景回环、转折婉曲，适合写花事、游赏与惜春心绪",
    },
    {
        "cipai": "忆江南",
        "keywords": ("江南", "烟雨", "小桥", "水乡", "采莲", "吴越"),
        "reason": "篇幅明快凝练，适合摄取江南水乡的鲜明片段",
    },
    {
        "cipai": "鹧鸪天",
        "keywords": ("田园", "村居", "归隐", "农事", "闲居", "乡野"),
        "reason": "近于七言而转折灵活，适合写田园日常与闲适情怀",
    },
    {
        "cipai": "临江仙",
        "keywords": ("登临", "江楼", "秋夜", "夜雨", "远思", "思乡", "澄怀", "人生感慨"),
        "reason": "上下阕转换自然，适合由登临江景推进到远思与人生襟抱",
    },
]

POET_RECOMMENDATIONS = [
    {
        "poet": "苏轼",
        "keywords": ("旷达", "豪迈", "怀古", "江山", "人生", "明月", "超然", "澄怀"),
        "cipai": ("念奴娇", "水调歌头", "临江仙", "江城子"),
        "reason": "视野开阔，善由眼前景物转入人生襟抱，并以旷达收束",
    },
    {
        "poet": "辛弃疾",
        "keywords": ("报国", "壮志", "沙场", "北伐", "忧国", "田园", "村居"),
        "cipai": ("鹧鸪天", "破阵子", "永遇乐", "摸鱼儿"),
        "reason": "情绪张力强，能以豪语、冷笔和顿挫承载壮志或田园寄意",
    },
    {
        "poet": "李清照",
        "keywords": ("闺愁", "相思", "孤寂", "惜花", "残春", "雁书"),
        "cipai": ("一剪梅", "声声慢", "如梦令", "醉花阴"),
        "reason": "善以细微感官、日常器物和时间痕迹含蓄映照心绪",
    },
    {
        "poet": "柳永",
        "keywords": ("送别", "离别", "羁旅", "长亭", "都市", "旅愁", "客愁"),
        "cipai": ("雨霖铃", "八声甘州", "望海潮"),
        "reason": "长于铺叙羁旅与离别，能沿时序和行程层层推进情感",
    },
    {
        "poet": "姜夔",
        "keywords": ("咏梅", "梅花", "访梅", "清寒", "疏影", "冷香", "空城", "孤芳"),
        "cipai": ("暗香", "疏影", "扬州慢", "卜算子"),
        "reason": "气质清空骚雅，适合以疏淡清寒的意象寄托幽独品格",
    },
    {
        "poet": "晏殊",
        "keywords": ("惜春", "伤春", "宴游", "流年", "闲愁", "小园"),
        "cipai": ("浣溪沙", "蝶恋花", "清平乐"),
        "reason": "语言温润、对偶工稳，适合从花时与寻常景物写轻愁和流年",
    },
    {
        "poet": "欧阳修",
        "keywords": ("游赏", "清欢", "春游", "明快", "恋情"),
        "cipai": ("蝶恋花", "采桑子", "生查子"),
        "reason": "笔调清丽亲切，适合在自然游赏和浅近叙写中含蓄见情",
    },
    {
        "poet": "秦观",
        "keywords": ("江南", "烟雨", "烟水", "暮色", "驿路", "阻隔", "凄迷", "怀人"),
        "cipai": ("满庭芳", "鹊桥仙", "踏莎行"),
        "reason": "风格柔婉凄迷，善用暮色、烟水和空间阻隔承载离愁",
    },
    {
        "poet": "周邦彦",
        "keywords": ("旧游", "物候", "梦境", "精雅"),
        "cipai": ("兰陵王", "六丑", "苏幕遮"),
        "reason": "章法精密，适合交织物候、旧游与眼前景并作含蓄转换",
    },
]

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


def clean_optional(value: str | None) -> str | None:
    cleaned = value.strip() if value else ""
    return cleaned or None


def current_season(today: date | None = None) -> str:
    month = (today or date.today()).month
    if month in (2, 3, 4):
        return "春"
    if month in (5, 6, 7):
        return "夏"
    if month in (8, 9, 10):
        return "秋"
    return "冬"


def seasonal_theme(today: date | None = None) -> dict[str, Any]:
    current = today or date.today()
    season = current_season(current)
    candidates = SEASONAL_CONTEXTS[season]
    selected_index = (current.day - 1) % len(candidates)
    selected = candidates[selected_index]
    return {
        "date": current.isoformat(),
        "season": season,
        "scene": selected["scene"],
        "theme": selected["theme"],
        "selectedIndex": selected_index + 1,
        "candidates": candidates,
        "basis": "按公历月份近似古典四时，并按日期在当季候选中稳定轮换：二至四月为春、五至七月为夏、八至十月为秋、十一月至次年一月为冬",
    }


def keyword_score(text: str, keywords: tuple[str, ...]) -> tuple[int, list[str]]:
    matched = [keyword for keyword in keywords if keyword in text]
    return sum(len(keyword) for keyword in matched), matched


def recommend_cipai(theme: str) -> dict[str, Any]:
    candidates = []
    for order, rule in enumerate(CIPAI_RECOMMENDATIONS):
        score, matched = keyword_score(theme, rule["keywords"])
        if score:
            candidates.append((score, -order, rule, matched))
    if not candidates:
        return {
            "value": "浣溪沙",
            "matchedKeywords": [],
            "reason": "主题未命中特定题材规则，采用篇制均衡、适配题材较广的《浣溪沙》",
        }
    _, _, selected, matched = max(candidates, key=lambda item: (item[0], item[1]))
    return {
        "value": selected["cipai"],
        "matchedKeywords": matched,
        "reason": selected["reason"],
    }


def recommend_poet(theme: str, cipai: str) -> dict[str, Any]:
    candidates = []
    for order, rule in enumerate(POET_RECOMMENDATIONS):
        theme_score, matched = keyword_score(theme, rule["keywords"])
        cipai_score = 4 if cipai in rule["cipai"] else 0
        score = theme_score + cipai_score
        if score:
            candidates.append((score, -order, rule, matched, bool(cipai_score)))
    if not candidates:
        return {
            "value": "晏殊",
            "matchedKeywords": [],
            "matchedCipai": False,
            "reason": "主题与词牌未命中特定风格规则，采用温润圆融、题材适应面较广的晏殊风格",
        }
    _, _, selected, matched, matched_cipai = max(candidates, key=lambda item: (item[0], item[1]))
    return {
        "value": selected["poet"],
        "matchedKeywords": matched,
        "matchedCipai": matched_cipai,
        "reason": selected["reason"],
    }


def resolve_composition_request(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    input_theme = clean_optional(args.theme)
    input_cipai = clean_optional(args.cipai)
    input_poet = clean_optional(args.poet)

    if input_theme:
        theme = input_theme
        theme_inference = {"inferred": False, "value": theme, "reason": "用户指定"}
    else:
        generated = seasonal_theme()
        theme = generated["theme"]
        theme_inference = {
            "inferred": True,
            "value": theme,
            "date": generated["date"],
            "season": generated["season"],
            "scene": generated["scene"],
            "selectedIndex": generated["selectedIndex"],
            "candidates": generated["candidates"],
            "reason": generated["basis"],
        }

    if input_cipai:
        cipai = input_cipai
        cipai_inference = {"inferred": False, "value": cipai, "reason": "用户指定"}
    else:
        recommended_cipai = recommend_cipai(theme)
        cipai = recommended_cipai["value"]
        cipai_inference = {"inferred": True, **recommended_cipai}

    if input_poet:
        poet = input_poet
        poet_inference = {"inferred": False, "value": poet, "reason": "用户指定"}
    else:
        recommended_poet = recommend_poet(theme, cipai)
        poet = recommended_poet["value"]
        poet_inference = {"inferred": True, **recommended_poet}

    request = {
        "cipai": cipai,
        "variant": args.variant,
        "theme": theme,
        "poet": poet,
        "rhyme": args.rhyme,
        "rhymes": args.rhymes,
    }
    inference = {
        "theme": theme_inference,
        "cipai": cipai_inference,
        "poet": poet_inference,
    }
    return request, inference


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


def rhyme_series_sort_key(series: str) -> tuple[int, str]:
    match = re.fullmatch(r"rhyme-(\d+)", series)
    return (int(match.group(1)), series) if match else (sys.maxsize, series)


def parse_rhyme_constraints(
    rhyme_spec: str | None,
    rhymes_spec: str | None,
    series_order: list[str],
    rhyme_data: dict[str, Any],
    unihan_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if rhyme_spec and rhymes_spec:
        raise SystemExit("--rhyme 与 --rhymes 不可同时使用")
    if rhyme_spec and len(series_order) > 1:
        raise SystemExit(
            f"该词牌含 {len(series_order)} 个韵系，请改用 --rhymes 分组指定，例如："
            '--rhymes "rhyme-1=第三部;rhyme-2=第七部"'
        )
    if (rhyme_spec or rhymes_spec) and not series_order:
        raise SystemExit("该词牌没有可指定的韵系")

    raw_by_series: dict[str, str] = {}
    if rhyme_spec and series_order:
        raw_by_series[series_order[0]] = rhyme_spec
    if rhymes_spec:
        for assignment in re.split(r"[;；]+", rhymes_spec):
            assignment = assignment.strip()
            if not assignment:
                continue
            match = re.fullmatch(r"(rhyme-\d+)\s*[=＝]\s*(.+)", assignment)
            if not match:
                raise SystemExit(
                    f"无法解析多韵系约束“{assignment}”；应写为 rhyme-N=韵部，并用分号分隔"
                )
            series, spec = match.group(1), match.group(2).strip()
            if series not in series_order:
                available = "、".join(series_order)
                raise SystemExit(f"词谱中没有韵系“{series}”；可用韵系：{available}")
            if series in raw_by_series:
                raise SystemExit(f"韵系“{series}”被重复指定")
            raw_by_series[series] = spec

    return {
        series: parse_rhyme_constraint(raw_by_series.get(series), rhyme_data, unihan_data)
        for series in series_order
    }


def compatible_rhyme_groups(
    rhyme_data: dict[str, Any],
    required_tones: set[str],
) -> list[str]:
    result = []
    for group in rhyme_data["groups"]:
        available_tones = {section["tone"] for section in group["sections"]}
        if required_tones <= available_tones:
            result.append(group["id"])
    return result


def select_nonadjacent_rhyme_groups(
    series_order: list[str],
    candidates: dict[str, list[str]],
) -> dict[str, str] | None:
    """为连续韵系选定韵部；相邻韵系不同，非相邻韵系可复用。"""
    selected: dict[str, str] = {}

    def visit(index: int, previous_group: str | None) -> bool:
        if index >= len(series_order):
            return True
        series = series_order[index]
        options = candidates.get(series, [])
        if not options:
            return visit(index + 1, None)
        for group_id in options:
            if group_id == previous_group:
                continue
            selected[series] = group_id
            if visit(index + 1, group_id):
                return True
            selected.pop(series, None)
        return False

    return selected if visit(0, None) else None


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
    request, inference = resolve_composition_request(args)
    pattern = select_pattern(cipu, request["cipai"], args.variant, rhyme_data, unihan_data)
    request["cipai"] = pattern["name"]
    request["variant"] = pattern["variant"]
    tones = required_rhyme_tones(pattern)
    series_order = sorted(tones, key=rhyme_series_sort_key)
    constraints = parse_rhyme_constraints(args.rhyme, args.rhymes, series_order, rhyme_data, unihan_data)
    suggested_groups = template_rhyme_groups(pattern)
    banks: dict[str, list[dict[str, Any]]] = {}
    compatibility_issues: list[dict[str, Any]] = []
    candidate_groups: dict[str, list[str]] = {}

    for series in series_order:
        constraint = constraints[series]
        if constraint["allowed_groups"]:
            group_ids = constraint["allowed_groups"]
        elif constraint["mode"] == "modern-final":
            group_ids = []
        else:
            preferred = suggested_groups.get(series, [])
            fallback = compatible_rhyme_groups(rhyme_data, tones[series])
            group_ids = list(dict.fromkeys([*preferred, *fallback]))
        candidate_groups[series] = group_ids

    selected_groups = select_nonadjacent_rhyme_groups(series_order, candidate_groups)
    if selected_groups is None:
        compatibility_issues.append(
            {
                "type": "adjacent_rhyme_group",
                "series": series_order,
                "candidateGroups": candidate_groups,
                "message": "无法为各韵系选择满足“相邻韵系不同韵部”的组合；请调整分组韵部",
            }
        )
        selected_groups = {}

    for series, series_tones in tones.items():
        constraint = constraints[series]
        banks[series] = []
        selected_group = selected_groups.get(series)
        group_ids = [selected_group] if selected_group else candidate_groups[series][:4]
        for group_id in group_ids:
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
        "request": request,
        "inference": inference,
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
        "rhymeConstraint": (
            constraints[series_order[0]]
            if len(series_order) == 1
            else {"mode": "per-series", "raw": args.rhymes}
        ),
        "rhymeConstraints": constraints,
        "suggestedRhymeGroups": suggested_groups,
        "selectedRhymeGroups": selected_groups,
        "requiredRhymeTones": {k: sorted(v) for k, v in tones.items()},
        "rhymeBanks": banks,
        "compatibilityIssues": compatibility_issues,
        "generationChecklist": [
            "先按行数、每句字数和平仄骨架拟句，再润色意象与章法",
            "同一 rhyme_series 的句末字须落在同一《词林正韵》韵部",
            "不同韵系可以复用韵部，但相邻 rhyme_series 不得使用同一韵部",
            "韵部字优先只用于韵脚；非韵脚位置尽量避开各韵系所用韵部",
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
    required_tones = required_rhyme_tones(pattern)
    series_order = sorted(required_tones, key=rhyme_series_sort_key)
    constraints = parse_rhyme_constraints(args.rhyme, args.rhymes, series_order, rhyme_data, unihan_data)
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

    actual_group_candidates: dict[str, list[str]] = {}
    for series, endings in series_endings.items():
        constraint = constraints[series]
        known_sets = [set(x["groups"]) for x in endings if x["groups"]]
        common = set.intersection(*known_sets) if known_sets else set()
        if len(known_sets) != len(endings):
            errors.append({"type": "unknown_rhyme", "series": series, "endings": endings, "message": "部分韵脚无法在《词林正韵》中定位"})
        elif not common:
            errors.append({"type": "rhyme_group", "series": series, "endings": endings, "message": "同一韵系的句末字不在同一韵部"})
        allowed_groups = set(constraint["allowed_groups"])
        if allowed_groups and common and not (common & allowed_groups):
            errors.append({"type": "specified_rhyme_group", "series": series, "commonGroups": sorted(common), "allowedGroups": sorted(allowed_groups)})
        constrained_common = common & allowed_groups if common & allowed_groups else common
        actual_group_candidates[series] = sorted(constrained_common)
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

    selected_groups = select_nonadjacent_rhyme_groups(series_order, actual_group_candidates)
    if selected_groups is None:
        errors.append(
            {
                "type": "adjacent_rhyme_group",
                "series": series_order,
                "candidateGroups": actual_group_candidates,
                "message": "相邻韵系使用了同一《词林正韵》韵部；不同韵系可隔组复用，但相邻组必须换韵部",
            }
        )
        selected_groups = {}
    resolved_series_groups = {
        series: {group_id}
        for series, group_id in selected_groups.items()
    }

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

    for series, groups in resolved_series_groups.items():
        if not groups:
            continue
        occurrences: list[dict[str, Any]] = []
        for line_number, (line_text, line_spec) in enumerate(zip(lines, pattern_lines), start=1):
            for position, (char, pos_spec) in enumerate(zip(line_text, line_spec["positions"]), start=1):
                if rhyme_series(pos_spec):
                    continue
                readings = cilin_readings(char, rhyme_data["characters"], unihan_data["characters"])
                matched = [
                    {
                        "group": reading["rhymeGroup"],
                        "section": reading["section"],
                        "tone": tone_symbol(reading["tone"]),
                    }
                    for reading in readings
                    if reading["rhymeGroup"] in groups
                ]
                if matched:
                    occurrences.append(
                        {
                            "line": line_number,
                            "position": position,
                            "char": char,
                            "matchedReadings": matched,
                        }
                    )
        if occurrences:
            warnings.append(
                {
                    "type": "non_rhyme_same_group",
                    "series": series,
                    "rhymeGroups": sorted(groups),
                    "occurrences": occurrences,
                    "message": "非韵脚位置使用了本韵系同韵部字；建议优先换用其他韵部字，多音字可结合语义核定",
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
        "rhymeConstraints": constraints,
        "selectedRhymeGroups": selected_groups,
        "note": "本工具确定性校验字数、平仄、分组押韵及相邻韵系换部，并提示非韵脚同韵部字与重复用字；多音字语境、主题贴合度、词人风格和语义质量仍需人工或模型复核。",
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
    p_prepare.add_argument("--cipai", help="词牌名；省略时根据主题推荐")
    p_prepare.add_argument("--variant", help="变体名或模板 ID；省略时采用大众常用体式（如临江仙格八），其余回退正体")
    p_prepare.add_argument("--theme", help="主题；省略时根据当前季节生成场景和主题")
    p_prepare.add_argument("--poet", help="拟仿词人；省略时根据主题和词牌推荐")
    prepare_rhyme = p_prepare.add_mutually_exclusive_group()
    prepare_rhyme.add_argument("--rhyme", help="单韵系词牌的韵部、韵目、指定韵脚字或现代拼音韵母")
    prepare_rhyme.add_argument("--rhymes", help='多韵系约束，如 "rhyme-1=第三部;rhyme-2=第七部"')
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
    validate_rhyme = p_validate.add_mutually_exclusive_group()
    validate_rhyme.add_argument("--rhyme", help="与 prepare 相同的单韵系韵脚约束")
    validate_rhyme.add_argument("--rhymes", help="与 prepare 相同的多韵系约束")
    p_validate.set_defaults(func=validate)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
