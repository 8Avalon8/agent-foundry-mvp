from __future__ import annotations

from typing import Any, Dict


JSONDict = Dict[str, Any]


def render_builder_web_app(config: JSONDict) -> str:
    """Return the built-in single-page Web/A2UI Agent Builder."""
    payload = _json_dumps(config).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Agent Foundry Builder</title>
<style>
  :root {{
    color-scheme: light;
    --bg: #f4f6f8;
    --panel: #ffffff;
    --line: #d8dee8;
    --text: #17202e;
    --muted: #637083;
    --accent: #176b5b;
    --accent-strong: #0f4f43;
    --warn: #9a6200;
    --danger: #b42318;
    --soft: #edf7f4;
    --shadow: 0 12px 34px rgba(20, 32, 52, 0.08);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  button, input, textarea, select {{ font: inherit; }}
  button {{
    border: 1px solid #1f2937;
    background: #1f2937;
    color: #fff;
    border-radius: 6px;
    padding: 8px 12px;
    cursor: pointer;
  }}
  button.secondary {{ background: #fff; color: #1f2937; }}
  button.accent {{ background: var(--accent); border-color: var(--accent); }}
  button:disabled {{ opacity: .55; cursor: not-allowed; }}
  textarea, input[type="text"] {{
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 10px 12px;
    background: #fff;
    color: var(--text);
  }}
  textarea {{ min-height: 96px; resize: vertical; }}
  .app-shell {{ min-height: 100vh; display: flex; flex-direction: column; }}
  header {{
    border-bottom: 1px solid var(--line);
    background: rgba(255,255,255,.92);
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  .topbar {{
    max-width: 1440px;
    margin: 0 auto;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }}
  .brand {{ display: flex; flex-direction: column; gap: 2px; min-width: 220px; }}
  .brand h1 {{ margin: 0; font-size: 20px; line-height: 1.2; }}
  .brand span {{ color: var(--muted); font-size: 13px; }}
  .status-pill {{
    border: 1px solid var(--line);
    background: #fff;
    border-radius: 999px;
    padding: 6px 10px;
    color: var(--muted);
    font-size: 13px;
    white-space: nowrap;
  }}
  main {{
    width: 100%;
    max-width: 1440px;
    margin: 0 auto;
    padding: 18px 20px 28px;
    display: grid;
    grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
    gap: 18px;
    flex: 1;
  }}
  .panel {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: var(--shadow);
  }}
  .sidebar {{ display: flex; flex-direction: column; min-height: calc(100vh - 96px); }}
  .composer, .chat, .result, .board {{ padding: 16px; }}
  .composer {{ border-bottom: 1px solid var(--line); }}
  .row {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .row > * {{ flex: 0 0 auto; }}
  .chat {{ display: flex; flex-direction: column; gap: 10px; overflow: auto; }}
  .msg {{
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px 12px;
    background: #fff;
    white-space: pre-wrap;
    line-height: 1.45;
  }}
  .msg.user {{ background: #f7fafc; }}
  .msg.agent {{ background: var(--soft); border-color: #b8ddd2; }}
  .msg.error {{ color: var(--danger); border-color: #f0b8b3; background: #fff7f6; }}
  .hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
  .board-shell {{ min-height: calc(100vh - 96px); overflow: auto; }}
  .board {{ display: flex; flex-direction: column; gap: 12px; }}
  .card {{
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #fff;
    padding: 14px;
  }}
  .card h2, .card h3 {{ margin: 0 0 8px; }}
  .card h2 {{ font-size: 18px; }}
  .card h3 {{ font-size: 15px; }}
  .summary-list {{ margin: 8px 0 0; padding-left: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
  .preset {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfe; }}
  .preset.recommended {{ border-color: var(--accent); background: var(--soft); }}
  .stage-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .stage {{
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 12px;
    color: var(--muted);
  }}
  .stage.current {{ border-color: var(--accent); color: var(--accent-strong); background: var(--soft); }}
  .stage.completed {{ background: #f1f5f9; color: #334155; }}
  .choice-list {{ display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }}
  .choice {{
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px;
    display: grid;
    grid-template-columns: 22px 1fr;
    gap: 10px;
    cursor: pointer;
    background: #fff;
  }}
  .choice:hover {{ border-color: #93a3b8; }}
  .choice small {{ display: block; color: var(--muted); margin-top: 3px; line-height: 1.45; }}
  .meta {{ color: var(--muted); font-size: 13px; }}
  .risk {{ color: var(--warn); }}
  pre {{
    margin: 8px 0 0;
    white-space: pre-wrap;
    overflow: auto;
    border-radius: 8px;
    background: #101826;
    color: #eef2f7;
    padding: 12px;
    max-height: 320px;
  }}
  .result {{ border-top: 1px solid var(--line); display: none; }}
  .result.visible {{ display: block; }}
  .result dl {{ display: grid; grid-template-columns: 86px 1fr; gap: 8px; margin: 10px 0 0; }}
  .result dt {{ color: var(--muted); }}
  .result dd {{ margin: 0; overflow-wrap: anywhere; }}
  @media (max-width: 920px) {{
    main {{ grid-template-columns: 1fr; }}
    .sidebar, .board-shell {{ min-height: auto; }}
    .topbar {{ align-items: flex-start; flex-direction: column; }}
  }}
</style>
</head>
<body>
<div class="app-shell">
  <header>
    <div class="topbar">
      <div class="brand">
        <h1>Agent Foundry Builder</h1>
        <span>自然语言澄清 + A2UI 决策面板 + Agent 工程生成</span>
      </div>
      <div class="row">
        <span class="status-pill" id="providerStatus">provider: loading</span>
        <span class="status-pill" id="sessionStatus">未开始</span>
      </div>
    </div>
  </header>
  <main>
    <section class="panel sidebar">
      <div class="composer">
        <label class="hint" for="goalInput">描述你想创建的 Agent</label>
        <textarea id="goalInput">我想做一个 SVN Review Agent，帮我审查 diff</textarea>
        <div class="row" style="margin-top:10px">
          <button class="accent" id="startBtn">开始设计</button>
          <button class="secondary" id="newBtn">新建会话</button>
          <button class="secondary" id="mockExampleBtn">填入写作示例</button>
        </div>
        <div style="margin-top:14px">
          <label class="hint" for="replyInput">继续用自然语言补充</label>
          <input id="replyInput" type="text" placeholder="例如：都按推荐 / 重点看 bug 和测试影响" />
          <div class="row" style="margin-top:8px">
            <button id="replyBtn">发送补充</button>
            <button class="secondary" id="recommendedBtn">都按推荐</button>
          </div>
        </div>
        <p class="hint" id="helpText">默认使用服务端配置的 provider。OpenAI 模式需要 OPENAI_API_KEY。</p>
      </div>
      <div class="chat" id="chat"></div>
      <div class="result" id="result"></div>
    </section>
    <section class="panel board-shell">
      <div class="board" id="board">
        <div class="card">
          <h2>等待开始</h2>
          <p class="meta">输入目标后，系统会返回一轮 Agent 回复和可交互 A2UI 决策面板。</p>
        </div>
      </div>
    </section>
  </main>
</div>
<script type="application/json" id="server-config">{payload}</script>
<script>
const config = JSON.parse(document.getElementById('server-config').textContent);
let current = {{ session_id: null, response: null, busy: false }};

const el = (id) => document.getElementById(id);
const board = el('board');
const chat = el('chat');
const resultPanel = el('result');

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}

function setBusy(next) {{
  current.busy = next;
  for (const id of ['startBtn', 'replyBtn', 'recommendedBtn']) el(id).disabled = next;
}}

function setStatus(text) {{
  el('sessionStatus').textContent = text;
}}

function addMessage(role, text) {{
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}}

async function api(path, payload) {{
  const res = await fetch(path, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload)
  }});
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}}

async function loadHealth() {{
  try {{
    const res = await fetch('/health');
    const data = await res.json();
    el('providerStatus').textContent = `provider: ${{data.provider}}${{data.model ? ' / ' + data.model : ''}}`;
    if (data.provider_error) addMessage('error', data.provider_error);
  }} catch (err) {{
    el('providerStatus').textContent = 'provider: unknown';
  }}
}}

async function startConversation(goal) {{
  if (!goal.trim()) return;
  setBusy(true);
  addMessage('user', goal);
  try {{
    const data = await api('/conversation/start', {{ user_goal: goal }});
    applyResponse(data);
  }} catch (err) {{
    addMessage('error', err.message);
  }} finally {{
    setBusy(false);
  }}
}}

async function sendReply(reply) {{
  if (!current.session_id) {{
    addMessage('error', '请先开始一个会话。');
    return;
  }}
  if (!reply.trim()) return;
  setBusy(true);
  addMessage('user', reply);
  try {{
    const data = await api('/conversation/respond', {{ session_id: current.session_id, natural_language_reply: reply }});
    applyResponse(data);
  }} catch (err) {{
    addMessage('error', err.message);
  }} finally {{
    setBusy(false);
  }}
}}

async function sendAction(event) {{
  if (!current.session_id) return;
  const actionEvent = {{ ...event, session_id: current.session_id }};
  setBusy(true);
  try {{
    const data = await api('/conversation/respond', {{ session_id: current.session_id, action_event: actionEvent }});
    applyResponse(data);
  }} catch (err) {{
    addMessage('error', err.message);
  }} finally {{
    setBusy(false);
  }}
}}

function applyResponse(data) {{
  current.response = data;
  current.session_id = data.session_id;
  addMessage('agent', data.assistant_message || data.message || data.status);
  setStatus(`${{data.status}} · ${{data.session_id || ''}}`);
  if (data.a2ui_tree) renderA2UI(data.a2ui_tree);
  renderResult(data);
}}

function renderResult(data) {{
  if (data.status !== 'completed') {{
    resultPanel.classList.remove('visible');
    resultPanel.innerHTML = '';
    return;
  }}
  const agent = data.agent_spec_summary?.agent || {{}};
  const artifacts = data.agent_spec_summary?.output?.artifacts || [];
  resultPanel.classList.add('visible');
  resultPanel.innerHTML = `
    <h2>已生成 Agent</h2>
    <dl>
      <dt>名称</dt><dd>${{escapeHtml(agent.name || '')}}</dd>
      <dt>类型</dt><dd>${{escapeHtml(agent.type || '')}}</dd>
      <dt>Agent</dt><dd>${{escapeHtml(data.agent_dir || '')}}</dd>
      <dt>Dry run</dt><dd>${{escapeHtml(data.run_dir || '')}}</dd>
      <dt>产物</dt><dd>${{escapeHtml(artifacts.join(', '))}}</dd>
    </dl>
  `;
}}

function renderA2UI(tree) {{
  board.innerHTML = '';
  board.appendChild(renderNode(tree.root, tree));
}}

function renderNode(node, tree) {{
  if (!node) return document.createTextNode('');
  const type = node.type;
  if (type === 'Stack') {{
    const wrap = document.createElement('div');
    wrap.className = 'board';
    for (const child of node.children || []) wrap.appendChild(renderNode(child, tree));
    return wrap;
  }}
  if (type === 'AgentSummaryCard') return renderSummary(node);
  if (type === 'PresetCardGroup') return renderPresets(node);
  if (type === 'StageProgress') return renderStages(node);
  if (type === 'DecisionCard') return renderDecision(node, tree);
  if (type === 'ImpactDiff') return renderImpact(node);
  if (type === 'ConfirmBar') return renderConfirm(node);
  return renderUnknown(node);
}}

function card(title) {{
  const section = document.createElement('section');
  section.className = 'card';
  if (title) section.innerHTML = `<h2>${{escapeHtml(title)}}</h2>`;
  return section;
}}

function renderSummary(node) {{
  const props = node.props || {{}};
  const section = card(props.title || 'Agent');
  section.innerHTML += `<p class="meta">${{escapeHtml(props.agent_type || '')}} · <span class="risk">${{escapeHtml(props.risk_level || '')}}</span></p>`;
  const ul = document.createElement('ul');
  ul.className = 'summary-list';
  for (const item of props.summary || []) {{
    const li = document.createElement('li');
    li.textContent = item;
    ul.appendChild(li);
  }}
  section.appendChild(ul);
  return section;
}}

function renderPresets(node) {{
  const section = card('推荐组合');
  const grid = document.createElement('div');
  grid.className = 'grid';
  for (const preset of node.props?.presets || []) {{
    const item = document.createElement('article');
    item.className = 'preset' + (preset.recommended ? ' recommended' : '');
    item.innerHTML = `<h3>${{escapeHtml(preset.title)}}</h3><p class="meta">${{escapeHtml(preset.description || '')}}</p>`;
    grid.appendChild(item);
  }}
  section.appendChild(grid);
  return section;
}}

function renderStages(node) {{
  const section = card('阶段');
  const list = document.createElement('div');
  list.className = 'stage-list';
  for (const stage of node.props?.stages || []) {{
    const pill = document.createElement('span');
    pill.className = 'stage ' + stage.status;
    pill.textContent = `${{stage.id}}: ${{stage.status}}`;
    list.appendChild(pill);
  }}
  section.appendChild(list);
  return section;
}}

function renderDecision(node, tree) {{
  const props = node.props || {{}};
  const section = card(props.title || props.question_id || '决策');
  const decision = tree?.state?.decisions?.[props.question_id];
  section.innerHTML += `<p class="meta">推荐：${{escapeHtml(props.recommendation?.value || '')}} ${{escapeHtml(props.recommendation?.reason || '')}}</p>`;
  if (decision) section.innerHTML += `<p class="meta">当前选择：${{escapeHtml(Array.isArray(decision.value) ? decision.value.join(', ') : decision.value)}}</p>`;
  if (props.affects?.length) section.innerHTML += `<p class="meta">影响：${{escapeHtml(props.affects.join(', '))}}</p>`;
  for (const child of node.children || []) section.appendChild(renderInput(child, tree));
  return section;
}}

function renderInput(node, tree) {{
  if (node.type === 'ChoiceGroup') return renderChoiceGroup(node, tree, false);
  if (node.type === 'MultiChoiceGroup') return renderChoiceGroup(node, tree, true);
  if (node.type === 'TextInputWithHint') return renderTextInput(node);
  return renderUnknown(node);
}}

function renderChoiceGroup(node, tree, multi) {{
  const props = node.props || {{}};
  const wrap = document.createElement('div');
  wrap.className = 'choice-list';
  const decision = tree?.state?.decisions?.[props.state_key];
  const decisionValue = decision?.value;
  const selected = new Set(decision ? (Array.isArray(decisionValue) ? decisionValue : [decisionValue]) : []);
  for (const option of props.options || []) {{
    const label = document.createElement('label');
    label.className = 'choice';
    const input = document.createElement('input');
    input.type = multi ? 'checkbox' : 'radio';
    input.name = props.state_key;
    input.value = option.id;
    input.checked = selected.has(option.id);
    const requiresInput = Boolean(option.requires_input?.id);
    input.addEventListener('change', () => {{
      if (requiresInput) return;
      const value = multi
        ? Array.from(wrap.querySelectorAll('input:checked')).map((item) => item.value)
        : option.id;
      sendAction({{ action: props.on_change?.action || 'select_option', payload: {{ question_id: props.state_key, value }} }});
    }});
    const text = document.createElement('span');
    text.innerHTML = `<strong>${{escapeHtml(option.label || option.id)}}</strong>${{option.recommended ? ' <small>推荐</small>' : ''}}<small>${{escapeHtml(option.description || option.tradeoff || '')}}</small>`;
    label.appendChild(input);
    label.appendChild(text);
    wrap.appendChild(label);
    if (requiresInput) {{
      const extra = document.createElement('div');
      extra.className = 'row';
      extra.style.paddingLeft = '32px';
      const extraInput = document.createElement('input');
      extraInput.type = 'text';
      extraInput.dataset.requiredInputId = option.requires_input.id;
      extraInput.dataset.optionId = option.id;
      extraInput.placeholder = option.requires_input.placeholder || '请输入补充信息';
      const apply = document.createElement('button');
      apply.className = 'secondary';
      apply.textContent = '应用';
      apply.addEventListener('click', () => {{
        input.checked = true;
        const value = multi
          ? Array.from(wrap.querySelectorAll('input:checked')).map((item) => item.value)
          : option.id;
        const inputs = {{}};
        for (const field of wrap.querySelectorAll('[data-required-input-id]')) {{
          if (field.value.trim()) inputs[field.dataset.requiredInputId] = field.value.trim();
        }}
        sendAction({{ action: props.on_change?.action || 'select_option', payload: {{ question_id: props.state_key, value, inputs }} }});
      }});
      extra.appendChild(extraInput);
      extra.appendChild(apply);
      wrap.appendChild(extra);
    }}
  }}
  return wrap;
}}

function renderTextInput(node) {{
  const props = node.props || {{}};
  const wrap = document.createElement('div');
  wrap.className = 'choice-list';
  const input = document.createElement('textarea');
  input.placeholder = props.placeholder || '请输入';
  const btn = document.createElement('button');
  btn.textContent = '提交';
  btn.addEventListener('click', () => sendAction({{ action: props.on_change?.action || 'update_text', payload: {{ question_id: props.state_key, value: input.value }} }}));
  wrap.appendChild(input);
  wrap.appendChild(btn);
  return wrap;
}}

function renderImpact(node) {{
  const section = card('Impact Preview');
  const pre = document.createElement('pre');
  pre.textContent = node.props?.diff_text || '';
  section.appendChild(pre);
  const btn = document.createElement('button');
  btn.className = 'secondary';
  btn.textContent = '刷新影响详情';
  btn.addEventListener('click', () => sendAction(node.props?.on_request_detail || {{ action: 'show_impact', payload: {{}} }}));
  section.appendChild(btn);
  return section;
}}

function renderConfirm(node) {{
  const section = card('确认');
  const row = document.createElement('div');
  row.className = 'row';
  for (const action of node.props?.actions || []) {{
    const btn = document.createElement('button');
    btn.className = action.id === 'use_recommended' ? 'accent' : 'secondary';
    btn.textContent = action.label || action.id;
    btn.addEventListener('click', () => sendAction(action.event || {{ action: action.id, payload: {{ stage: node.props?.stage }} }}));
    row.appendChild(btn);
  }}
  section.appendChild(row);
  return section;
}}

function renderUnknown(node) {{
  const section = card(node.type || 'Unknown');
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(node, null, 2);
  section.appendChild(pre);
  return section;
}}

el('startBtn').addEventListener('click', () => startConversation(el('goalInput').value));
el('replyBtn').addEventListener('click', () => {{
  const input = el('replyInput');
  const value = input.value;
  input.value = '';
  sendReply(value);
}});
el('recommendedBtn').addEventListener('click', () => sendReply('都按推荐'));
el('newBtn').addEventListener('click', () => {{
  current = {{ session_id: null, response: null, busy: false }};
  chat.innerHTML = '';
  resultPanel.innerHTML = '';
  resultPanel.classList.remove('visible');
  board.innerHTML = '<div class="card"><h2>等待开始</h2><p class="meta">输入目标后，系统会返回一轮 Agent 回复和可交互 A2UI 决策面板。</p></div>';
  setStatus('未开始');
}});
el('mockExampleBtn').addEventListener('click', () => {{
  el('goalInput').value = '我想做一个微信公众号写作 Agent，帮我把素材变成文章';
}});

loadHealth();
</script>
</body>
</html>"""


def _json_dumps(data: JSONDict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)
