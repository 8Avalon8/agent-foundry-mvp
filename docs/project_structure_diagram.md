# Agent Foundry 项目结构图

这张图按当前代码结构整理，重点是让人一眼看清主链路和模块边界。

```mermaid
flowchart TD
    U[用户自然语言需求]

    subgraph Entry[入口层]
        CLI[agent_foundry/cli.py<br/>new board chat-build dry-run serve-web]
        WEB[serve-web<br/>内置网页 Builder]
        API[serve-conversation<br/>Conversation Runtime API]
    end

    subgraph Builder[构建大脑]
        INTENT[Intent Parser<br/>规则式或 LLM]
        BOARD[Decision Board<br/>分阶段问题和推荐项]
        SESSION[PreSpecSession<br/>保存选择和未确认项]
        ORCH[Conversation Orchestrator<br/>自然语言追问和 action event]
        DESIGN[Agent Design Card<br/>阶段性确认卡]
        SPEC[AgentSpec v0.1<br/>正式蓝图]
    end

    subgraph LLM[LLM 层]
        PROVIDER[provider.py<br/>offline mock openai]
        MOCK[mock_provider.py]
        OPENAI[openai_provider.py]
    end

    subgraph Render[表现层]
        CLI_RENDER[CLI / Markdown / HTML]
        WEB_RENDER[web_renderer.py]
        A2UI[a2ui_renderer.py<br/>A2UI tree]
        ACTION[action_protocol.py<br/>点击事件回写 Session]
    end

    subgraph Compile[编译与生成]
        COMPILER[agentspec_compiler.py]
        FILES[file_generator.py]
        AGENT_FILES[Agent 工程文件<br/>agent.yaml system_prompt runbook policies examples]
    end

    subgraph Runtime[运行时]
        DRY[dry_run.py / llm_dry_run.py]
        PERM[permission_engine.py<br/>allow ask deny]
        FEEDBACK[feedback_engine.py]
        MEMORY[memory_engine.py<br/>只生成 patch 提案]
    end

    subgraph Output[输出物]
        AGENTS[workspace 或 generated_examples_llm/agents]
        RUNS[runs/dry_run_*]
        PATCH[rule_patch_proposal.md<br/>style_rule_patch.md]
    end

    U --> CLI
    U --> WEB
    WEB --> API
    CLI --> INTENT
    API --> ORCH

    INTENT --> PROVIDER
    PROVIDER --> MOCK
    PROVIDER --> OPENAI

    INTENT --> BOARD
    BOARD --> SESSION
    SESSION --> ORCH
    ORCH --> ACTION
    ACTION --> SESSION

    SESSION --> CLI_RENDER
    SESSION --> WEB_RENDER
    SESSION --> A2UI

    SESSION --> DESIGN
    DESIGN --> SPEC
    SPEC --> COMPILER
    COMPILER --> FILES
    FILES --> AGENT_FILES

    AGENT_FILES --> DRY
    DRY --> PERM
    DRY --> FEEDBACK
    FEEDBACK --> MEMORY

    AGENT_FILES --> AGENTS
    DRY --> RUNS
    MEMORY --> PATCH
```

## 怎么看

第一层是入口。`agent_foundry/cli.py` 承接 CLI、Web 服务和 Conversation API。

第二层是 Builder。它把一句话需求变成决策面板，再变成 `PreSpecSession`，最后生成 `AgentSpec`。

第三层是表现层。CLI、Web、A2UI 都只是渲染同一个决策状态，再把操作回写成 action event。

第四层是编译与运行时。Compiler 生成 Agent 工程文件，dry run 再读取这些文件跑验证流程。

最重要的边界是：LLM 负责提案和理解，确定性代码负责权限、编译、文件生成和高风险动作边界。
