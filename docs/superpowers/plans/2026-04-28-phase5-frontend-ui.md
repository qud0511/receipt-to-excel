# Phase 5 — Browser UI (HTML/CSS/JS)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** curl 없이 브라우저만으로 전체 워크플로우(템플릿 등록 → 영수증 업로드 → 진행률 확인 → 파일 다운로드)를 완수할 수 있는 단일 페이지 UI를 구현한다.

**Architecture:** FastAPI `StaticFiles` 로 `static/` 디렉토리를 서빙한다. 프레임워크 없이 vanilla JS로 구현하며 세 영역으로 구성한다: ① 템플릿 라이브러리(좌측 패널), ② 파일 업로드 + 진행률(우측 패널), ③ 다운로드 버튼. SSE는 `EventSource` 로 구독하고, 재연결 시 마지막 상태를 유지한다.

**Tech Stack:** HTML5, CSS3, vanilla JavaScript (fetch + EventSource), FastAPI StaticFiles

**전제:** Phase 4 완료

---

**Definition of Done:**
```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```
브라우저에서 `http://localhost:8000` 접속 → 다음 순서 동작 확인:
1. 템플릿 등록 (xlsx 업로드 + 이름 입력 → 목록에 표시)
2. 템플릿 선택
3. 영수증 이미지 업로드 (여러 장)
4. "변환 시작" 클릭 → 진행률 바 업데이트
5. 완료 후 xlsx 다운로드 버튼 + PDF 다운로드 버튼 활성화
6. 버튼 클릭 → 파일 다운로드

---

## 파일 구조

```
static/
  index.html                         (NEW)
  style.css                          (NEW)
  app.js                             (NEW)

app/
  main.py                            (MODIFY — StaticFiles 마운트)
```

---

## Task 1: FastAPI StaticFiles 마운트 + HTML 기본 구조

**Files:**
- Modify: `app/main.py`
- Create: `static/index.html`
- Create: `static/style.css`

- [ ] **Step 1: `app/main.py` 수정 (StaticFiles 추가)**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_template_store
from app.api.routes import jobs, templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_template_store()
    await store.init_db()
    yield


