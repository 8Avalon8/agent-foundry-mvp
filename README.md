# Agent Foundry MVP — LLM Upgrade

这是一个可运行的 **Agent Builder / Agent 蓝图生成器** MVP。

当前版本已经支持两种模式：

```text
offline 模式：规则式模板、可测试、无需 API Key
LLM 模式：LLM 负责意图理解、设计草案、动态问题、自然语言决策更新和 dry run 内容生成
```

核心链路：

```text
自然语言需求
  → Intent Parser / LLM Intent Parser
  → Pre-Spec Decision Board
  → 用户选择或自然语言补充
  → PreSpecSession
  → Agent Design Card
  → AgentSpec v0.1
  → Agent 工程文件
  → Deterministic or LLM Dry Run
```

---

## 新增：LLM Builder Brain

新增目录：

```text
agent_foundry/llm/
  provider.py          # Provider 抽象，支持 offline / mock / openai
  mock_provider.py     # 本地确定性 Mock LLM，用于测试和 demo
  openai_provider.py   # OpenAI Responses API Provider

agent_foundry/builder/llm_builder.py
  # LLM 意图解析
  # LLM 设计草案生成
  # LLM 动态问题生成
  # 自然语言决策更新
```

LLM 负责“智能判断”：

```text
1. 把一句话需求解析成结构化 Intent
2. 生成个性化 Pre-Spec 设计摘要
3. 推荐合适 preset
4. 补充 0-3 个高价值动态问题
5. 把自然语言补充转成结构化决策
6. 生成 LLM dry run 内容
```

确定性代码仍然负责“安全边界”：

```text
1. AgentSpec 编译
2. tool_policy allow / ask / deny
3. 工程目录生成
4. 高风险动作不自动放行
5. Rule Patch / Style Patch 仍需审批
```

---

## 安装

基础模式：

```bash
pip install -e .
```

使用 OpenAI Provider：

```bash
pip install -e '.[openai]'
# 或
pip install -r requirements-openai.txt
```

设置 API Key：

```bash
export OPENAI_API_KEY="你的 key"
```

可选设置默认模型：

```bash
export AGENT_FOUNDRY_OPENAI_MODEL="gpt-5.5"
```

如果你使用 OpenAI-compatible gateway，可以设置：

```bash
export OPENAI_BASE_URL="https://your-gateway.example/v1"
```

---

## 运行方式

### 1. 离线模板模式

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --format cli
```

### 2. Mock LLM 模式

无需网络和 API Key：

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" \
  --llm-provider mock \
  --stage feedback_protocol \
  --format cli
```

这个模式会展示 LLM 动态追加的问题，例如：

```text
Review 报告需要多强的证据要求？
```

### 3. OpenAI LLM 模式

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" \
  --llm-provider openai \
  --model gpt-5.5 \
  --stage feedback_protocol \
  --format cli
```

也可以使用快捷参数：

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --llm
```

---

## 创建 Agent

### Mock LLM 创建 SVN Review Agent

```bash
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" \
  --llm-provider mock \
  --accept-recommended \
  --dry-run \
  --output ./workspace
```

### 交互式创建和续跑

```bash
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" \
  --interactive \
  --output ./workspace
```

交互输入支持 `question=value`、选项序号和多选逗号分隔。每个阶段确认后会保存 session；之后可以从保存点继续：

```bash
python3 -m agent_foundry.cli new \
  --session ./workspace/.agent_foundry_sessions/session_xxx.json \
  --interactive \
  --output ./workspace
```

### OpenAI 创建 Agent

```bash
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" \
  --llm-provider openai \
  --model gpt-5.5 \
  --accept-recommended \
  --dry-run \
  --output ./workspace
```

生成目录示例：

```text
workspace/
  .agent_foundry_sessions/
    session_xxx.json
    session_xxx_design_card.md
  agents/
    svn-reviewer/
      agent.yaml
      system_prompt.md
      runbook.md
      tool_policy.yaml
      human_feedback.yaml
      memory_policy.yaml
      eval_rubric.yaml
      output_schema.json
      prespec_session.json
      agent_design_card.md
      examples/
      runs/
        dry_run_xxx/
          review_report.md
          findings.json
          test_suggestions.md
          rule_patch_proposal.md
          llm_dry_run_metadata.json
```

---

## 自然语言更新 PreSpecSession

用户可以不用手动找问题 ID，而是直接说：

```bash
python3 -m agent_foundry.cli update-session ./workspace/.agent_foundry_sessions/session_xxx.json \
  "可以读项目上下文，但不能自动写文件；生成 patch 必须让我确认" \
  --llm-provider mock
```

它会更新类似字段：

