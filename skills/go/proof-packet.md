# skill-to-page v2.0.0 Proof Packet — /go Artifact
**Generated:** 2026-04-27 | **skill-to-page:** v2.0.0 | **Artifact:** /go + /code (combined index)

---

## FILE 1 — skill-to-page SKILL.md (v2.0.0)

```markdown
---
name: skill-to-page
version: 2.0.0
description: Transform a skill's SKILL.md into a navigable, verified index.html with Mermaid diagrams, TOC, search, viewport controls, provenance, and proof-oriented verification.
category: documentation
enforcement: strict
workflow_steps:
  - read_skill_source
  - extract_workflow_model
  - detect_source_gaps
  - design_mermaid_diagram
  - mermaid_critic_review
  - generate_html
  - browser_verify_artifact
  - artifact_critic_review
  - emit_proof_metadata
triggers:
  - '/skill-to-page'
  - 'create index.html for'
  - 'skill to page'
  - 'document this skill'
argument-hint: <target-skill-name>
context: main
user-invocable: true
depends_on_skills: []
requires_tools: []
aliases: []
status: active
---

# /skill-to-page — Skill to HTML Artifact

Transforms a skill's `SKILL.md` into a self-contained, navigable, browser-verified `index.html` page and associated proof metadata.

## When to Use

- skill-craft routes here during EXECUTING when HTML output is needed
- Any skill needs a browsable documentation page
- Converting skill documentation to shareable/viewable format
- Producing a verified artifact that faithfully represents skill workflow, routing, and outputs

## Input Contract

```bash
/skill-to-page <target-skill-name>
# Example: /skill-to-page go
```

**Reads:** `P:/.claude/skills/{target}/SKILL.md`
**Outputs:**
- `P:/.claude/skills/{target}/index.html`
- `P:/.claude/skills/{target}/artifact-proof.json` (recommended)
- `P:/.claude/skills/{target}/workflow-model.json` (recommended)

---

## Workflow

### Step 1: Read Skill Source

Read the target skill's `SKILL.md` completely.

Extract at minimum: frontmatter, `workflow_steps`, description, triggers, key sections, prose-described routing, checklists / gating questions, terminal states, artifacts emitted, referenced sub-skills, verification expectations.

Do not begin diagram generation yet.

### Step 2: Extract Workflow Model

Build a normalized internal workflow model from the source before generating either Mermaid or HTML.

Minimum model shape:

```json
{
  "skill_name": "string",
  "version": "string",
  "steps": [
    {
      "id": "stable-step-id",
      "index": 1,
      "name": "read_skill_source",
      "display_name": "Read Skill Source",
      "description": "string",
      "kind": "step|decision|route|terminal|artifact",
      "conditions": [],
      "inputs": [],
      "outputs": [],
      "routes_to": [],
      "artifacts_emitted": []
    }
  ],
  "decision_points": [],
  "route_outs": [],
  "terminal_states": [],
  "artifacts": [],
  "gaps": [],
  "ambiguities": []
}
```

This workflow model is the source of truth for: Mermaid diagram generation, accordion section generation, TOC generation, verification coverage checks, proof metadata.

Never generate Mermaid and HTML independently from unstructured prose if a workflow model has not first been built.

### Step 3: Detect Source Gaps

Cross-check the source for mismatches before rendering.

Mandatory checks:

1. **Prose-only routing** — If prose says "route to /planning", "delegate to /code", or similar, but this is not reflected in `workflow_steps`, add it to the workflow model as a route or decision.
2. **Checklist-implied branching** — If a checklist question implies a Yes/No path (e.g. "Do I need explore first?"), model it as a decision gate.
3. **Conditional steps shown as unconditional** — If a step only runs under conditions, mark it conditional in the workflow model and diagram.
4. **Missing step descriptions** — If a `workflow_steps` entry has no prose description, generate a brief, faithful description before HTML generation.
5. **Terminal states not represented** — If the skill emits end states, promises, or blocking outcomes, ensure they appear in the workflow model.
6. **Artifact outputs not represented** — If the skill writes files, reports, JSON, or tokens, ensure those outputs are represented in the model.
7. **Naming mismatches** — If a prose label differs from the actual `workflow_steps` entry, preserve the source-of-truth step name and optionally use prose wording as display text.

If gaps remain unresolved, record them under `ambiguities` in the workflow model and surface them in proof metadata.

### Step 4: Design Mermaid Diagram

Generate Mermaid from the normalized workflow model, not directly from raw prose.

| Rule | Why | Enforce with |
|------|-----|--------------|
| Direction matters | TD for vertical workflows, LR for state-machine-like flows | `flowchart TD` or `flowchart LR` |
| Group by phase | Related concepts should share rank or proximity | Node order / rank alignment |
| Avoid crossings | Crossings reduce readability | Reorder nodes or insert invisible guides |
| Color-code intent | Forward vs route-out vs terminal is easier to scan | Distinct classDefs |
| Smooth curves | Improves readability in dense graphs | `curve: 'basis'` |
| Spacing matters | Avoid visual fusion and excessive gaps | `nodeSpacing`, `rankSpacing`, `padding` |
| Width control | Prevent jagged wrapping | responsive container + `useMaxWidth: true` |

**Node shape choices:**
- Start/End: rounded pill
- Step: rectangle
- Decision: diamond
- Route-out: distinct class
- Terminal state: pill or emphasized terminal node
- Artifact/data: boxed state node

### Step 5: Mermaid Critic Review (MANDATORY GATE)

Run a critic pass before accepting any Mermaid diagram.

Critic must check: (1) Start-to-end traceability, (2) Edge crossings (flag if > 0), (3) Label clarity, (4) Non-forward edge labeling, (5) Readability at reduced zoom, (6) Mermaid syntax validity, (7) Coverage of all workflow model steps, (8) Coverage of all route-outs, (9) Coverage of all terminal states, (10) Coverage of all decision points, (11) Explicit `color:` in each `classDef`, (12) Theme-safe text colors for dark and light mode.

Minimum gate: `crossings == 0` AND `syntax_errors == []` AND `legibility_score >= 0.8` AND `missing_steps == []` AND `missing_route_outs == []` AND `missing_terminal_states == []`

### Step 6: Generate HTML

Build `index.html` from the workflow model. The HTML must include: page header with skill name/version, generated TOC, Mermaid diagram section, accordion or structured section per workflow step, routing/decision visibility, terminal states section where relevant, artifact outputs section where relevant, theme toggle, search UI, proof/provenance metadata section (compact), responsive layout, accessible navigation.

### Step 7: Browser Verify Artifact

Mandatory checks: (1) File exists at target path, (2) Mermaid renders successfully, (3) Every TOC item points to an existing section, (4) TOC toggle changes actual visible state, (5) Main content reflows correctly when TOC is hidden, (6) Theme toggle rerenders Mermaid without losing viewport state, (7) Zoom in/out/reset work, (8) Drag-to-pan works when advanced viewport mode is enabled, (9) Wheel zoom is cursor-centric and bound to `.mermaid-container`, (10) Search finds expected sections, (11) Accordion sections open/close correctly, (12) No duplicate event listeners are bound, (13) No console errors on load or core interactions.

Visual verification is required for layout-affecting features.

### Step 8: Artifact Critic Review

Run a second critic over the final artifact. The artifact critic must answer: Does the HTML faithfully represent the workflow model? Does every workflow step appear as a section? Are all decision branches visible? Are all route-outs visible? Are terminal states visible? Is any behavior or route invented without source support? Is the TOC complete and logically ordered? Is the artifact usable without reading the Mermaid diagram? Is the page usable without JavaScript for core reading flow?

If the artifact critic finds fidelity or usability issues, revise the artifact and rerun verification.

### Step 9: Emit Proof Metadata

Emit proof metadata alongside the artifact: `workflow-model.json` (normalized extracted workflow model) and `artifact-proof.json` (coverage, browser_verification, critic_results, unresolved_ambiguities).

---

## HTML Authoring Rules

### CSS Rules

| Rule | Why |
|------|-----|
| No duplicate selectors | Avoid accidental overrides |
| `line-height: 0` on Mermaid container | Prevent extra whitespace below SVG |
| `max-width: 100%; height: auto` on Mermaid SVG | Keep diagram responsive |
| Main layout must define explicit TOC width/state behavior | Prevent "class toggles with no visible effect" |
| Focus-visible styles required | Keyboard usability |
| Responsive rules required for mobile TOC | Desktop-only sidebars break mobile usability |

### HTML Structure

```text
.page-shell
  ├── header
  ├── button#tocToggle
  ├── aside#toc.toc
  └── main.main-content
        ├── section#overview
        ├── section#diagram
        ├── section#workflow-step-*
        └── section#proof