app = FastAPI(title="Receipt to Excel", lifespan=lifespan)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")
```

- [ ] **Step 2: `static/index.html` 작성**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>영수증 자동 정리</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <h1>영수증 자동 정리</h1>
    <p class="subtitle">영수증을 업로드하면 지출결의서와 증적용 PDF를 자동으로 만들어드립니다</p>
  </header>

  <main>
    <!-- 좌측: 템플릿 라이브러리 -->
    <section id="template-panel" class="panel">
      <h2>템플릿 라이브러리</h2>

      <div class="card" id="register-form-card">
        <h3>새 템플릿 등록</h3>
        <form id="register-form">
          <label>
            xlsx 파일 (Named Range 필요)
            <input type="file" id="template-file" accept=".xlsx" required>
          </label>
          <label>
            템플릿 이름
            <input type="text" id="template-name" placeholder="지출결의서_4월" required>
          </label>
          <button type="submit" class="btn btn-primary">등록</button>
        </form>
        <p id="register-error" class="error hidden"></p>
      </div>

      <div id="template-list" class="template-list">
        <p class="hint">등록된 템플릿이 없습니다.</p>
      </div>
    </section>

    <!-- 우측: 변환 작업 -->
    <section id="job-panel" class="panel">
      <h2>영수증 변환</h2>

      <div class="card">
        <div id="selected-template" class="selected-template">
          <span class="label">선택된 템플릿:</span>
          <span id="selected-name" class="value">없음 (왼쪽에서 선택하세요)</span>
        </div>

        <label class="dropzone" id="dropzone">
          <input type="file" id="receipt-files" accept=".jpg,.jpeg,.png,.pdf,.xlsx,.pptx" multiple>
          <div class="dropzone-content">
            <span class="icon">📎</span>
            <span>클릭하거나 파일을 끌어다 놓으세요</span>
            <span class="hint">JPG, PNG, PDF, XLSX, PPTX 지원 · 최대 50개</span>
          </div>
        </label>

        <div id="file-list" class="file-list hidden"></div>

        <button id="start-btn" class="btn btn-success" disabled>변환 시작</button>
      </div>

      <!-- 진행률 -->
      <div class="card hidden" id="progress-card">
        <h3>처리 중...</h3>
        <div class="progress-bar-container">
          <div class="progress-bar" id="progress-bar"></div>
        </div>
        <p id="progress-text" class="progress-text">준비 중...</p>
        <div id="failed-files" class="failed-files hidden"></div>
      </div>

      <!-- 완료 / 다운로드 -->
      <div class="card hidden" id="result-card">
        <h3>변환 완료 ✓</h3>
        <div class="download-buttons">
          <a id="btn-excel" href="#" class="btn btn-download" download>
            📊 지출결의서 (xlsx) 다운로드
          </a>
          <a id="btn-pdf" href="#" class="btn btn-download hidden" download>
            📄 증적용 영수증 모음 (PDF) 다운로드
          </a>
        </div>
      </div>

      <!-- 오류 -->
      <div class="card hidden" id="error-card">
        <h3>오류 발생</h3>
        <p id="error-message" class="error"></p>
        <button class="btn btn-secondary" onclick="resetJob()">다시 시도</button>
      </div>
    </section>
  </main>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: `static/style.css` 작성**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --primary: #2563eb;
  --success: #16a34a;
  --danger: #dc2626;
  --warning: #d97706;
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --muted: #64748b;
  --radius: 8px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}

header {
  background: var(--primary);
  color: white;
  padding: 1.25rem 2rem;
}
header h1 { font-size: 1.5rem; font-weight: 700; }
header .subtitle { font-size: 0.875rem; opacity: 0.85; margin-top: 0.25rem; }

main {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 1.5rem;
  padding: 1.5rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.panel h2 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 1rem;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1rem;
}
.card h3 { font-size: 0.9rem; font-weight: 600; margin-bottom: 1rem; }

/* Form */
form { display: flex; flex-direction: column; gap: 0.75rem; }
label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.875rem; font-weight: 500; }
input[type="text"], input[type="file"] {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  width: 100%;
}
input[type="text"]:focus { outline: 2px solid var(--primary); outline-offset: 1px; }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0.5rem 1rem;
  border: none; border-radius: 6px; cursor: pointer;
  font-size: 0.875rem; font-weight: 500; text-decoration: none;
  transition: opacity 0.15s;
}
.btn:hover { opacity: 0.85; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary  { background: var(--primary); color: white; }
.btn-success  { background: var(--success); color: white; width: 100%; margin-top: 0.5rem; }
.btn-secondary { background: var(--border); color: var(--text); }
.btn-download { background: #0f172a; color: white; margin-right: 0.5rem; margin-top: 0.5rem; }

/* Template list */
.template-list { display: flex; flex-direction: column; gap: 0.5rem; }
.template-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.625rem 0.875rem;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 6px; cursor: pointer; transition: border-color 0.15s;
}
.template-item:hover { border-color: var(--primary); }
.template-item.selected { border-color: var(--primary); background: #eff6ff; }
.template-item-name { font-size: 0.875rem; font-weight: 500; }
.template-item-fields { font-size: 0.75rem; color: var(--muted); }
.template-delete { background: none; border: none; color: var(--danger); cursor: pointer; font-size: 1rem; }

/* Dropzone */
.dropzone {
  display: block;
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s;
  margin-top: 0.75rem;
}
.dropzone:hover, .dropzone.drag-over { border-color: var(--primary); background: #f0f7ff; }
.dropzone input[type="file"] { display: none; }
.dropzone-content { display: flex; flex-direction: column; gap: 0.25rem; color: var(--muted); }
.dropzone-content .icon { font-size: 2rem; }

/* File list */
.file-list { margin-top: 0.75rem; font-size: 0.8rem; color: var(--muted); }
.file-list-item { padding: 0.25rem 0; border-bottom: 1px solid var(--border); }

/* Selected template */
.selected-template { margin-bottom: 0.75rem; font-size: 0.875rem; }
.selected-template .label { color: var(--muted); }
.selected-template .value { font-weight: 600; margin-left: 0.25rem; }

/* Progress */
.progress-bar-container {
  height: 10px; background: var(--border); border-radius: 99px; overflow: hidden; margin: 0.75rem 0;
}
.progress-bar { height: 100%; background: var(--primary); width: 0%; transition: width 0.3s ease; }
.progress-text { font-size: 0.875rem; color: var(--muted); }

/* Failed files */
.failed-files { margin-top: 0.75rem; font-size: 0.8rem; color: var(--warning); }

/* Download buttons */
.download-buttons { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }

/* Utilities */
.hidden { display: none !important; }
.error { color: var(--danger); font-size: 0.875rem; margin-top: 0.5rem; }
.hint { font-size: 0.8rem; color: var(--muted); }

@media (max-width: 768px) {
  main { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: `static/` 디렉토리 확인**

```bash
ls static/
```
Expected: `index.html  style.css` (app.js는 Task 2에서 생성)

- [ ] **Step 5: Commit**

```bash
git add app/main.py static/index.html static/style.css
git commit -m "feat: FastAPI StaticFiles mount, HTML shell, CSS design system"
```

---

## Task 2: app.js — 전체 구현

**Files:**
- Create: `static/app.js`

- [ ] **Step 1: `static/app.js` 작성**

```javascript
// ───────────────────────────────────────────────
// 상태
// ───────────────────────────────────────────────
let templates = [];
let selectedTemplateId = null;
let selectedFiles = [];
let currentJobId = null;
let eventSource = null;

