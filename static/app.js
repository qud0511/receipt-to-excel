'use strict';

const templateSelect = document.getElementById('template-select');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const submitBtn = document.getElementById('submit-btn');
const progressSection = document.getElementById('progress-section');
const resultSection = document.getElementById('result-section');

let selectedFiles = [];

// ── Template loading ──────────────────────────────────────────────────────────

async function loadTemplates() {
  try {
    const res = await fetch('/templates');
    const data = await res.json();
    templateSelect.innerHTML = '<option value="">템플릿 선택...</option>';
    data.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.template_id;
      opt.textContent = t.name;
      templateSelect.appendChild(opt);
    });
  } catch {
    templateSelect.innerHTML = '<option value="">템플릿 로드 실패</option>';
  }
}

// ── File handling ─────────────────────────────────────────────────────────────

function renderFileList() {
  fileList.innerHTML = '';
  selectedFiles.forEach((f, i) => {
    const chip = document.createElement('div');
    chip.className = 'file-chip';
    chip.innerHTML = `<span>${f.name}</span><button title="제거" data-i="${i}">×</button>`;
    fileList.appendChild(chip);
  });
}

fileList.addEventListener('click', e => {
  const btn = e.target.closest('button[data-i]');
  if (!btn) return;
  selectedFiles.splice(Number(btn.dataset.i), 1);
  renderFileList();
});

function addFiles(incoming) {
  const allowed = ['image/jpeg', 'image/png', 'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation'];
  const newFiles = Array.from(incoming).filter(f => allowed.includes(f.type));
  selectedFiles = [...selectedFiles, ...newFiles];
  renderFileList();
}

dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  addFiles(e.dataTransfer.files);
});

// ── Job submission ────────────────────────────────────────────────────────────

submitBtn.addEventListener('click', async () => {
  if (!templateSelect.value) return alert('템플릿을 선택하세요.');
  if (selectedFiles.length === 0) return alert('파일을 추가하세요.');

  submitBtn.disabled = true;
  progressSection.style.display = 'block';
  resultSection.style.display = 'none';
  setStatus('pending');

  const fd = new FormData();
  fd.append('template_id', templateSelect.value);
  selectedFiles.forEach(f => fd.append('files', f));

  let jobId;
  try {
    const res = await fetch('/jobs', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    jobId = data.job_id;
    updateProgress(0, data.total, '');
  } catch (e) {
    alert('업로드 실패: ' + e.message);
    submitBtn.disabled = false;
    return;
  }

  streamJob(jobId);
});

// ── SSE streaming ─────────────────────────────────────────────────────────────

function streamJob(jobId) {
  const es = new EventSource(`/jobs/${jobId}/stream`);

  es.onmessage = e => {
    const job = JSON.parse(e.data);
    if (job.error) { es.close(); showError(job.error); return; }

    setStatus(job.status);
    updateProgress(job.done ?? 0, job.total ?? 1, job.current_file ?? '');
    renderFailedFiles(job.failed_files ?? []);

    if (job.status === 'completed' || job.status === 'failed') {
      es.close();
      submitBtn.disabled = false;
      if (job.status === 'completed') showResult(jobId, job.pdf_url);
    }
  };

  es.onerror = () => { es.close(); showError('연결이 끊겼습니다.'); submitBtn.disabled = false; };
}

// ── UI helpers ────────────────────────────────────────────────────────────────

function setStatus(status) {
  const badge = document.getElementById('status-badge');
  const labels = { pending: '대기 중', running: '처리 중', completed: '완료', failed: '실패' };
  badge.textContent = labels[status] ?? status;
  badge.className = `status-badge badge-${status}`;
}

function updateProgress(done, total, currentFile) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('progress-label').textContent =
    currentFile ? `처리 중: ${currentFile} (${done}/${total})` : `${done}/${total} 완료`;
}

function renderFailedFiles(files) {
  const ul = document.getElementById('failed-list');
  ul.innerHTML = '';
  files.forEach(f => {
    const li = document.createElement('li');
    li.textContent = f;
    ul.appendChild(li);
  });
}

function showResult(jobId, pdfUrl) {
  resultSection.style.display = 'block';
  const btns = document.getElementById('download-btns');
  btns.innerHTML = '';

  const excelBtn = document.createElement('a');
  excelBtn.href = `/jobs/${jobId}/result`;
  excelBtn.download = `지출결의서_${jobId}.xlsx`;
  excelBtn.className = 'btn-download btn-excel';
  excelBtn.textContent = '엑셀 다운로드';
  btns.appendChild(excelBtn);

  if (pdfUrl) {
    const pdfBtn = document.createElement('a');
    pdfBtn.href = pdfUrl;
    pdfBtn.download = `영수증_${jobId}.pdf`;
    pdfBtn.className = 'btn-download btn-pdf';
    pdfBtn.textContent = '영수증 PDF 다운로드';
    btns.appendChild(pdfBtn);
  }
}

function showError(msg) {
  document.getElementById('progress-label').textContent = '오류: ' + msg;
  setStatus('failed');
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadTemplates();