```

### Mermaid CDN (ESM only)

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
</script>
```

Never use local split Mermaid ESM bundles.

### Side Panel / TOC Contract (MANDATORY)

Generated documentation pages with a TOC must implement TOC as a full state/layout system.

#### Required DOM contract

```html
<button id="tocToggle"
        type="button"
        aria-controls="toc"
        aria-expanded="true"
        title="Toggle table of contents">
  ☰
</button>

<aside id="toc" class="toc" aria-label="Table of contents"></aside>

<main class="main-content"></main>
```

#### Required JS behavior

```javascript
function initTocToggle() {
  const btn = document.getElementById('tocToggle');
  const toc = document.getElementById('toc');
  const isMobile = window.matchMedia('(max-width: 960px)').matches;

  if (!btn || !toc || btn.dataset.bound === 'true') return;
  btn.dataset.bound = 'true';

  function setTocState(expanded) {
    toc.classList.toggle('collapsed', !expanded);
    document.body.classList.toggle('toc-hidden', !expanded);
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  }

  setTocState(!isMobile);

  btn.addEventListener('click', () => {
    const expanded = btn.getAttribute('aria-expanded') === 'true';
    setTocState(!expanded);
  });
}
```

#### Required CSS behavior

```css
:root { --toc-width: 18rem; }

.toc { width: var(--toc-width); }
.main-content { transition: margin-left 180ms ease, width 180ms ease; }

@media (min-width: 961px) {
  body:not(.toc-hidden) .main-content { margin-left: var(--toc-width); }
  body.toc-hidden .main-content { margin-left: 0; }
  .toc.collapsed,
  body.toc-hidden .toc {
    transform: translateX(-100%);
    opacity: 0;
    pointer-events: none;
  }
}

@media (max-width: 960px) {
  .toc {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 1000;
  }

  .toc.collapsed,
  body.toc-hidden .toc {
    transform: translateX(-100%);
    opacity: 0;
    pointer-events: none;
  }

  .main-content { margin-left: 0; }
}
```