```text
context_scope = project_search
source_modify_policy = deny
patch_policy = write_patch_ask
```

---

## Dry Run

### 离线 dry run

```bash
python3 -m agent_foundry.cli dry-run ./workspace/agents/svn-reviewer
```

### Review feedback 标签闭环

dry run 会生成 `findings.json`、`feedback_requests.json` 和 `rule_patch_proposal.md`。用户可以提交 finding label，并重新生成候选规则补丁：

```bash
python3 -m agent_foundry.cli feedback ./workspace/agents/svn-reviewer/runs/dry_run_xxx \
  --label F001=accepted \
  --label F002=false_positive \
  --reason F002="该对象由上游工厂保证非空"
```

支持标签：`accepted`、`false_positive`、`too_minor`、`duplicate`、`needs_more_evidence`。规则补丁只会写入 `rule_patch_proposal.md`，不会自动更新长期规则。

### Writing feedback 选题和风格闭环

writing-agent dry run 会生成 `topic_options.md`、`topic_selection_request.json`、`outline.md`、`article.md`、`publish_package.json` 和 `style_rule_patch.md`。用户可以选择选题并提交风格反馈：

```bash
python3 -m agent_foundry.cli writing-feedback ./workspace/agents/wechat-ai-writer/runs/dry_run_xxx \
  --topic 2 \
  --style-feedback "标题更克制一点，多保留真实工作流细节"
```

风格规则只会更新 `style_rule_patch.md` 候选，不会自动写入 `style_rules.md`。

### LLM dry run

```bash
python3 -m agent_foundry.cli dry-run ./workspace/agents/svn-reviewer \
  --llm-provider mock
```

或：

```bash
python3 -m agent_foundry.cli dry-run ./workspace/agents/svn-reviewer \
  --llm-provider openai \
  --model gpt-5.5
```

---

## 当前支持的 Agent 类型

模板层支持：

```text
review-agent
writing-agent
coding-agent
research-agent
automation-agent
monitor-agent
```

MVP 重点验证：

```text
1. SVN Review Agent
2. 微信公众号 / AI 写作 Agent
```

---

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

当前测试覆盖：

```text
1. Mock / OpenAI provider 初始化路径
2. DecisionQuestion / PreSpecSession schema 与 round-trip
3. Decision Graph visible_when 条件分支
4. CLI interactive / saved session resume
5. Impact Preview before/after diff
6. Agent Design Card 阶段分组
7. AgentSpec 安全默认值和 schema 约束
8. 工程文件生成稳定文件集
9. Review / Writing feedback 闭环
10. Runtime Permission Engine approval request
11. Web / A2UI renderer 和 action event protocol
12. UI demo action events -> AgentSpec -> dry run
```

## MVP 验收矩阵

| 验收项 | 命令 | 预期证据 |
| --- | --- | --- |
| 全量单测 | `python3 -m unittest discover -s tests -v` | 测试全部通过。 |
| Review board | `python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --llm-provider mock --stage feedback_protocol --format cli` | 展示动态问题、推荐理由和影响预览。 |
| Review E2E | `python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --accept-recommended --dry-run --output ./workspace` | dry run 下生成 `review_report.md`、`findings.json`、`test_suggestions.md`、`feedback_requests.json`、`rule_patch_proposal.md`。 |
| Writing E2E | `python3 -m agent_foundry.cli new "我想做一个微信公众号写作 Agent，帮我把素材变成文章" --llm-provider mock --accept-recommended --dry-run --output ./workspace` | dry run 下生成 `topic_options.md`、`outline.md`、`article.md`、`publish_package.json`、`style_rule_patch.md`。 |
| 权限安全 | 查看生成的 `agent.yaml` 与 `permission_checks.json` | 高风险动作没有静默 `allow`，长期记忆更新需要审批。 |
| UI Demo | `python3 -m agent_foundry.cli ui-demo --output ./workspace/ui_demo` | 生成 review/writing 两条 action event -> AgentSpec -> dry run demo。 |

---

## 当前边界

这一版仍然不做：

```text
1. 真正 Web UI runtime
2. 真正 A2UI runtime
3. 真正调用 SVN 命令
4. 真正运行 shell 测试
5. 真正接入公众号 / 飞书
6. 自动提交代码
7. 自动发布内容
8. 静默修改长期记忆
```

所有高风险动作仍然应该通过 `tool_policy` 和 `human_feedback` 进入 ask / deny，而不是交给 LLM 自行决定。

---

## 发布到 GitHub

我推荐先发布为私有仓库：

```bash
gh auth login
bash scripts/publish_to_github.sh agent-foundry-mvp private
```

更多说明见 [GITHUB_PUBLISH.md](GITHUB_PUBLISH.md)。
