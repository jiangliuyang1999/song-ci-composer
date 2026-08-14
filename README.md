# song-ci-composer

宋词创作辅助工具 —— 基于《御定词谱》与《词林正韵》，按指定或自动推荐的词牌、主题、韵脚与词人风格创作并校验宋词。

## 特性

- **格律硬约束**：覆盖 826 个词牌、2306 个体式，严格校验句数、字数、平仄与押韵
- **多韵系支持**：支持《减字木兰花》等换韵词牌，相邻韵系自动校验不同部
- **非韵脚避韵**：提示非押韵位置误用的同韵部字，提升声律品质
- **智能推荐**：未指定主题时按季节生成场景，节日期间按概率触发节日主题；未指定词牌/词人时自动推荐
- **确定性校验**：CLI 脚本逐项检查，退出码明确区分通过/错误/警告

## 快速开始

依赖仅需 Python 3.10+，无第三方库。

```bash
# 查看词牌是否收录
python3 scripts/ci_tool.py list --query "浣溪沙"

# 自动生成约束包（主题、词牌、词人风格全自动推荐）
python3 scripts/ci_tool.py prepare

# 指定主题和词牌
python3 scripts/ci_tool.py prepare --cipai "临江仙" --theme "秋夜思乡"

# 校验创作结果
python3 scripts/ci_tool.py validate \
  --cipai "浣溪沙" \
  --rhyme "第七部" \
  --text "第一句，第二句，第三句。第四句，第五句，第六句。"
```

## 多韵系词牌

换韵词牌（如《减字木兰花》）使用 `--rhymes` 按组指定韵部：

```bash
python3 scripts/ci_tool.py prepare \
  --cipai "减字木兰花" \
  --theme "春日送别" \
  --rhymes "rhyme-1=第三部;rhyme-2=第七部;rhyme-3=第三部;rhyme-4=第六部"
```

> 相邻韵系不得使用同一韵部，非相邻韵系可隔组复用。

## 韵脚指定方式

`--rhyme` / `--rhymes` 接受以下格式：

- 部名：`第七部`
- 部 ID：`cilin-07`
- 韵目：`十四寒`
- 句末字：`寒、山、阑`
- 拼音韵母：`an`（新韵）

## 项目结构

```
song-ci-composer/
├── assets/
│   ├── qinding-cipu.json      # 《御定词谱》结构化数据
│   ├── cilin-zhengyun.json    # 《词林正韵》韵部数据
│   └── unihan-readings.json   # 汉字读音数据
├── references/
│   └── style-cards.md         # 常见词人风格特征
├── scripts/
│   └── ci_tool.py             # 核心 CLI 工具
└── SKILL.md                   # 完整使用说明
```

## 校验错误类型

| 错误码 | 说明 |
|--------|------|
| `line_count` / `length` | 句数或字数不符 |
| `tone` | 平仄错误 |
| `rhyme_group` | 同韵系句末字不在同一韵部 |
| `adjacent_rhyme_group` | 相邻韵系使用同一韵部 |
| `non_rhyme_same_group` | 非韵脚位置出现同韵部字（警告） |
| `repeated_rhyme_character` | 韵脚字重复 |
| `repeated_character` | 全文用字重复（警告） |

## 许可证

MIT