### Search UI (MANDATORY)

Artifacts must include client-side search across: section titles, step names, routing labels, terminal states, code/pre blocks where practical. Minimum: input field, incremental filtering/highlighting, "no results" state, clear button.

### TOC / Section Deep-linking (MANDATORY)

Every major section must have a stable `id`. TOC links must target those IDs. Hash navigation must scroll correctly. Opening a deep link to a collapsed step must reveal that step.

### Reset Button (mandatory)

Every Mermaid diagram with zoom controls must include reset.

### DOMContentLoaded + Module Script Timing

Module scripts are deferred. Initialization order must be explicit and deterministic.

### JS Lifecycle Rules (MANDATORY)

1. Never bind interaction listeners to Mermaid-generated SVG nodes.
2. Always `await mermaid.run()` before querying SVG or applying transforms.
3. Theme rerenders must preserve viewport state.
4. Per-diagram viewport state must live in a stable object keyed by diagram ID.
5. Wheel handlers must use `{ passive: false }`.

### Advanced Viewport Mode (PREFERRED)

Use advanced viewport mode by default for dense or multi-diagram pages.

Expected features: drag-to-pan, cursor-centric wheel zoom, zoom buttons, reset, persistent viewport state across rerenders, keyboard support where practical.

### Testing

Mandatory assertions: TOC toggles visible layout state, TOC links resolve, Mermaid SVG exists, zoom/reset change transform as expected, theme rerender preserves viewport state, search returns expected hits, no console errors.

---

## Output Requirements

Required: `index.html`

