const board = document.querySelector("#board");
const detail = document.querySelector("#detail");
const summary = document.querySelector("#summary");
const refresh = document.querySelector("#refresh");
const search = document.querySelector("#search");
const showArchived = document.querySelector("#showArchived");
const statusFilters = document.querySelector("#statusFilters");
const viewSwitch = document.querySelector("#viewSwitch");
const boardControls = document.querySelector("#boardControls");
const boardView = document.querySelector("#boardView");
const maintenanceView = document.querySelector("#maintenanceView");
const maintenanceRefresh = document.querySelector("#maintenanceRefresh");
const maintenanceStats = document.querySelector("#maintenanceStats");
const maintenanceCandidates = document.querySelector("#maintenanceCandidates");
const maintenancePreview = document.querySelector("#maintenancePreview");
const retentionDays = document.querySelector("#retentionDays");
const cleanupDryRun = document.querySelector("#cleanupDryRun");
const cleanupConfirm = document.querySelector("#cleanupConfirm");
const checkpointDb = document.querySelector("#checkpointDb");
const vacuumDb = document.querySelector("#vacuumDb");

const DEFAULT_VISIBLE_STATUSES = ["planning", "in_progress", "review", "blocked", "completed"];
const STATUS_ORDER = [...DEFAULT_VISIBLE_STATUSES, "archived"];

const STATUS_LABELS = {
  planning: "规划中",
  in_progress: "执行中",
  review: "检查中",
  blocked: "已阻塞",
  completed: "已完成",
  archived: "已归档",
};

const STATUS_HINTS = {
  planning: "准备上下文",
  in_progress: "实现推进",
  review: "检查验收",
  blocked: "等待决策",
  completed: "完成待归档",
  archived: "历史归档",
};

const PATTERN_LABELS = {
  generic: "通用流程",
  fan_out: "扇出协作",
  pipeline: "流水线",
  human_loop: "人工确认",
};

const state = {
  boardData: { columns: [] },
  selectedTaskId: "",
  searchText: "",
  status: "all",
  view: "board",
  cleanupToken: "",
};

