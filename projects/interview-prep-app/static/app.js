/* 面试备战站 · 原生 JavaScript 单页（无框架、无构建链、无 CDN 依赖）。
   机制说明：
   - 所有数据来自 app.py 的 /api/* 接口，前端不持有事实源——刷新页面即回到服务端真值。
   - Markdown 渲染用极简自实现 mdRender()：这就是"离线降级方案"本体，
     不引 marked.js CDN，断网/内网环境照样渲染（粗体/行内码/链接/两级列表够用）。
   - 延伸阅读链接原为工作区相对路径（../xxx-handbook/...），rewriteHref 把它改写为
     后端只读挂载的 /workspace/...，点击可回查原手册。 */

"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const RATE_LABEL = { know: "会", half: "半会", no: "不会" };

// ---------------- 基础设施 ----------------

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `HTTP ${resp.status}`;
    throw new Error(detail);
  }
  return resp.json();
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

let toastTimer = null;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
}

// ---------------- 极简 Markdown 渲染（离线方案） ----------------

function rewriteHref(href) {
  // ../tuning-handbook/X.md 相对于 interview-handbook/，等价于工作区根下的 tuning-handbook/X.md
  return href.startsWith("../") ? "/workspace/" + href.slice(3) : href;
}

function mdInline(text) {
  let s = esc(text);
  s = s.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, t, href) =>
    `<a href="${esc(rewriteHref(href))}" target="_blank" rel="noopener">${t}</a>`);
  return s;
}

function mdRender(src) {
  // 行级规则：``` 围栏切换代码块模式；"- " 为一级列表、"  - "（两空格起）为二级列表，
  // 其余整行为段落。用栈维护未闭合的 <ul>：列表行切换层级时先补齐/闭合，非列表行闭合全部。
  // 代码块专治 07 手撕题的代码骨架（16 题全带 ```python 围栏），块内只转义不再做行内渲染。
  const lines = String(src).split("\n");
  let html = "";
  let openUl = 0;
  let inCode = false;
  const closeUl = (depth) => { while (openUl > depth) { html += "</ul>"; openUl--; } };
  const openUlTo = (depth) => { while (openUl < depth) { html += "<ul>"; openUl++; } };

  for (const raw of lines) {
    if (raw.trim().startsWith("```")) {
      closeUl(0);
      if (inCode) { html += "</code></pre>"; inCode = false; }
      else { html += "<pre><code>"; inCode = true; }
      continue;
    }
    if (inCode) { html += esc(raw) + "\n"; continue; }
    const m = raw.match(/^(\s*)-\s+(.*)$/);
    if (m) {
      const depth = m[1].length >= 2 ? 2 : 1;
      if (depth < openUl) closeUl(depth);
      if (depth > openUl) openUlTo(depth);
      html += `<li>${mdInline(m[2])}</li>`;
    } else {
      closeUl(0);
      if (raw.trim()) html += `<p>${mdInline(raw.trim())}</p>`;
    }
  }
  if (inCode) html += "</code></pre>";
  closeUl(0);
  return html;
}

function renderSections(sections, keys) {
  return keys
    .filter((k) => sections[k])
    .map((k) => `<div class="sec-h">${esc(k)}</div><div class="sec-body">${mdRender(sections[k])}</div>`)
    .join("");
}

// ---------------- 徽章与视图切换 ----------------

function badge(text, cls) { return `<span class="badge ${cls}">${esc(text)}</span>`; }
function diffBadge(d) { return badge(d, `diff-${d}`); }
function freqBadge(f) { return badge(`频次${f}`, `freq-${f}`); }
function rateBadge(latest, inWrongbook) {
  let html = badge(latest ? RATE_LABEL[latest] : "未测", `rate-${latest || "none"}`);
  if (inWrongbook) html += " " + badge("错题本", "rate-no");
  return html;
}

const VIEWS = ["dashboard", "library", "test", "wrongbook"];
function show(view) {
  VIEWS.forEach((v) => {
    $(`#view-${v}`).hidden = v !== view;
    $$(`.tab[data-view="${v}"]`).forEach((t) => t.classList.toggle("active", v === view));
  });
  if (view === "dashboard") loadDashboard();
  if (view === "library") loadLibrary();
  if (view === "wrongbook") loadWrongbook();
  if (view === "test") backToTestSetup();
}

// ---------------- 视图一：进度仪表盘 ----------------