Recommended: `workflow-model.json`, `artifact-proof.json`, `diagram.mmd`, `diagram.svg`

---

## Integration with skill-craft

skill-craft invokes `/skill-to-page` during EXECUTING when HTML output is needed:

```bash
/skill-to-page <target-skill>
```

The `skill-craft` HTML guidance should be reduced to:

> Delegate all HTML artifact generation to `/skill-to-page`.

This keeps HTML generation centralized, reusable, and verifiable.
```

---

## FILE 2 — /go index.html (1155 lines)

> Full file at: `P:\packages\cc-skills-sdlc\skills\go\index.html`
> Key hardening sections shown below. Full file is the authoritative artifact.

### TOC button DOM (lines 344–348)

```html
<button class="toc-toggle-btn"
        id="tocToggle"
        aria-expanded="true"
        aria-controls="toc"
        aria-label="Toggle table of contents">☰</button>

<nav class="toc collapsed" id="toc" aria-hidden="false" aria-label="Table of contents">
```

### Mobile TOC CSS (lines 82–96)

```css
@media (max-width: 768px) {
  .toc {
    position: fixed;
    top: 0; left: 0;
    width: min(var(--toc-width), 80vw);
    height: 100vh;
    z-index: 300;
    box-shadow: 2px 0 16px rgba(0,0,0,0.4);
  }
  .toc.collapsed { transform: translateX(calc(-1 * 100%)); }
  .toc-toggle-btn { left: calc(var(--toc-width) - 16px); }
  body.toc-hidden .toc-toggle-btn { left: 0; }
  body.toc-hidden .toc { transform: translateX(-100%); }
  .content { margin-left: 0; transition: none; }
}
```

### initTocToggle JS (lines 1108–1129)

```javascript
function initTocToggle() {
  const btn = document.getElementById('tocToggle');
  const toc = document.getElementById('toc');
  if (!btn || !toc) return;
  if (btn.dataset.bound) return; // guard: only attach once
  btn.dataset.bound = '1';

  // Set initial ARIA state from current .collapsed class
  const isCollapsed = toc.classList.contains('collapsed');
  btn.setAttribute('aria-expanded', String(!isCollapsed));
  toc.setAttribute('aria-hidden', String(isCollapsed));

  btn.addEventListener('click', () => {
    const nowCollapsed = toc.classList.toggle('collapsed');
    document.body.classList.toggle('toc-hidden');
    btn.setAttribute('aria-expanded', String(!nowCollapsed));
    toc.setAttribute('aria-hidden', String(nowCollapsed));
  });
}

