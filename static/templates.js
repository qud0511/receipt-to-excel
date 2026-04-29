'use strict';

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    if (btn.dataset.tab === 'templates') loadTemplateList();
  });
});

// ── Standard fields that Ollama extracts ──────────────────────────────────────
const STANDARD_FIELDS = [
  { key: '날짜',     label: '날짜 (YYYY-MM-DD)' },
  { key: '업체명',   label: '업체명 / 거래처' },
  { key: '품목',     label: '품목 / 내용' },
  { key: '금액',     label: '합계 금액' },
  { key: '부가세',   label: '부가세' },
  { key: '결제수단', label: '결제수단' },
  { key: '비고',     label: '비고' },
];

// ── State ─────────────────────────────────────────────────────────────────────
let selectedTplFile = null;
let analyzedData    = null;   // POST /templates/analyze 결과

const tplDropzone     = document.getElementById('tpl-dropzone');
const tplFileInput    = document.getElementById('tpl-file-input');
const tplNameInput    = document.getElementById('tpl-name');
const tplRegBtn       = document.getElementById('tpl-register-btn');
const tplRegMsg       = document.getElementById('tpl-register-msg');
const tplSelectedFile = document.getElementById('tpl-selected-file');
const mapperSection   = document.getElementById('tpl-mapper-section');

// ── File selection ────────────────────────────────────────────────────────────
function setSelectedFile(file) {
  selectedTplFile = file;
  analyzedData    = null;
  tplSelectedFile.textContent = file ? `선택됨: ${file.name}` : '';
  mapperSection.hidden = true;
  updateRegBtnState();

  if (file) analyzeFile(file);
}

tplDropzone.addEventListener('click', () => tplFileInput.click());
tplFileInput.addEventListener('change', () => {
  if (tplFileInput.files[0]) setSelectedFile(tplFileInput.files[0]);
  tplFileInput.value = '';
});
tplDropzone.addEventListener('dragover', e => { e.preventDefault(); tplDropzone.classList.add('dragover'); });
tplDropzone.addEventListener('dragleave', () => tplDropzone.classList.remove('dragover'));
tplDropzone.addEventListener('drop', e => {
  e.preventDefault();
  tplDropzone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f && f.name.endsWith('.xlsx')) setSelectedFile(f);
  else showRegMsg('⚠ .xlsx 파일만 등록할 수 있습니다.', 'error');
});

// ── Auto-analyze ──────────────────────────────────────────────────────────────
async function analyzeFile(file) {
  showRegMsg('구조 분석 중...', 'info');
  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/templates/analyze', { method: 'POST', body: fd });
    const data = await res.json();

    // Named Range가 이미 있으면 분석 불필요
    if (data.has_named_ranges) {
      showRegMsg('FIELD_* Named Range가 감지되었습니다. 바로 등록 가능합니다.', 'success');
      updateRegBtnState();
      return;
    }

    analyzedData = data;
    if (data.sheets && data.sheets.length > 0) {
      showRegMsg('헤더가 감지되었습니다. 아래에서 필드를 매핑해 주세요.', 'info');
      renderMapper(data.sheets);
    } else {
      showRegMsg('헤더를 감지할 수 없습니다. Named Range가 있는 파일을 사용하세요.', 'error');
    }
  } catch {
    showRegMsg('분석 실패. 네트워크를 확인해 주세요.', 'error');
  }
}