async function loadDashboard() {
  try {
    const s = await api("/api/stats");
    const pct = (x) => (x * 100).toFixed(1) + "%";
    $("#dash-summary").innerHTML = `
      <div class="stat-card"><div class="num">${s.total}</div><div class="label">题库总数</div></div>
      <div class="stat-card"><div class="num">${s.reviewed}</div><div class="label">已自测</div></div>
      <div class="stat-card"><div class="num">${pct(s.completion)}</div><div class="label">完成率</div></div>
      <div class="stat-card warn"><div class="num">${pct(s.wrong_rate)}</div><div class="label">错题率（半会+不会）</div></div>`;

    const dist = s.distribution;
    const maxVal = Math.max(dist.know, dist.half, dist.no, dist.untested, 1);
    const distRow = (name, val, color) => `
      <div class="dist-row"><span class="name">${name}</span>
        <div class="dist-bar"><div style="width:${(val / maxVal) * 100}%;background:${color}"></div></div>
        <span class="val">${val} 题（${s.reviewed + dist.untested ? pct(val / (s.reviewed + dist.untested)) : "0%"}）</span>
      </div>`;
    $("#dash-distribution").innerHTML = `
      <h2>自评分布（全库）</h2>
      ${distRow("会", dist.know, "#16a34a")}
      ${distRow("半会", dist.half, "#d97706")}
      ${distRow("不会", dist.no, "#dc2626")}
      ${distRow("未测", dist.untested, "#9ca3af")}`;

    $("#dash-topics").innerHTML = `
      <h2>分主题进度</h2>
      <table><thead><tr>
        <th>主题</th><th>题数</th><th>已测</th><th>会</th><th>半会</th><th>不会</th><th>完成率</th><th>错题率</th>
      </tr></thead><tbody>
      ${s.by_topic.map((t) => `
        <tr style="cursor:default">
          <td>${esc(t.name)}</td><td class="num">${t.total}</td><td class="num">${t.reviewed}</td>
          <td class="num">${t.know}</td><td class="num">${t.half}</td><td class="num">${t.no}</td>
          <td style="min-width:120px">
            <div class="dist-bar"><div style="width:${t.completion * 100}%;background:#2563eb"></div></div>
            <span class="muted">${pct(t.completion)}</span>
          </td>
          <td>${pct(t.wrong_rate)}</td>
        </tr>`).join("")}
      </tbody></table>`;
  } catch (e) { toast("仪表盘加载失败：" + e.message); }
}

// ---------------- 视图二：题库检索 ----------------

let libPage = 1;
const LIB_PAGE_SIZE = 20;

function libFilters() {
  return new URLSearchParams({
    topic: $("#f-topic").value,
    difficulty: $("#f-difficulty").value,
    frequency: $("#f-frequency").value,
    status: $("#f-status").value,
    q: $("#f-keyword").value.trim(),
  });
}

async function loadLibrary() {
  const params = libFilters();
  params.set("page", libPage);
  params.set("page_size", LIB_PAGE_SIZE);
  try {
    const data = await api("/api/questions?" + params);
    $("#lib-count").textContent = `命中 ${data.total} 题`;
    $("#lib-table tbody").innerHTML = data.items.map((q) => `
      <tr data-qid="${q.id}">
        <td class="num">${q.id}</td>
        <td>${esc(q.title)}</td>
        <td class="num">${esc(q.topic_name)}</td>
        <td>${diffBadge(q.difficulty)}</td>
        <td>${freqBadge(q.frequency)}</td>
        <td>${rateBadge(q.latest, q.in_wrongbook)}</td>
      </tr>`).join("");
    const pages = Math.max(1, Math.ceil(data.total / LIB_PAGE_SIZE));
    $("#lib-page").textContent = `${libPage} / ${pages}`;
    $("#lib-prev").disabled = libPage <= 1;
    $("#lib-next").disabled = libPage >= pages;
    $$("#lib-table tbody tr").forEach((tr) =>
      tr.addEventListener("click", () => openDetail(tr.dataset.qid)));
  } catch (e) { toast("题库加载失败：" + e.message); }
}

// ---------------- 题目详情弹层（四件套全文） ----------------