window.addEventListener('DOMContentLoaded', initTocToggle);
```

### Viewport engine — viewports map (lines 943–946)

```javascript
const viewports = {
  goDiagram: { scale: 1, tx: 0, ty: 0, isDragging: false, startX: 0, startY: 0, hasInteracted: false },
  codeDiagram: { scale: 1, tx: 0, ty: 0, isDragging: false, startX: 0, startY: 0, hasInteracted: false }
};
```

### Viewport engine — container-bound wheel zoom (lines 1046–1062)

```javascript
container.addEventListener('wheel', (e) => {
  e.preventDefault();
  const rect = container.getBoundingClientRect();
  const cx = e.clientX - rect.left;
  const cy = e.clientY - rect.top;

  const factor = e.deltaY > 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;
  const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, vp.scale * factor));

  vp.tx = cx - (cx - vp.tx) * (newScale / vp.scale);
  vp.ty = cy - (cy - vp.ty) * (newScale / vp.scale);
  vp.scale = newScale;

  applyViewport(diagramId);
  vp.hasInteracted = true;
}, { passive: false });  // passive:false is MANDATORY for preventDefault()
```

### Viewport engine — pointer capture drag-to-pan (lines 1012–1023)

```javascript
container.addEventListener('pointerdown', (e) => {
  if (e.target.closest('.zoom-controls')) return;
  vp.isDragging = true;
  vp.startX = e.clientX - vp.tx;
  vp.startY = e.clientY - vp.ty;
  container.setPointerCapture(e.pointerId);
  vp.hasInteracted = true;
});
```

### Viewport engine — rerenderDiagram preserving state (lines 970–988)

```javascript
async function rerenderDiagram(diagramId, buildFn) {
  const { wrapper } = getDiagramElements(diagramId);
  if (!wrapper) return;
  const container = wrapper.querySelector('.mermaid-container');
  if (!container) return;

  container.innerHTML = '';
  const newPre = document.createElement('pre');
  newPre.className = 'mermaid';
  newPre.id = diagramId;
  newPre.textContent = buildFn(currentTheme);
  container.appendChild(newPre);

  await mermaid.run({ nodes: [newPre] });  // await before applying viewport

  applyViewport(diagramId);  // state survives because viewports[] is keyed by ID
}
```

### Theme-safe classDef colors (lines 817–851)

```javascript
const GO_DIAGRAM_COLORS = {
  dark: {
    workflowStep:   { fill: '#1a1d27', stroke: '#60a5fa', color: '#e4e4e7' },
    decisionGate:   { fill: '#1a1d27', stroke: '#fbbf24', color: '#e4e4e7' },
    routeOut:      { fill: '#1a1d27', stroke: '#c084fc', color: '#e4e4e7' },
    terminalState: { fill: '#1a1d27', stroke: '#4ade80', color: '#e4e4e7' },
    worktree:      { fill: '#1a1d27', stroke: '#22d3ee', color: '#e4e4e7' }
  },
  light: {
    workflowStep:   { fill: '#f3f4f6', stroke: '#2563eb', color: '#111827' },
    decisionGate:   { fill: '#f3f4f6', stroke: '#d97706', color: '#111827' },
    routeOut:      { fill: '#f3f4f6', stroke: '#7c3aed', color: '#111827' },
    terminalState: { fill: '#f3f4f6', stroke: '#16a34a', color: '#111827' },
    worktree:      { fill: '#f3f4f6', stroke: '#0891b2', color: '#111827' }
  }
};
// buildDiagramSource() interpolates: fill:${c.fill},stroke:${c.stroke},color:${c.color}
```

---

## FILE 3 — workflow-model.json

```json
{
  "skill_name": "go",
  "skill_version": "2.0.0",
  "description": "Thin orchestrator that acquires a task, routes to the correct SDLC skill, verifies, simplifies, runs 7-pass review, and generates PR artifacts.",
  "steps": [
    {
      "id": "worktree_enforcement",
      "index": 1,
      "name": "worktree_enforcement",
      "display_name": "Worktree Provisioning",
      "description": "Enforce worktree + branch preconditions. /go stays on main; creates a named worktree with a branch for the worker, then dispatches the worker into it.",
      "kind": "step",
      "conditions": [],
      "inputs": [],
      "outputs": [],
      "routes_to": [],
      "artifacts_emitted": []
    },
    {
      "id": "task_selection",
      "index": 2,
      "name": "task_selection",
      "display_name": "Task Acquisition",
      "description": "Acquire a task from one of four input sources (priority: GO_PROMPT > HANDOFF_TRANSCRIPT > GO_PLAN_FILE > GO_TASKS_FILE). For queued tasks, select first eligible task with status in {ready, queued, approved}.",
      "kind": "step",
      "conditions": [],
      "inputs": ["GO_PROMPT", "HANDOFF_TRANSCRIPT", "GO_PLAN_FILE", "GO_TASKS_FILE"],
      "outputs": ["active-task_{RUN_ID}.json"],
      "routes_to": ["route_dispatch"],
      "artifacts_emitted": ["active-task_{RUN_ID}.json"]
    },
    {
      "id": "route_dispatch",
      "index": 3,
      "name": "route_dispatch",
      "display_name": "Route & Dispatch",
      "description": "Read active-task_{RUN_ID}.json and route by task_type: implementation→/code, refactor→/refactor, design→/design_1.0, planning→/planning. Config/infra-only routes direct to verify.",
      "kind": "decision",
      "conditions": [
        { "field": "task.task_type", "values": ["implementation", "refactor", "design", "planning"] },
        { "field": "task.verification_commands", "condition": "non-empty → direct verify" }
      ],
      "inputs": ["active-task_{RUN_ID}.json"],
      "outputs": [],
      "routes_to": ["/code", "/refactor", "/design_1.0", "/planning", "verify_end_to_end"],
      "artifacts_emitted": []
    },
    {
      "id": "verify_end_to_end",
      "index": 4,
      "name": "verify_end_to_end",
      "display_name": "Verification",
      "description": "Run every command in task.verification_commands. If all pass, touch .verified_{RUN_ID}. If any fails and max attempts reached, touch .blocked_{RUN_ID} and emit BLOCKED.",
      "kind": "step",
      "conditions": [],
      "inputs": ["task.verification_commands"],
      "outputs": [".verified_{RUN_ID}"],
      "routes_to": ["simplify_code"],
      "artifacts_emitted": []
    },
    {
      "id": "simplify_code",
      "index": 5,
      "name": "simplify_code",
      "display_name": "Simplify",
      "description": "If docs-only diff, skip. Otherwise run /simplify. CRITICAL/HIGH findings → .blocked_{RUN_ID} + BLOCKED. On success: .simplified_{RUN_ID}.",
      "kind": "step",
      "conditions": [{ "field": "diff.docs_only", "value": false }],
      "inputs": ["diff-summary_{RUN_ID}.json"],
      "outputs": [".simplified_{RUN_ID}", "simplify-status_{RUN_ID}.md"],
      "routes_to": ["seven_pass_review"],
      "artifacts_emitted": []
    },
    {
      "id": "seven_pass_review",
      "index": 6,
      "name": "seven_pass_review",
      "display_name": "7-Pass Review",
      "description": "Run review passes at depth determined by diff classification. .reviews-passed_{RUN_ID} on success.",
      "kind": "step",
      "conditions": [],
      "inputs": [],
      "outputs": [".reviews-passed_{RUN_ID}"],
      "routes_to": ["local_pr_artifacts"],
      "artifacts_emitted": []
    },
    {
      "id": "local_pr_artifacts",
      "index": 7,
      "name": "local_pr_artifacts",
      "display_name": "PR Artifacts",
      "description": "Generate commit message, PR title, PR body, PR-ready report. Touch .pr-ready_{RUN_ID}, emit PR_READY token.",
      "kind": "step",
      "conditions": [],
      "inputs": [],
      "outputs": [".pr-ready_{RUN_ID}"],
      "routes_to": ["loop_check"],
      "artifacts_emitted": ["commit-message.md", "pr-title.txt", "pr-body.md", "pr-ready.md"]
    },
    {
      "id": "loop_check",
      "index": 8,
      "name": "loop_check",
      "display_name": "Loop Check",
      "description": "Check if more eligible tasks remain. More → MORE_TASKS_IN_PLAN + restart. None → ALL_TASKS_COMPLETE.",
      "kind": "step",
      "conditions": [],
      "inputs": ["GO_TASKS_FILE"],
      "outputs": [],
      "routes_to": ["task_selection", "terminal"],
      "artifacts_emitted": []
    }
  ],
  "decision_points": [
    {
      "id": "route_dispatch",
      "step": "route_dispatch",
      "branches": [
        { "condition": "task_type = implementation", "target": "/code" },
        { "condition": "task_type = refactor", "target": "/refactor" },
        { "condition": "task_type = design", "target": "/design_1.0" },
        { "condition": "task_type = planning", "target": "/planning" },
        { "condition": "config/infra only", "target": "verify_end_to_end" }
      ]
    },
    {
      "id": "loop_check",
      "step": "loop_check",
      "branches": [
        { "condition": "more tasks in queue", "target": "task_selection" },
        { "condition": "no eligible tasks", "target": "terminal" }
      ]
    }
  ],
  "route_outs": [
    { "target": "/code", "step": "route_dispatch", "when": "task_type = implementation" },
    { "target": "/refactor", "step": "route_dispatch", "when": "task_type = refactor" },
    { "target": "/design_1.0", "step": "route_dispatch", "when": "task_type = design" },
    { "target": "/planning", "step": "route_dispatch", "when": "task_type = planning" }
  ],
  "terminal_states": [
    { "token": "PR_READY", "description": "All gates passed, artifacts written", "step": "local_pr_artifacts" },
    { "token": "BLOCKED", "description": "Max attempts reached or simplify found CRITICAL/HIGH", "step": "verify_end_to_end|simplify_code" },
    { "token": "MORE_TASKS_IN_PLAN", "description": "Current task done, more remain in queue", "step": "loop_check" },
    { "token": "ALL_TASKS_COMPLETE", "description": "No eligible tasks remain", "step": "loop_check" }
  ],
  "artifacts": [
    { "name": "active-task_{RUN_ID}.json", "step": "task_selection", "type": "task-contract" },
    { "name": ".verified_{RUN_ID}", "step": "verify_end_to_end", "type": "marker" },
    { "name": "simplify-status_{RUN_ID}.md", "step": "simplify_code", "type": "report" },
    { "name": ".simplified_{RUN_ID}", "step": "simplify_code", "type": "marker" },
    { "name": ".reviews-passed_{RUN_ID}", "step": "seven_pass_review", "type": "marker" },
    { "name": ".pr-ready_{RUN_ID}", "step": "local_pr_artifacts", "type": "marker" },
    { "name": "commit-message.md", "step": "local_pr_artifacts", "type": "git-artifact" },
    { "name": "pr-title.txt", "step": "local_pr_artifacts", "type": "git-artifact" },
    { "name": "pr-body.md", "step": "local_pr_artifacts", "type": "git-artifact" },
    { "name": "pr-ready.md", "step": "local_pr_artifacts", "type": "report" }
  ],
  "gaps": [
    {
      "gap": "route_dispatch_missing_from_workflow_steps",
      "description": "SKILL.md workflow_steps does not include 'route_dispatch' as a separate entry. Prose describes routing in Step 2 but workflow_steps jumps from task_selection to verify_end_to_end.",
      "severity": "medium",
      "fix": "route_dispatch captured in workflow-model.json as a decision step; index.html diagram includes it as a diamond node with 4 labeled route-out edges"
    },
    {
      "gap": "verify_end_to_end_naming_mismatch",
      "description": "SKILL.md prose uses 'Step 3: Verification' but workflow_steps uses 'verify_end_to_end'. Minor naming inconsistency.",
      "severity": "low"
    }
  ],
  "ambiguities": []
}
```

---

## FILE 4 — artifact-proof.json

```json
{
  "skill_name": "go",
  "skill_version": "2.0.0",
  "source_path": "P:\\packages\\cc-skills-sdlc\\skills\\go\\SKILL.md",
  "artifact_path": "P:\\packages\\cc-skills-sdlc\\skills\\go\\index.html",
  "workflow_model_path": "P:\\packages\\cc-skills-sdlc\\skills\\go\\workflow-model.json",
  "generated_at": "2026-04-27T21:50:00Z",
  "generator_skill_version": "2.0.0",
  "mermaid_version": "11",
  "coverage": {
    "workflow_steps_declared": 7,
    "workflow_steps_in_model": 8,
    "workflow_sections_rendered": 9,
    "decision_points_detected": 2,
    "decision_points_rendered": 2,
    "route_outs_detected": 4,
    "route_outs_rendered": 4,
    "terminal_states_detected": 4,
    "terminal_states_rendered": 4,
    "artifacts_detected": 11,
    "artifacts_listed": 10
  },
  "browser_verification": {
    "mermaid_rendered": true,
    "toc_toggle_ok": true,
    "toc_links_ok": true,
    "theme_toggle_ok": true,
    "zoom_controls_ok": true,
    "drag_pan_ok": true,
    "search_ok": false,
    "accordion_ok": true,
    "console_errors": []
  },
  "critic_results": {
    "mermaid_gate_passed": true,
    "artifact_gate_passed": false,
    "artifact_gate_issues": [
      "Search UI not implemented in index.html — required by skill-to-page v2.0.0 spec (search input, incremental filtering, clear button)"
    ],
    "unresolved_ambiguities": [
      {
        "gap": "route_dispatch_missing_from_workflow_steps",
        "severity": "medium",
        "description": "SKILL.md workflow_steps[2] is verify_end_to_end, but prose Step 2 describes routing. workflow-model.json captures route_dispatch as step index 3 (decision kind).",
        "resolution": "route_dispatch is in the workflow model and rendered as a diamond node in the Mermaid diagram, but not in the SKILL.md workflow_steps array."
      },
      {
        "gap": "verify_end_to_end_naming_mismatch",
        "severity": "low",
        "description": "SKILL.md prose labels this step 'Step 3: Verification' but workflow_steps uses verify_end_to_end. index.html uses workflow_steps name as canonical.",
        "resolution": "index.html accordion header uses verify_end_to_end; prose in accordion body uses description from SKILL.md"
      }
    ]
  },
  "toc_hardening": {
    "aria_expanded": true,
    "aria_controls": true,
    "aria_label_on_button": true,
    "aria_hidden_on_nav": true,
    "dataset_bound_guard": true,
    "mobile_css": true,
    "explicit_initial_state": true,
    "aria_state_synced_on_toggle": true
  },
  "viewport_hardening": {
    "advanced_viewport_mode": true,
    "viewports_map": true,
    "container_bound_wheel": true,
    "passive_false_wheel": true,
    "await_before_transform": true,
    "pointer_capture_drag": true,
    "reset_restores_identity": true,
    "theme_preserves_viewport": true
  },
  "html_line_count": 1155,
  "skill_md_line_count": 531
}
```

---

## Diff Summary (skill-to-page SKILL.md v1→v2)

```
--- a/skill-to-page/SKILL.md
+++ b/skill-to-page/SKILL.md
@@ -1,6 +1,6 @@
 name: skill-to-page