// ───────────────────────────────────────────────
// 초기화
// ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadTemplates();
  setupRegisterForm();
  setupDropzone();
  document.getElementById('start-btn').addEventListener('click', startJob);
});

// ───────────────────────────────────────────────
// 템플릿 목록
// ───────────────────────────────────────────────
async function loadTemplates() {
  try {
    const res = await fetch('/templates');
    templates = await res.json();
    renderTemplateList();
  } catch (e) {
    showRegisterError('템플릿 목록을 불러오지 못했습니다.');
  }
}

function renderTemplateList() {
  const list = document.getElementById('template-list');
  if (templates.length === 0) {
    list.innerHTML = '<p class="hint">등록된 템플릿이 없습니다.</p>';
    return;
  }
  list.innerHTML = templates.map(t => `
    <div class="template-item ${t.template_id === selectedTemplateId ? 'selected' : ''}"
         onclick="selectTemplate('${t.template_id}', '${escapeHtml(t.name)}')">
      <div>
        <div class="template-item-name">${escapeHtml(t.name)}</div>
        <div class="template-item-fields">${t.fields.join(', ')}</div>
      </div>
      <button class="template-delete"
              onclick="event.stopPropagation(); deleteTemplate('${t.template_id}')"
              title="삭제">✕</button>
    </div>
  `).join('');
}

function selectTemplate(id, name) {
  selectedTemplateId = id;
  document.getElementById('selected-name').textContent = name;
  renderTemplateList();
  updateStartButton();
}

async function deleteTemplate(id) {
  if (!confirm('템플릿을 삭제할까요?')) return;
  await fetch(`/templates/${id}`, { method: 'DELETE' });
  if (selectedTemplateId === id) {
    selectedTemplateId = null;
    document.getElementById('selected-name').textContent = '없음 (왼쪽에서 선택하세요)';
  }
  await loadTemplates();
  updateStartButton();
}