// ── Column mapper UI ──────────────────────────────────────────────────────────
function renderMapper(sheets) {
  mapperSection.hidden = false;
  mapperSection.innerHTML = '';

  // 시트 선택
  const sheetGroup = createElement('div', 'mapper-group');
  sheetGroup.innerHTML = `<label class="mapper-label">시트 선택</label>`;
  const sheetSel = createElement('select', 'mapper-select');
  sheetSel.id = 'mapper-sheet-sel';
  sheets.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.name;
    opt.textContent = s.name;
    sheetSel.appendChild(opt);
  });
  sheetGroup.appendChild(sheetSel);
  mapperSection.appendChild(sheetGroup);

  // 데이터 시작행
  const startGroup = createElement('div', 'mapper-group');
  startGroup.innerHTML = `<label class="mapper-label">데이터 시작 행</label>`;
  const startInput = createElement('input', 'mapper-input');
  startInput.type = 'number';
  startInput.id = 'mapper-data-start';
  startInput.min = 1;
  startGroup.appendChild(startInput);
  mapperSection.appendChild(startGroup);

  // 필드 매핑 테이블
  const table = createElement('div', 'mapper-table');
  const headerRow = createElement('div', 'mapper-row mapper-header');
  headerRow.innerHTML = `<span>추출 필드</span><span>엑셀 컬럼 (헤더 선택)</span>`;
  table.appendChild(headerRow);

  STANDARD_FIELDS.forEach(f => {
    const row = createElement('div', 'mapper-row');
    const label = createElement('span', 'mapper-field-label');
    label.textContent = f.label;

    const sel = createElement('select', 'mapper-col-sel');
    sel.dataset.field = f.key;
    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = '— 사용 안 함 —';
    sel.appendChild(noneOpt);

    row.appendChild(label);
    row.appendChild(sel);
    table.appendChild(row);
  });

  mapperSection.appendChild(table);

  // 시트 변경 시 컬럼 목록 갱신
  function updateColOptions() {
    const selected = sheets.find(s => s.name === sheetSel.value);
    if (!selected) return;

    startInput.value = selected.data_start_row;

    const candidates = selected.candidate_headers;
    document.querySelectorAll('.mapper-col-sel').forEach(sel => {
      const currentVal = sel.value;
      // noneOpt 제외하고 초기화
      while (sel.options.length > 1) sel.remove(1);

      candidates.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.col;
        opt.textContent = `${c.col}${c.row}: ${c.label}`;
        sel.appendChild(opt);
      });

      // 필드명과 유사한 헤더 자동 선택
      const field = sel.dataset.field;
      const autoMatch = candidates.find(c =>
        c.label.replace(/\s/g, '').includes(field.replace(/\s/g, '')) ||
        _fieldAlias(field).some(a => c.label.replace(/\s/g, '').includes(a))
      );
      if (autoMatch) sel.value = autoMatch.col;
      else if (currentVal) sel.value = currentVal;
    });
  }

  sheetSel.addEventListener('change', updateColOptions);
  updateColOptions();

  updateRegBtnState();
}

function _fieldAlias(field) {
  const map = {
    '날짜':     ['일자', '날짜', '거래일'],
    '업체명':   ['거래처', '업체', '상호', '가맹점'],
    '금액':     ['합계', '금액', '결제', '이용금액'],
    '부가세':   ['부가세', 'VAT'],
    '결제수단': ['결제수단', '카드', '수단'],
    '비고':     ['비고', '내용', '메모', '적요'],
  };
  return map[field] || [];
}

// ── Register button state ─────────────────────────────────────────────────────
function updateRegBtnState() {
  tplRegBtn.disabled = !(selectedTplFile && tplNameInput.value.trim());
}
tplNameInput.addEventListener('input', updateRegBtnState);