async function openDetail(qid) {
  try {
    const q = await api("/api/questions/" + qid);
    $("#modal-title").textContent = `${q.id}. ${q.title}`;
    $("#modal-meta").innerHTML =
      `${badge(q.topic_name, "freq-中")} ${diffBadge(q.difficulty)} ${freqBadge(q.frequency)} `
      + rateBadge(q.latest, q.in_wrongbook);
    $("#modal-body").innerHTML = renderSections(q.sections,
      ["考察点", "参考回答", "追问与陷阱", "加分项", "延伸阅读"]);
    $("#modal-rating-hint").textContent = q.latest ? `当前自评：${RATE_LABEL[q.latest]}` : "尚未自评";
    $("#modal-mask").hidden = false;
    $$("#modal .rate").forEach((btn) => {
      btn.onclick = async () => {
        try {
          const r = await api("/api/reviews", {
            method: "POST", body: JSON.stringify({ qid, rating: btn.dataset.rating }),
          });
          $("#modal-rating-hint").textContent = `已记录：${RATE_LABEL[r.latest]}`
            + (r.in_wrongbook ? "（已进错题本）" : "");
          toast(`${qid} 自评已记录：${RATE_LABEL[r.latest]}`);
          $("#modal-meta").innerHTML =
            `${badge(q.topic_name, "freq-中")} ${diffBadge(q.difficulty)} ${freqBadge(q.frequency)} `
            + rateBadge(r.latest, r.in_wrongbook);
        } catch (e) { toast("提交失败：" + e.message); }
      };
    });
  } catch (e) { toast("详情加载失败：" + e.message); }
}

function closeModal() { $("#modal-mask").hidden = true; }

// ---------------- 视图三：卡片自测 ----------------

let testQueue = [];   // 本轮队列：存题目 id，卡片渲染时再拉详情
let testIndex = 0;
let testTally = { know: 0, half: 0, no: 0 };

function backToTestSetup() {
  $("#test-setup").hidden = false;
  $("#test-card").hidden = true;
  $("#test-done").hidden = true;
}