async function getJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function postJson(path) {
  const response = await fetch(path, { method: "POST", headers: { Accept: "application/json" } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
  return payload;
}

function text(value, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function statusLabel(status) {
  return STATUS_LABELS[status] || text(status);
}

function patternLabel(pattern) {
  return PATTERN_LABELS[pattern] || text(pattern);
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return text(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function createElement(tag, className = "", content = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== "") element.textContent = content;
  return element;
}

function allTasks(data) {
  return (data.columns || []).flatMap((column) =>
    (column.tasks || []).map((task) => ({ ...task, status: task.status || column.status })),
  );
}

function countByStatus(tasks, status) {
  if (status === "all") {
    return tasks.filter((task) => DEFAULT_VISIBLE_STATUSES.includes(task.status)).length;
  }
  return tasks.filter((task) => task.status === status).length;
}

function renderStatusFilters(tasks) {
  statusFilters.querySelectorAll("button").forEach((button) => {
    const status = button.dataset.status;
    const label = button.dataset.label;
    button.textContent = `${label} ${countByStatus(tasks, status)}`;
    button.classList.toggle("active", state.status === status);
  });
}

function matchesSearch(task) {
  const query = state.searchText.trim().toLowerCase();
  if (!query) return true;
  const fields = [
    task.id,
    task.title,
    task.priority,
    task.assignee,
    statusLabel(task.status),
    patternLabel(task.pattern),
  ];
  return fields.some((field) => text(field, "").toLowerCase().includes(query));
}

function matchesStatus(task) {
  if (state.status === "archived") return task.status === "archived";
  if (state.status !== "all") return task.status === state.status && task.status !== "archived";
  const taskArchived = task.status === "archived";
  if (taskArchived) return showArchived.checked;
  return DEFAULT_VISIBLE_STATUSES.includes(task.status);
}

function activeStatuses() {
  if (state.status === "archived") return [];
  if (state.status !== "all") return [state.status];
  return DEFAULT_VISIBLE_STATUSES;
}

function showArchiveHistory() {
  return state.status === "archived" || (state.status === "all" && showArchived.checked);
}

function archivedTasks(tasks) {
  return tasks.filter((task) => task.status === "archived" && matchesSearch(task));
}

function taskCard(task) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `task priority-${task.priority || "P2"} status-${task.status}`;
  button.dataset.taskId = task.id;
  button.setAttribute("aria-pressed", task.id === state.selectedTaskId ? "true" : "false");
  if (task.id === state.selectedTaskId) button.classList.add("selected");

  const head = createElement("span", "task-head");
  const title = createElement("span", "task-title", task.title || task.id);
  const badge = createElement("span", "status-badge", statusLabel(task.status));
  head.append(title, badge);

  const meta = createElement("span", "task-meta");
  const progress = task.child_total ? ` · 子任务 ${task.child_done}/${task.child_total}` : "";
  meta.textContent = `${patternLabel(task.pattern)} · ${text(task.priority, "P2")} · ${text(task.assignee)}${progress}`;

  const id = createElement("span", "task-id", text(task.id));
  button.append(head, meta, id);
  button.addEventListener("click", () => loadDetail(task.id));
  return button;
}

function renderColumn(status, tasks) {
  const section = createElement("section", `column status-column status-${status}`);
  const heading = createElement("div", "column-heading");
  const title = createElement("h2", "", statusLabel(status));
  const count = createElement("span", "column-count", String(tasks.length));
  const hint = createElement("p", "column-hint", STATUS_HINTS[status] || "");
  heading.append(title, count);
  section.append(heading, hint);

  if (tasks.length === 0) {
    section.append(createElement("p", "empty-state", "暂无匹配任务"));
    return section;
  }

  for (const task of tasks) section.append(taskCard(task));
  return section;
}

function archiveCard(task) {
  const card = taskCard(task);
  card.classList.add("archive-card");
  return card;
}

function renderArchiveHistory(tasks) {
  const section = createElement("section", "archive-history");
  const heading = createElement("div", "archive-heading");
  heading.append(
    createElement("div", "", "历史归档"),
    createElement("span", "column-count", String(tasks.length)),
  );
  section.append(heading, createElement("p", "column-hint", "按最近任务顺序展示，点击可查看详情"));

  if (tasks.length === 0) {
    section.append(createElement("p", "empty-state", "暂无匹配归档任务"));
    return section;
  }

  const list = createElement("div", "archive-grid");
  for (const task of tasks) list.append(archiveCard(task));
  section.append(list);
  return section;
}

function renderBoard(data) {
  state.boardData = data || { columns: [] };
  const tasks = allTasks(state.boardData);
  const visibleActive = tasks.filter(
    (task) => task.status !== "archived" && matchesStatus(task) && matchesSearch(task),
  );
  const visibleArchived = showArchiveHistory() ? archivedTasks(tasks) : [];
  const visibleCount = visibleActive.length + visibleArchived.length;
  const archivedCount = tasks.filter((task) => task.status === "archived").length;

  renderStatusFilters(tasks);
  board.classList.toggle("archive-view", state.status === "archived");
  board.classList.toggle("with-archive-history", showArchiveHistory() && state.status !== "archived");
  board.replaceChildren();

  for (const status of activeStatuses()) {
    const columnTasks = visibleActive.filter((task) => task.status === status);
    board.append(renderColumn(status, columnTasks));
  }

  if (showArchiveHistory()) board.append(renderArchiveHistory(visibleArchived));

  if (state.view === "board") {
    summary.textContent = `显示 ${visibleCount} 个任务 · 归档 ${archivedCount} 个`;
  }
}

function detailSection(title, children) {
  const section = createElement("section", "detail-section");
  section.append(createElement("h3", "", title));
  if (Array.isArray(children)) {
    section.append(...children);
  } else {
    section.append(children);
  }
  return section;
}

function detailRow(label, value) {
  const item = createElement("div", "detail-row");
  item.append(createElement("span", "", label), createElement("strong", "", text(value)));
  return item;
}

function renderBasics(data) {
  const task = data.task || {};
  return detailSection("基础信息", [
    detailRow("任务 ID", task.id),
    detailRow("产物目录", task.artifact_dir),
    detailRow("状态", statusLabel(task.status)),
    detailRow("模式", patternLabel(task.pattern)),
    detailRow("优先级", task.priority),
    detailRow("负责人", task.assignee),
    detailRow("父任务", task.parent_id),
    detailRow("子任务数", String((data.children || []).length)),
  ]);
}

function renderAuditTrail(audit) {
  const entries = audit || [];
  if (entries.length === 0) {
    return detailSection("审计记录", createElement("p", "empty-state", "暂无审计记录"));
  }

  const timeline = createElement("div", "timeline");
  for (const entry of entries) {
    const item = createElement("div", "timeline-item");
    const fromStatus = entry.from_status ? statusLabel(entry.from_status) : "创建";
    const transition = `${fromStatus} 至 ${statusLabel(entry.to_status)}`;
    item.append(
      createElement("strong", "", transition),
      createElement("span", "", `${text(entry.operator)} · ${formatTime(entry.created_at)}`),
    );
    if (entry.reason) item.append(createElement("p", "", entry.reason));
    timeline.append(item);
  }
  return detailSection("审计记录", timeline);
}

function renderChildren(children) {
  const rows = children || [];
  if (rows.length === 0) {
    return detailSection("子任务", createElement("p", "empty-state", "暂无子任务"));
  }

  const list = createElement("div", "compact-list");
  for (const child of rows) {
    const item = createElement("div", "compact-item");
    item.append(
      createElement("strong", "", child.title || child.id),
      createElement("span", "", `${statusLabel(child.status)} · ${patternLabel(child.pattern)} · ${text(child.assignee)}`),
      createElement("span", "muted", child.artifact_dir || child.id),
    );
    list.append(item);
  }
  return detailSection("子任务", list);
}

function renderAgentRuns(agentRuns) {
  const rows = agentRuns || [];
  if (rows.length === 0) {
    return detailSection("代理运行", createElement("p", "empty-state", "暂无代理运行"));
  }

  const list = createElement("div", "compact-list");
  for (const run of rows) {
    const item = createElement("div", "compact-item");
    item.append(
      createElement("strong", "", `${text(run.agent_type)} · ${text(run.status)}`),
      createElement("span", "", text(run.host_context_key, "无宿主上下文")),
      createElement("span", "muted", `${formatTime(run.created_at)} / ${formatTime(run.closed_at)}`),
    );
    list.append(item);
  }
  return detailSection("代理运行", list);
}

function renderActiveBlock(activeBlock) {
  if (!activeBlock) {
    return detailSection("阻塞状态", createElement("p", "empty-state", "暂无阻塞"));
  }

  return detailSection("阻塞状态", [
    detailRow("原因", activeBlock.reason),
    detailRow("阻塞时间", formatTime(activeBlock.blocked_at)),
    detailRow("决策", activeBlock.decision),
    detailRow("决策人", activeBlock.decided_by),
  ]);
}

function revealDetail() {
  detail.classList.add("visible");
  if (window.matchMedia("(max-width: 900px)").matches) {
    detail.scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

function renderDetail(data) {
  const task = data.task || {};
  const header = createElement("div", "detail-title");
  header.append(
    createElement("p", "eyebrow", "任务详情"),
    createElement("h2", "", task.title || task.id || "未命名任务"),
  );
  detail.replaceChildren(
    header,
    renderBasics(data),
    renderActiveBlock(data.activeBlock),
    renderChildren(data.children),
    renderAgentRuns(data.agentRuns),
    renderAuditTrail(data.audit),
  );
  revealDetail();
}

async function loadDetail(id) {
  state.selectedTaskId = id;
  renderBoard(state.boardData);
  detail.replaceChildren(createElement("p", "detail-loading", "正在加载任务详情..."));
  revealDetail();

  try {
    renderDetail(await getJson(`/api/task/${encodeURIComponent(id)}`));
  } catch (error) {
    detail.replaceChildren(createElement("p", "detail-error", `详情加载失败：${error.message}`));
  }
}

async function loadBoard() {
  try {
    renderBoard(await getJson("/api/board"));
  } catch (error) {
    summary.textContent = `看板加载失败：${error.message}`;
  }
}

function renderMaintenanceStats(payload) {
  const rows = [
    ["DB 大小", `${payload.db_bytes || 0} B`],
    ["WAL 大小", `${payload.wal_bytes || 0} B`],
    ["runtime_context", payload.row_counts?.runtime_context || 0],
    ["runtime_session", payload.row_counts?.runtime_session || 0],
    ["dashboard_process", payload.row_counts?.dashboard_process || 0],
    ["待清理", Object.values(payload.cleanup_candidates || {}).reduce((sum, value) => sum + Number(value || 0), 0)],
  ];
  maintenanceStats.replaceChildren(
    ...rows.map(([label, value]) => {
      const item = createElement("div", "maintenance-stat");
      item.append(createElement("span", "", label), createElement("strong", "", String(value)));
      return item;
    }),
  );
  const candidates = payload.cleanup_candidates || {};
  const candidateRows = [
    ["已关闭 runtime", candidates.closed_runtime_contexts || 0],
    ["孤立 session", candidates.orphan_runtime_sessions || 0],
    ["失效看板进程", candidates.stale_dashboard_processes || 0],
  ];
  maintenanceCandidates.replaceChildren(
    createElement("h3", "", "清理候选"),
    ...candidateRows.map(([label, value]) => {
      const row = createElement("div", "candidate-row");
      row.append(createElement("span", "", label), createElement("strong", "", String(value)));
      return row;
    }),
  );
  summary.textContent = `数据库维护 · 待清理 ${Object.values(candidates).reduce((sum, value) => sum + Number(value || 0), 0)} 项`;
}

async function loadMaintenanceStats() {
  try {
    renderMaintenanceStats(await getJson("/api/maintenance/db/stats"));
  } catch (error) {
    maintenancePreview.textContent = `维护概览加载失败：${error.message}`;
  }
}

function retentionQuery() {
  return `retention_days=${encodeURIComponent(retentionDays.value || "30")}`;
}

function renderMaintenancePreview(payload) {
  maintenancePreview.textContent = JSON.stringify(payload, null, 2);
}

async function runCleanupDryRun() {
  state.cleanupToken = "";
  cleanupConfirm.disabled = true;
  try {
    const payload = await postJson(`/api/maintenance/db/cleanup?dry_run=true&${retentionQuery()}`);
    state.cleanupToken = payload.confirmation_token || "";
    cleanupConfirm.disabled = !state.cleanupToken;
    renderMaintenancePreview(payload);
    await loadMaintenanceStats();
  } catch (error) {
    maintenancePreview.textContent = `扫描失败：${error.message}`;
  }
}

async function runCleanupConfirm() {
  if (!state.cleanupToken) return;
  try {
    const payload = await postJson(
      `/api/maintenance/db/cleanup?confirm=${encodeURIComponent(state.cleanupToken)}&${retentionQuery()}`,
    );
    state.cleanupToken = "";
    cleanupConfirm.disabled = true;
    renderMaintenancePreview(payload);
    await loadMaintenanceStats();
  } catch (error) {
    maintenancePreview.textContent = `清理失败：${error.message}`;
  }
}

async function runMaintenanceAction(path, label) {
  try {
    renderMaintenancePreview(await postJson(path));
    await loadMaintenanceStats();
  } catch (error) {
    maintenancePreview.textContent = `${label} 失败：${error.message}`;
  }
}

function setView(view) {
  state.view = view;
  const maintenanceMode = view === "maintenance";
  boardView.hidden = maintenanceMode;
  statusFilters.hidden = maintenanceMode;
  boardControls.hidden = maintenanceMode;
  maintenanceView.hidden = !maintenanceMode;
  document.body.classList.toggle("maintenance-mode", maintenanceMode);
  viewSwitch.querySelectorAll("button[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  if (maintenanceMode) {
    loadMaintenanceStats();
  } else {
    renderBoard(state.boardData);
  }
}

search.addEventListener("input", () => {
  state.searchText = search.value;
  renderBoard(state.boardData);
});

showArchived.addEventListener("change", () => {
  renderBoard(state.boardData);
});

statusFilters.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-status]");
  if (!button) return;
  state.status = button.dataset.status;
  renderBoard(state.boardData);
});

refresh.addEventListener("click", loadBoard);
viewSwitch.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-view]");
  if (!button) return;
  setView(button.dataset.view);
});
maintenanceRefresh.addEventListener("click", loadMaintenanceStats);
cleanupDryRun.addEventListener("click", runCleanupDryRun);
cleanupConfirm.addEventListener("click", runCleanupConfirm);
checkpointDb.addEventListener("click", () => runMaintenanceAction("/api/maintenance/db/checkpoint", "Checkpoint"));
vacuumDb.addEventListener("click", () => runMaintenanceAction("/api/maintenance/db/vacuum", "VACUUM"));
loadBoard();
setInterval(loadBoard, 3000);