// ───────────────────────────────────────────────
// 템플릿 등록 폼
// ───────────────────────────────────────────────
function setupRegisterForm() {
  document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const file = document.getElementById('template-file').files[0];
    const name = document.getElementById('template-name').value.trim();
    if (!file || !name) return;

    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', name);

    try {
      const res = await fetch('/templates', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.json();
        showRegisterError(err.detail || '등록 실패');
        return;
      }
      hideRegisterError();
      e.target.reset();
      await loadTemplates();
    } catch (err) {
      showRegisterError('서버 연결 오류');
    }
  });
}

function showRegisterError(msg) {
  const el = document.getElementById('register-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideRegisterError() {
  document.getElementById('register-error').classList.add('hidden');
}

// ───────────────────────────────────────────────
// 파일 드롭존
// ───────────────────────────────────────────────
function setupDropzone() {
  const dropzone = document.getElementById('dropzone');
  const input = document.getElementById('receipt-files');

  input.addEventListener('change', () => {
    selectedFiles = Array.from(input.files);
    renderFileList();
    updateStartButton();
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    selectedFiles = Array.from(e.dataTransfer.files);
    renderFileList();
    updateStartButton();
  });
}

function renderFileList() {
  const el = document.getElementById('file-list');
  if (selectedFiles.length === 0) {
    el.classList.add('hidden');
    return;
  }
  el.innerHTML = selectedFiles
    .map(f => `<div class="file-list-item">📄 ${escapeHtml(f.name)} (${formatBytes(f.size)})</div>`)
    .join('');
  el.classList.remove('hidden');
}

function updateStartButton() {
  const btn = document.getElementById('start-btn');
  btn.disabled = !(selectedTemplateId && selectedFiles.length > 0);
}

// ───────────────────────────────────────────────
// 작업 시작
// ───────────────────────────────────────────────
async function startJob() {
  if (!selectedTemplateId || selectedFiles.length === 0) return;

  resetJobUI();
  showCard('progress-card');

  const fd = new FormData();
  fd.append('template_id', selectedTemplateId);
  for (const f of selectedFiles) fd.append('files', f);

  let jobId;
  try {
    const res = await fetch('/jobs', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json();
      showError(err.detail || '작업 시작 실패');
      return;
    }
    const data = await res.json();
    jobId = data.job_id;
    currentJobId = jobId;
    updateProgress({ status: 'pending', done: 0, total: data.total, current_file: null });
  } catch (e) {
    showError('서버 연결 오류');
    return;
  }

  subscribeSSE(jobId);
}

// ───────────────────────────────────────────────
// SSE 구독
// ───────────────────────────────────────────────
function subscribeSSE(jobId) {
  if (eventSource) eventSource.close();

  eventSource = new EventSource(`/jobs/${jobId}/stream`);

  eventSource.onmessage = (e) => {
    const job = JSON.parse(e.data);
    if (job.error && !job.status) {
      showError(job.error);
      return;
    }
    updateProgress(job);
    if (job.status === 'completed') {
      eventSource.close();
      showResult(job);
    } else if (job.status === 'failed') {
      eventSource.close();
      showError(job.error || 'OCR 처리 중 오류가 발생했습니다.');
    }
  };

  eventSource.onerror = () => {
    document.getElementById('progress-text').textContent =
      '연결이 끊어졌습니다. 재연결 중...';
  };
}

// ───────────────────────────────────────────────
// 진행률 업데이트
// ───────────────────────────────────────────────
function updateProgress(job) {
  const pct = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;
  document.getElementById('progress-bar').style.width = `${pct}%`;

  const statusMap = { pending: '준비 중', processing: '처리 중', completed: '완료' };
  const fileInfo = job.current_file ? ` — ${job.current_file}` : '';
  document.getElementById('progress-text').textContent =
    `${statusMap[job.status] || job.status}: ${job.done} / ${job.total}${fileInfo}`;

  if (job.failed_files && job.failed_files.length > 0) {
    const el = document.getElementById('failed-files');
    el.textContent = `⚠ 처리 실패: ${job.failed_files.join(', ')}`;
    el.classList.remove('hidden');
  }
}

// ───────────────────────────────────────────────
// 완료 — 다운로드 버튼 표시
// ───────────────────────────────────────────────
function showResult(job) {
  hideCard('progress-card');
  showCard('result-card');

  const btnExcel = document.getElementById('btn-excel');
  btnExcel.href = job.download_url;
  btnExcel.setAttribute('download', `지출결의서_${job.job_id || ''}.xlsx`);

  const btnPdf = document.getElementById('btn-pdf');
  if (job.pdf_url) {
    btnPdf.href = job.pdf_url;
    btnPdf.setAttribute('download', `증적용_영수증_모음.pdf`);
    btnPdf.classList.remove('hidden');
  } else {
    btnPdf.classList.add('hidden');
  }
}

// ───────────────────────────────────────────────
// 오류 표시
// ───────────────────────────────────────────────
function showError(msg) {
  hideCard('progress-card');
  hideCard('result-card');
  document.getElementById('error-message').textContent = msg;
  showCard('error-card');
}

function resetJob() {
  if (eventSource) eventSource.close();
  currentJobId = null;
  hideCard('progress-card');
  hideCard('result-card');
  hideCard('error-card');
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('failed-files').classList.add('hidden');
}

function resetJobUI() {
  hideCard('result-card');
  hideCard('error-card');
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('failed-files').classList.add('hidden');
  document.getElementById('failed-files').textContent = '';
}

// ───────────────────────────────────────────────
// 유틸
// ───────────────────────────────────────────────
function showCard(id) { document.getElementById(id).classList.remove('hidden'); }
function hideCard(id) { document.getElementById(id).classList.add('hidden'); }

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
```

- [ ] **Step 2: 전체 테스트 통과 확인 (정적 파일은 테스트 제외)**

```bash
source .venv/bin/activate && pytest -v
```
Expected: 모든 기존 테스트 passed

- [ ] **Step 3: 서버 기동 후 브라우저 확인**

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

브라우저에서 `http://localhost:8000` 접속 후 확인:
- 페이지 로딩 ✓ (헤더 + 두 패널)
- 템플릿 등록 폼 표시 ✓
- 드롭존 표시 ✓

- [ ] **Step 4: 샘플 템플릿으로 E2E 확인**

```bash
# 샘플 템플릿 생성
source .venv/bin/activate && python3 scripts/make_sample_template.py
```

1. 브라우저에서 `tests/fixtures/template.xlsx` 등록 → 좌측 목록에 표시
2. 템플릿 선택 → "선택된 템플릿" 업데이트
3. `tests/fixtures/sample.jpg` 업로드 → 파일 목록에 표시, "변환 시작" 활성화
4. "변환 시작" → 진행률 바 업데이트
5. 완료 → xlsx 다운로드 버튼 표시 (Ollama 있으면 PDF 버튼도 표시)

- [ ] **Step 5: Commit**

```bash
git add static/ app/main.py
git commit -m "feat: browser UI — template library, drag-drop upload, SSE progress, download buttons"
```

---

## Self-Review

| 스펙 요구사항 | 구현 태스크 |
|--------------|------------|
| 템플릿 등록/목록/선택/삭제 UI | Task 2 — register form + template list |
| 파일 업로드 (drag-and-drop 포함) | Task 2 — dropzone setup |
| SSE 진행률 실시간 업데이트 | Task 2 — subscribeSSE() |
| SSE 재연결 시 상태 유지 | Task 2 — onerror 핸들러 |
| completed → xlsx + PDF 버튼 동시 표시 | Task 2 — showResult() |
| pdf_url null 시 PDF 버튼 숨김 | Task 2 — `if (job.pdf_url)` |
| 에러 인라인 표시 | Task 2 — showError() |
| 프레임워크 없는 정적 파일 | Task 1 — vanilla JS + FastAPI StaticFiles |

**플레이스홀더 없음.**  
**API 일관성** — `fetch('/templates')`, `fetch('/jobs', ...)`, `EventSource('/jobs/{id}/stream')` 모두 Phase 1-4에서 정의된 엔드포인트와 일치.
