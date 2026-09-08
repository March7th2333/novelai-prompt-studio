# NovelAI Prompt Studio · NovelAI 提示词工作室

把画面想法变成可复制、可检查、可迭代的 NovelAI 提示词。**不是出图 API 客户端，也不是自动堆砌标签的模板。**

Version: **1.0.0** · Python **3.10+** · Runtime dependencies: **none** · License: **MIT** (original code and documentation)

## 能做什么

支持构思生成、保留约束的精修、参考图分层拆解、三个方向的风格探索，以及对照图片和提示词的小步诊断。默认给一套主方案；不自动生成图片、不登录 NovelAI、不消耗 Anlas。

核心流程是：明确硬约束 → 设计主体/构图/光影 → 区分 Base 与 Character Prompts → 编写 UC → 检查显式与隐含冲突 → 给出下一轮观察点。静态脚本仅检查可确定的结构；审美与实际模型效果需要出图反馈。

## 安装

解压源码包，在项目目录运行：

```sh
python3 tools/install_skill.py
```

默认安装到 `~/.agents/skills/novelai-prompt-studio`，目标已存在时拒绝覆盖。安装到项目内：

```sh
python3 tools/install_skill.py --dest /absolute/path/to/project/.agents/skills
```

这安装的是本地 Agent Skill，不会把它发布到插件目录。支持本地 skills 的 Codex/桌面宿主可以加载；见 [安装说明](docs/INSTALL.md)。

## 开始使用

在支持 `$skill` 调用的宿主中：

```text
$novelai-prompt-studio
帮我设计一张黑底粉蓝油画感的人像，平衡模式。
保留短粉发和虹膜内部上粉下蓝的渐变，背景别太花。
目标模型 V4.5 Full，Quality Tags 关闭，UC 预设 None。
```

也可以说：“只改背景，保留人物、服装和动作”“检查这段 NovelAI 提示词”“对照这张出图分析为什么材质太塑料”。没有参考图时不会编造图中内容。

## 本地检查

```sh
python3 skills/novelai-prompt-studio/scripts/lint_prompt.py \
  skills/novelai-prompt-studio/examples/portrait.json

python3 skills/novelai-prompt-studio/scripts/diff_prompt.py \
  skills/novelai-prompt-studio/examples/portrait.json \
  skills/novelai-prompt-studio/examples/portrait-refined.json

python3 -m unittest discover -s tests -v
python3 tools/build_release.py
```

`lint_prompt.py` 支持 `--format json` 和 `--strict`；`diff_prompt.py` 检查旧版本声明的 `locked_paths`，并给出完整差异。输入是本项目的审阅记录格式，**不是 NovelAI 官方 API payload 或官方导入文件**。

## 内容

| 路径 | 用途 |
|---|---|
| `skills/novelai-prompt-studio/SKILL.md` | 可直接加载的核心工作流程 |
| `references/`（skill 内） | 模型能力快照、语法、构图、诊断、来源 |
| `presets/`（skill 内） | 可选角色与风格草案，默认不启用 |
| `examples/`（skill 内） | 人像、精修、双人、标题海报记录 |
| `tests/` | 离线自动测试；不等于实际出图验证 |
| `tools/` | 安装、白名单打包、受保护的 GitHub 发布工具 |
| `docs/` | 安装、发布、验证与维护说明 |

## 模型与证据边界

模型能力快照核验日期为 **2026-09-08**。V3 / V4 / V4.5 / V5 分开记录；未知模型不会回退成“已支持”。V5 的完整质量词与 UC 预设快照未获得同等完整资料，明确标为未知。自带 UC 规则只覆盖有依据的风险词，**不是完整预设复刻**。工具会报告覆盖范围，绝不把“没发现”写成“保证没有冲突”。

不声称拥有精确 NovelAI tokenizer；不以字符数冒充 token 数。不保证锁脸、固定 seed 的像素级复现，或任何提示词必然成功。见 [来源与证据](skills/novelai-prompt-studio/references/SOURCES.md)。

## GitHub 发布

见 [发布说明](docs/PUBLISHING.md)。脚本默认只打印计划；必须显式传入 `--execute` 才写入 GitHub。默认私有仓库，拒绝复用已有仓库、拒绝跨账号写入，不做 force push，不修改全局 Git 配置。

公开发布源码不等于提交到 ChatGPT 插件目录。发布工具需要运行环境里已有 `git`、`gh` 和有效 GitHub 登录；本项目不会收集或存储令牌。

## English summary

A bilingual, instruction-first Agent Skill for composing and iterating NovelAI prompts. Includes version-aware capabilities, bounded prompt linting, immutable-path diffs, opt-in creative presets, offline tests, safe local installation, reproducible allowlisted archives, and an explicit GitHub publishing helper. No image-generation API, paid actions, private reference corpus, or credentials are bundled.

## License and attribution

Original code and original documentation are under the MIT license. NovelAI is a third-party product; this project is not affiliated with or endorsed by NovelAI. Linked documentation, third-party names, and fictional characters retain their respective rights. No source images or proprietary tutorials are redistributed.