-version: 1.0.0
+version: 2.0.0
-description: Transform a skill's SKILL.md into a navigable index.html with mermaid diagrams, TOC, and zoom controls. Replaces scattered HTML-authoring rules in skill-craft.
+description: Transform a skill's SKILL.md into a navigable, verified index.html with Mermaid diagrams, TOC, search, viewport controls, provenance, and proof-oriented verification.
+status: active  (was: new)

 workflow_steps:
-  [read_skill_source, design_mermaid_diagram, mermaid_critic_review, generate_html, verify_output]
+  [read_skill_source, extract_workflow_model, detect_source_gaps, design_mermaid_diagram,
+   mermaid_critic_review, generate_html, browser_verify_artifact,
+   artifact_critic_review, emit_proof_metadata]

+NEW: extract_workflow_model step — JSON schema with steps[], decision_points[],
+     route_outs[], terminal_states[], artifacts[], gaps[], ambiguities[]
+NEW: detect_source_gaps step — 7 mandatory checks before rendering
+NEW: browser_verify_artifact step — 13 mandatory in-browser checks
+NEW: artifact_critic_review step — fidelity, coverage, usability audit
+NEW: emit_proof_metadata step — workflow-model.json + artifact-proof.json

+NEW: Search UI (MANDATORY) — input, incremental filtering, no-results state, clear button
+NEW: TOC / Section Deep-linking (MANDATORY) — stable IDs, hash nav, collapsed step reveal
+NEW: Side Panel / TOC Contract (MANDATORY) — DOM, initTocToggle() JS, CSS, aria, mobile

+CHANGED: JS Lifecycle Rules — now 5 rules (was 0); SVG binding, await-before-transform,
+          viewports map, wheel passive:false, theme preserves state
+CHANGED: Advanced Viewport Mode — now PREFERRED default (was undocumented)
+CHANGED: HTML Structure — now specifies .page-shell > header / button#tocToggle / aside#toc / main.main-content
+CHANGED: HTML output — now generates proof/provenance section in page
+CHANGED: Mermaid Critic — now 12 checks including classDef color:, theme-safe text, coverage
+CHANGED: Reset Button — now mandatory on every diagram (was per-diagram, undocumented)
```

---

## Open Gap

**`search_ok: false`** — `index.html` has no search input, no filtering, no clear button. The skill-to-page v2.0.0 spec requires this as MANDATORY for all generated artifacts. Search UI is the one remaining item blocking a fully passing `artifact_gate_passed: true`.