async function fetchAllFiltered(params) {
  // 翻页取全：page_size 上限 200，128 题一页拿完，循环只为防御将来题库扩容
  const all = [];
  let page = 1;
  for (;;) {
    params.set("page", page);
    params.set("page_size", 200);
    const data = await api("/api/questions?" + params);
    all.push(...data.items);
    if (all.length >= data.total || data.items.length === 0) break;
    page += 1;
  }
  return all;
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

async function startTest(queueIds) {
  if (!queueIds.length) { toast("当前范围没有题目"); return; }
  testQueue = queueIds;
  testIndex = 0;
  testTally = { know: 0, half: 0, no: 0 };
  $("#test-setup").hidden = true;
  $("#test-done").hidden = true;
  $("#test-card").hidden = false;
  renderCard();
}

async function startTestFromFilters() {
  const params = new URLSearchParams({
    topic: $("#t-topic").value,
    difficulty: $("#t-difficulty").value,
    frequency: $("#t-frequency").value,
  });
  const scope = $("#t-scope").value;
  if (scope === "untested") params.set("status", "untested");
  if (scope === "wrongbook") params.set("status", "wrongbook");
  if (scope === "high") params.set("frequency", "高");
  try {
    let items = await fetchAllFiltered(params);
    if ($("#t-shuffle").checked) shuffle(items);
    await startTest(items.map((q) => q.id));
  } catch (e) { toast("组卷失败：" + e.message); }
}

async function renderCard() {
  const qid = testQueue[testIndex];
  $("#test-progress").textContent = `第 ${testIndex + 1} / ${testQueue.length} 题`;
  $("#card-front").hidden = false;
  $("#card-back").hidden = true;
  try {
    const q = await api("/api/questions/" + qid);
    $("#card-meta").innerHTML = `${badge(q.topic_name, "freq-中")} ${diffBadge(q.difficulty)} ${freqBadge(q.frequency)}`;
    $("#card-title").textContent = q.title;
    // 背面内容预取：翻面时零等待
    $("#card-meta-back").innerHTML = $("#card-meta").innerHTML;
    $("#card-title-back").textContent = `${q.id}. ${q.title}`;
    $("#card-answer").innerHTML = renderSections(q.sections, ["参考回答"]);
  } catch (e) { toast("题目加载失败：" + e.message); }
}

async function submitCardRating(rating) {
  const qid = testQueue[testIndex];
  try {
    const r = await api("/api/reviews", {
      method: "POST", body: JSON.stringify({ qid, rating }),
    });
    testTally[rating] += 1;
    if (r.in_wrongbook) toast(`${qid} 已进错题本`);
    testIndex += 1;
    if (testIndex >= testQueue.length) {
      $("#test-card").hidden = true;
      $("#test-done").hidden = false;
      const t = testTally;
      $("#test-done-summary").textContent =
        `本轮 ${testQueue.length} 题：会 ${t.know} · 半会 ${t.half} · 不会 ${t.no}。`
        + ` 半会/不会已自动进错题本，可在错题本视图重测。`;
    } else {
      renderCard();
    }
  } catch (e) { toast("提交失败：" + e.message); }
}

// ---------------- 视图四：错题本 ----------------

async function loadWrongbook() {
  try {
    const data = await api("/api/wrongbook");
    $("#wb-count").textContent = data.total
      ? `错题本共 ${data.total} 题（半会/不会自动入本，重测改评后自动出本）`
      : "错题本是空的——去卡片自测里刷几题吧";
    $("#wb-table").hidden = data.total === 0;
    $("#wb-table tbody").innerHTML = data.items.map((q) => `
      <tr data-qid="${q.id}">
        <td class="num">${q.id}</td>
        <td>${esc(q.title)}</td>
        <td class="num">${esc(q.topic)}</td>
        <td>${rateBadge(q.latest, false)}</td>
        <td>
          <button class="wb-retest" data-qid="${q.id}">重测</button>
          <button class="wb-dismiss" data-qid="${q.id}">移除</button>
        </td>
      </tr>`).join("");
    $$("#wb-table tbody tr").forEach((tr) => {
      tr.addEventListener("click", (ev) => {
        if (ev.target.tagName === "BUTTON") return; // 按钮点击不触发行详情
        openDetail(tr.dataset.qid);
      });
    });
    $$(".wb-retest").forEach((btn) => btn.addEventListener("click", async () => {
      show("test");
      await startTest([btn.dataset.qid]);
    }));
    $$(".wb-dismiss").forEach((btn) => btn.addEventListener("click", async () => {
      try {
        await api(`/api/wrongbook/${btn.dataset.qid}/dismiss`, { method: "POST" });
        toast(`${btn.dataset.qid} 已移出错题本`);
        loadWrongbook();
      } catch (e) { toast("移除失败：" + e.message); }
    }));
  } catch (e) { toast("错题本加载失败：" + e.message); }
}

// ---------------- 初始化与事件绑定 ----------------

function populateTopicSelects(meta) {
  const options = meta.topics
    .map((t) => `<option value="${t.id}">${t.id} ${esc(t.name)}（${t.count} 题）</option>`)
    .join("");
  $("#f-topic").innerHTML = `<option value="">全部</option>` + options;
  $("#t-topic").innerHTML = `<option value="">全部</option>` + options;
}

async function init() {
  try {
    const meta = await api("/api/meta");
    populateTopicSelects(meta);
  } catch (e) {
    toast("服务初始化失败：" + e.message + "（若索引未构建，先跑 python build_index.py）");
  }

  $$(".tab").forEach((tab) => tab.addEventListener("click", () => show(tab.dataset.view)));
  $("#f-search").addEventListener("click", () => { libPage = 1; show("library"); });
  $("#f-keyword").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { libPage = 1; loadLibrary(); }
  });
  ["#f-topic", "#f-difficulty", "#f-frequency", "#f-status"].forEach((sel) =>
    $(sel).addEventListener("change", () => { libPage = 1; loadLibrary(); }));
  $("#lib-prev").addEventListener("click", () => { libPage--; loadLibrary(); });
  $("#lib-next").addEventListener("click", () => { libPage++; loadLibrary(); });

  $("#t-start").addEventListener("click", startTestFromFilters);
  $("#card-reveal").addEventListener("click", () => {
    $("#card-front").hidden = true;
    $("#card-back").hidden = false;
  });
  $$("#card-back .rate").forEach((btn) =>
    btn.addEventListener("click", () => submitCardRating(btn.dataset.rating)));
  $("#card-detail-link").addEventListener("click", () =>
    openDetail(testQueue[testIndex]));
  $("#test-again").addEventListener("click", backToTestSetup);

  $("#modal-close").addEventListener("click", closeModal);
  $("#modal-mask").addEventListener("click", (ev) => {
    if (ev.target === $("#modal-mask")) closeModal(); // 点遮罩关闭，点弹层内部不关
  });

  show("dashboard");
}

init();