// ── Submit ────────────────────────────────────────────────────────────────────
tplRegBtn.addEventListener('click', async () => {
  const name = tplNameInput.value.trim();
  if (!name || !selectedTplFile) return;

  tplRegBtn.disabled = true;
  showRegMsg('등록 중...', 'info');

  const fd = new FormData();
  fd.append('name', name);
  fd.append('file', selectedTplFile);

  // Named Range 없는 파일 → field_map 포함
  if (analyzedData) {
    const sheetSel   = document.getElementById('mapper-sheet-sel');
    const startInput = document.getElementById('mapper-data-start');
    const fieldMap   = {
      __sheet:       sheetSel ? sheetSel.value : analyzedData.sheets[0].name,
      __data_start:  startInput ? parseInt(startInput.value, 10) : 6,
    };

    document.querySelectorAll('.mapper-col-sel').forEach(sel => {
      if (sel.value) fieldMap[sel.dataset.field] = sel.value;
    });

    if (Object.keys(fieldMap).length <= 2) {
      showRegMsg('⚠ 하나 이상의 필드를 선택해 주세요.', 'error');
      tplRegBtn.disabled = false;
      updateRegBtnState();
      return;
    }

    fd.append('field_map', JSON.stringify(fieldMap));
  }

  try {
    const res = await fetch('/templates', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    showRegMsg(`✓ 등록 완료 — ${data.name}  (필드: ${data.fields.join(', ')})`, 'success');
    tplNameInput.value = '';
    setSelectedFile(null);
    mapperSection.hidden = true;
    loadTemplateList();
    reloadUploadTemplates();
  } catch (e) {
    showRegMsg('✗ 등록 실패: ' + e.message, 'error');
  } finally {
    updateRegBtnState();
  }
});

// ── Template list ─────────────────────────────────────────────────────────────
document.getElementById('tpl-refresh-btn').addEventListener('click', loadTemplateList);

async function loadTemplateList() {
  const container = document.getElementById('tpl-list');
  container.innerHTML = '<p class="loading">불러오는 중...</p>';
  try {
    const res = await fetch('/templates');
    renderTemplateList(await res.json());
  } catch {
    container.innerHTML = '<p class="msg-error">불러오기 실패</p>';
  }
}

function renderTemplateList(list) {
  const container = document.getElementById('tpl-list');
  if (list.length === 0) {
    container.innerHTML = '<p class="muted-text">등록된 템플릿이 없습니다.</p>';
    return;
  }
  container.innerHTML = '';
  list.forEach(t => container.appendChild(buildTemplateCard(t)));
}

function buildTemplateCard(t) {
  const card = createElement('div', 'tpl-item');
  card.dataset.id = t.template_id;

  card.innerHTML = `
    <div class="tpl-item-header">
      <div>
        <span class="tpl-name">${escHtml(t.name)}</span>
        <span class="tpl-id">${t.template_id}</span>
      </div>
      <div class="tpl-actions">
        <button class="btn-sm btn-outline prompt-btn">
          ${t.has_custom_prompt ? '✎ 프롬프트 수정' : '+ 프롬프트'}
        </button>
        <button class="btn-sm btn-danger delete-btn">삭제</button>
      </div>
    </div>
    <div class="tpl-fields">
      ${t.fields.map(f => `<span class="field-chip">${escHtml(f)}</span>`).join('')}
    </div>
    ${t.has_custom_prompt ? '<div class="tpl-prompt-badge">커스텀 프롬프트 설정됨</div>' : ''}
  `;

  card.querySelector('.prompt-btn').addEventListener('click', () => openPromptModal(t));
  card.querySelector('.delete-btn').addEventListener('click', () => deleteTemplate(t.template_id, t.name));
  return card;
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function deleteTemplate(id, name) {
  if (!confirm(`"${name}" 템플릿을 삭제할까요?`)) return;
  try {
    const res = await fetch(`/templates/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json()).detail);
    loadTemplateList();
    reloadUploadTemplates();
  } catch (e) {
    alert('삭제 실패: ' + e.message);
  }
}

// ── Prompt modal ──────────────────────────────────────────────────────────────
const modal       = document.getElementById('prompt-modal');
const modalTitle  = document.getElementById('modal-title');
const modalPrompt = document.getElementById('modal-prompt');
const modalCancel = document.getElementById('modal-cancel');
const modalSave   = document.getElementById('modal-save');
let _editingId    = null;

async function openPromptModal(t) {
  _editingId = t.template_id;
  modalTitle.textContent = `프롬프트 편집 — ${t.name}`;
  try {
    const res = await fetch(`/templates/${t.template_id}`);
    const detail = await res.json();
    modalPrompt.value = detail.custom_prompt || '';
  } catch { modalPrompt.value = ''; }
  modal.hidden = false;
}

modalCancel.addEventListener('click', () => { modal.hidden = true; _editingId = null; });
modal.addEventListener('click', e => { if (e.target === modal) { modal.hidden = true; _editingId = null; } });

modalSave.addEventListener('click', async () => {
  if (!_editingId) return;
  try {
    const res = await fetch(`/templates/${_editingId}/prompt`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ custom_prompt: modalPrompt.value || null }),
    });
    if (!res.ok) throw new Error((await res.json()).detail);
    modal.hidden = true;
    _editingId = null;
    loadTemplateList();
  } catch (e) { alert('저장 실패: ' + e.message); }
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function createElement(tag, className) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  return el;
}

function showRegMsg(text, type) {
  tplRegMsg.textContent = text;
  tplRegMsg.className = `form-msg msg-${type}`;
}

function escHtml(str) {
  return str.replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function reloadUploadTemplates() {
  if (typeof loadTemplates === 'function') loadTemplates();
}
