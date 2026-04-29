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

// ── Template registration ─────────────────────────────────────────────────────
const tplDropzone   = document.getElementById('tpl-dropzone');
const tplFileInput  = document.getElementById('tpl-file-input');
const tplNameInput  = document.getElementById('tpl-name');
const tplRegBtn     = document.getElementById('tpl-register-btn');
const tplRegMsg     = document.getElementById('tpl-register-msg');
const tplSelectedFile = document.getElementById('tpl-selected-file');

let selectedTplFile = null;

function setSelectedFile(file) {
  selectedTplFile = file;
  tplSelectedFile.textContent = file ? `선택됨: ${file.name}` : '';
  updateRegBtnState();
}

function updateRegBtnState() {
  tplRegBtn.disabled = !(selectedTplFile && tplNameInput.value.trim());
}

tplNameInput.addEventListener('input', updateRegBtnState);

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

tplRegBtn.addEventListener('click', async () => {
  const name = tplNameInput.value.trim();
  if (!name || !selectedTplFile) return;

  tplRegBtn.disabled = true;
  showRegMsg('등록 중...', 'info');

  const fd = new FormData();
  fd.append('name', name);
  fd.append('file', selectedTplFile);

  try {
    const res = await fetch('/templates', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    showRegMsg(`✓ 등록 완료 — ${data.name} (필드: ${data.fields.join(', ')})`, 'success');
    tplNameInput.value = '';
    setSelectedFile(null);
    loadTemplateList();
    reloadUploadTemplates(); // 변환 탭 드롭다운도 갱신
  } catch (e) {
    showRegMsg('✗ 등록 실패: ' + e.message, 'error');
  } finally {
    updateRegBtnState();
  }
});

function showRegMsg(text, type) {
  tplRegMsg.textContent = text;
  tplRegMsg.className = `form-msg msg-${type}`;
}

// ── Template list ─────────────────────────────────────────────────────────────
document.getElementById('tpl-refresh-btn').addEventListener('click', loadTemplateList);

async function loadTemplateList() {
  const container = document.getElementById('tpl-list');
  container.innerHTML = '<p class="loading">불러오는 중...</p>';
  try {
    const res = await fetch('/templates');
    const list = await res.json();
    renderTemplateList(list);
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
  const card = document.createElement('div');
  card.className = 'tpl-item';
  card.dataset.id = t.template_id;

  card.innerHTML = `
    <div class="tpl-item-header">
      <div>
        <span class="tpl-name">${escHtml(t.name)}</span>
        <span class="tpl-id">${t.template_id}</span>
      </div>
      <div class="tpl-actions">
        <button class="btn-sm btn-outline prompt-btn" title="커스텀 프롬프트 편집">
          ${t.has_custom_prompt ? '✎ 프롬프트 수정' : '+ 프롬프트'}
        </button>
        <button class="btn-sm btn-danger delete-btn" title="삭제">삭제</button>
      </div>
    </div>
    <div class="tpl-fields">
      ${t.fields.map(f => `<span class="field-chip">${escHtml(f)}</span>`).join('')}
    </div>
    ${t.has_custom_prompt
      ? '<div class="tpl-prompt-badge">커스텀 프롬프트 설정됨</div>'
      : ''}
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
const modal        = document.getElementById('prompt-modal');
const modalTitle   = document.getElementById('modal-title');
const modalPrompt  = document.getElementById('modal-prompt');
const modalCancel  = document.getElementById('modal-cancel');
const modalSave    = document.getElementById('modal-save');

let _editingId = null;

async function openPromptModal(t) {
  _editingId = t.template_id;
  modalTitle.textContent = `프롬프트 편집 — ${t.name}`;

  // 현재 프롬프트 조회
  try {
    const res = await fetch(`/templates/${t.template_id}`);
    const detail = await res.json();
    modalPrompt.value = detail.custom_prompt || '';
  } catch {
    modalPrompt.value = '';
  }

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
  } catch (e) {
    alert('저장 실패: ' + e.message);
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function escHtml(str) {
  return str.replace(/[&<>"']/g, c =>
    ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

// 변환 탭 템플릿 드롭다운 갱신 (app.js에 정의된 함수 재사용)
function reloadUploadTemplates() {
  if (typeof loadTemplates === 'function') loadTemplates();
}
