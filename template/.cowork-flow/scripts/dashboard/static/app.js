const board = document.querySelector("#board");
const detail = document.querySelector("#detail");
const summary = document.querySelector("#summary");
const refresh = document.querySelector("#refresh");

const labels = {
  planning: "Planning",
  in_progress: "In progress",
  review: "Review",
  blocked: "Blocked",
  completed: "Completed",
  archived: "Archived",
};

const marks = {
  generic: "G",
  fan_out: "F",
  pipeline: "P",
  human_loop: "H",
};

async function getJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function taskCard(task) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `task priority-${task.priority || "P2"}`;
  button.dataset.taskId = task.id;

  const title = document.createElement("span");
  title.className = "task-title";
  title.textContent = task.title || task.id;

  const meta = document.createElement("span");
  meta.className = "task-meta";
  const mark = marks[task.pattern] || "G";
  const progress = task.child_total ? ` · ${task.child_done}/${task.child_total}` : "";
  meta.textContent = `${mark} · ${task.priority || "P2"} · ${task.assignee || "-"}${progress}`;

  button.append(title, meta);
  button.addEventListener("click", () => loadDetail(task.id));
  return button;
}

function renderBoard(data) {
  board.replaceChildren();
  let count = 0;
  for (const column of data.columns || []) {
    const section = document.createElement("section");
    section.className = "column";
    const heading = document.createElement("h2");
    const tasks = column.tasks || [];
    count += tasks.length;
    heading.textContent = `${labels[column.status] || column.status} ${tasks.length}`;
    section.append(heading);
    for (const task of tasks) section.append(taskCard(task));
    board.append(section);
  }
  summary.textContent = `${count} tasks`;
}

function row(label, value) {
  const item = document.createElement("div");
  item.className = "row";
  const left = document.createElement("span");
  left.textContent = label;
  const right = document.createElement("strong");
  right.textContent = value || "-";
  item.append(left, right);
  return item;
}

async function loadDetail(id) {
  const data = await getJson(`/api/task/${encodeURIComponent(id)}`);
  detail.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = data.task.title;
  detail.append(
    title,
    row("Status", data.task.status),
    row("Pattern", data.task.pattern),
    row("Priority", data.task.priority),
    row("Children", String((data.children || []).length)),
    row("Audit", String((data.audit || []).length)),
    row("Agent runs", String((data.agentRuns || []).length)),
  );
}

async function loadBoard() {
  try {
    renderBoard(await getJson("/api/board"));
  } catch (error) {
    summary.textContent = error.message;
  }
}

refresh.addEventListener("click", loadBoard);
loadBoard();
setInterval(loadBoard, 3000);
