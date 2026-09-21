# 仓库指南

`trans-lc-pilot` 是一个 Workbuddy Expert Plugin：LangChain 驱动的文档处理专家，通过小型 CLI 对外服务。保持改动精简、类型完备、以环境变量驱动。

## 项目分层

```
.codebuddy-plugin/plugin.json   ← Plugin manifest（Workbuddy 扫描入口）
agents/<name>.md                ← Expert 人设 + system prompt（YAML frontmatter + Markdown）
skills/<skill-name>/SKILL.md    ← 每个 skill 一个目录
avatars/                        ← 专家头像（可选）
src/trans_lc_pilot/             ← Python 引擎
pyproject.toml                  ← 构建 + CLI 入口（[project.scripts]）
AGENTS.md                       ← 本文档：开发协作指南
```

## 协作约定

**先澄清，再动手。** 当请求含糊，或一个决策有多个站得住脚的选项时，停下来先问——不要随机选一个。列出选项和各自的权衡，由人类决定。这适用于命名、模块布局、文件格式、依赖选择、范围界定，不仅仅是代码提交。

如果仓库本身已经有答案（现有风格、之前的决策、`git log`），直接据此回答；只在真正面临岔路口时才提问。

当决策不能等时，在回复中显式说明：选了什么、有哪些备选、日后改回来需要付出什么代价。

## Skills

项目的 skills 存放在 `skills/<skill-name>/SKILL.md`，与任何特定 agent 的目录约定无关。每个 skill 描述一项可用能力、适用场景、执行步骤和注意事项。当前提供：

- **split-docx** — 按标题拆分 docx 为多个 HTML，附带索引页

新增 skill 时，在 `skills/` 下新建 kebab-case 目录，内含一份 `SKILL.md`（YAML frontmatter + Markdown 正文），然后更新本节清单。

## 项目结构与模块组织

项目采用 `src/` 布局的 Python 包。所有应用代码位于 `src/trans_lc_pilot/` 下：

- `config.py` — 冻结的 `Settings` dataclass，通过 `python-dotenv` 从 `.env` 加载。
- `tools.py` — `@tool` 定义以及 `default_tools()` 注册表。
- `agent.py` — `build_llm`、`build_agent` 和 `run_once`；持有 system prompt。
- `cli.py` — argparse 入口和 REPL 循环（脚本名：`trans-lc-pilot`）。

顶层文件：`pyproject.toml`（Hatchling 构建、项目元数据、脚本入口点）、`uv.lock`（锁定的依赖）、`README.md`、`.env.example`、`.gitignore`。

## 构建、测试与开发命令

一切用 `uv`；不要手工编辑 `uv.lock` 或直接调用 `pip`。

- `uv sync` — 将依赖安装/锁定到本地 `.venv`。
- `uv run trans-lc-pilot "prompt"` — 一次性调用 agent。
- `uv run trans-lc-pilot` — 启动交互式 REPL。
- 首次运行前：`cp .env.example .env`，然后填写 `OPENAI_API_KEY`。

目前尚未接入测试运行器；见下方*测试指南*。

## 编码风格与命名约定

- Python ≥ 3.12。每个模块以 `from __future__ import annotations` 开头。
- 所有公开函数和 dataclass 字段都要有类型注解；优先使用现代语法（`str | None`、`list[str]`）。
- 模块、函数、变量用 `snake_case`；类用 `PascalCase`（如 `Settings`）。模块文件名用简短名词（`agent.py`、`tools.py`）。
- 函数尽量短小且保持纯函数性质；副作用集中在 `cli.py`。
- 分支用 `if … elif … else` 链表达。
  - 优先这样写：

    ```python
    if kind == "docx":
        reader = docx_to_docproj
    elif kind == "md":
        reader = md_to_docproj
    else:
        raise ValueError(f"unsupported kind: {kind}")
    return reader(path)
    ```

  - 不要这样写：

    ```python
    if kind == "docx":
        return docx_to_docproj(path)
    if kind == "md":
        return md_to_docproj(path)
    raise ValueError(f"unsupported kind: {kind}")
    ```

- 已配置 `ruff` 作为 linter（见 `pyproject.toml` 中的 `[tool.ruff]`）。
  运行 `uv run ruff check .` 检查，`uv run ruff check --fix .` 应用安全的自动修复。公开函数、类和模块必须带 Google 风格 docstring（pydocstyle `D` 规则，`convention = "google"`）。
  尚未配置 formatter —— 保持 4 空格缩进、双引号字符串、多行字面量末尾加逗号。

## 测试指南

目前还没有提交测试。添加时放在 `tests/` 下，镜像 `src/trans_lc_pilot/` 的目录结构（如 `tests/test_tools.py`），使用 `pytest`。测试命名 `test_<unit>_<behavior>`，并保持封闭——mock 掉 LLM，绝不要用真实 API key 联网。运行方式：`uv run pytest`。

## 提交与 Pull Request 规范

仓库目前还没有提交记录，因此采用轻量约定：简短祈使语气的主题（≤ 72 字符），可选的正文解释*为什么*。建议前缀：`feat:`、`fix:`、`chore:`、`docs:`、`refactor:`。
PR 应描述用户可见的变更、关联跟踪 issue，并注明影响环境或模型的改动（如新增必需的 `OPENAI_*` 变量）。

**审查要求：** 每次提交在落地前必须经过人工审查和明确批准——不允许无人值守或自动提交。Agent 和 bot 可以准备提交（暂存文件、起草消息、展示 diff），但**只有当人类在当前回合明确要求时**（如"请提交当前变更"、"commit these changes"）才可以执行 `git commit`。否则，交由审查者手动执行 `git commit` / merge。

## 安全与配置提示

- 绝不提交 `.env`；它已被 git 忽略。只有 `.env.example` 属于仓库。
- 运行时需要 `OPENAI_API_KEY` —— 缺失时 `build_llm` 会抛出异常。
- `OPENAI_BASE_URL` 可指向兼容的本地或托管端点；留空则使用 OpenAI。