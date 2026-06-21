// ── STATE ──
let selectedFile = null;
let activeTab = 'file';

// ── TAB SWITCHING ──
const tabFile = document.getElementById('tabFile');
const tabPaste = document.getElementById('tabPaste');
const fileTabContent = document.getElementById('fileTabContent');
const pasteTabContent = document.getElementById('pasteTabContent');
const pasteArea = document.getElementById('pasteArea');

tabFile.addEventListener('click', () => switchTab('file'));
tabPaste.addEventListener('click', () => switchTab('paste'));

function switchTab(tab) {
  activeTab = tab;
  tabFile.classList.toggle('active', tab === 'file');
  tabPaste.classList.toggle('active', tab === 'paste');
  fileTabContent.classList.toggle('active', tab === 'file');
  pasteTabContent.classList.toggle('active', tab === 'paste');
  updateAnalyzeBtn();
}

// ── FILE UPLOAD ──
const resumeFileInput = document.getElementById('resumeFile');
const uploadZone = document.getElementById('uploadZone');
const fileSelected = document.getElementById('fileSelected');
const fileNameSpan = document.getElementById('fileName');
const removeFileBtn = document.getElementById('removeFile');
const analyzeBtn = document.getElementById('analyzeBtn');
const btnText = document.getElementById('btnText');
const btnLoader = document.getElementById('btnLoader');
const uploadSection = document.getElementById('uploadSection');
const resultsSection = document.getElementById('resultsSection');
const backBtn = document.getElementById('backBtn');
const jobDescriptionInput = document.getElementById('jobDescription');

uploadZone.addEventListener('click', (e) => {
  if (e.target.tagName === 'LABEL') return; // let the label handle it natively, avoid double-trigger on iOS
  resumeFileInput.click();
});
uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
resumeFileInput.addEventListener('change', () => {
  // TEMPORARY DEBUG — remove once iOS issue is diagnosed
  alert('Change event fired. Files: ' + resumeFileInput.files.length);
  if (resumeFileInput.files[0]) setFile(resumeFileInput.files[0]);
});

function setFile(file) {
  selectedFile = file;
  fileNameSpan.textContent = file.name;
  fileSelected.style.display = 'flex';
  uploadZone.style.display = 'none';
  updateAnalyzeBtn();
}

removeFileBtn.addEventListener('click', () => {
  selectedFile = null;
  resumeFileInput.value = '';
  fileSelected.style.display = 'none';
  uploadZone.style.display = 'block';
  updateAnalyzeBtn();
});

pasteArea.addEventListener('input', updateAnalyzeBtn);

function updateAnalyzeBtn() {
  const hasFile = activeTab === 'file' && selectedFile;
  const hasPaste = activeTab === 'paste' && pasteArea.value.trim().length > 50;
  analyzeBtn.disabled = !(hasFile || hasPaste);
}

backBtn.addEventListener('click', () => {
  resultsSection.style.display = 'none';
  uploadSection.style.display = 'block';
});

// ── ANALYZE ──
analyzeBtn.addEventListener('click', async () => {
  if (analyzeBtn.disabled) return;

  btnText.style.display = 'none';
  btnLoader.style.display = 'inline';
  analyzeBtn.disabled = true;

  const formData = new FormData();
  if (activeTab === 'file' && selectedFile) {
    formData.append('resume', selectedFile);
  } else {
    formData.append('resume_text', pasteArea.value.trim());
  }
  formData.append('job_description', jobDescriptionInput.value.trim());

  try {
    const res = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }

    renderResults(data);
    uploadSection.style.display = 'none';
    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    alert('Something went wrong. Check your connection and try again.');
    console.error(err);
  } finally {
    btnText.style.display = 'inline';
    btnLoader.style.display = 'none';
    updateAnalyzeBtn();
  }
});

// ── RENDER REPORT ──
function renderResults(data) {
  renderMetricRow(data);
  renderVerdict(data);
  renderCategoryBars(data);
  renderKeywordTags(data);
  renderSectionBars(data);
  renderSectionsDetected(data);
  renderAtsChecklist(data);
  renderStrengthsImprovements(data);
  renderTips(data);
  renderBulletRewrites(data);
  renderGrammar(data);
  renderInterviewQuestions(data);
}

function scoreClass(val) {
  if (val >= 75) return 'score-green';
  if (val >= 45) return 'score-amber';
  return 'score-red';
}

function renderMetricRow(data) {
  const overall = data.overall_score ?? 0;
  const ats = data.ats_score ?? 0;
  const match = data.jd_match_percent ?? 0;
  const matchLabel = data.has_jd ? 'Job match' : 'Career strength';
  const matchSub = data.has_jd ? (data.role_name || 'vs job description') : 'general estimate';

  const applyMap = {
    yes: { icon: '✓ Yes', cls: 'score-green' },
    maybe: { icon: '~ Maybe', cls: 'score-amber' },
    no: { icon: '✕ No', cls: 'score-red' }
  };
  const apply = applyMap[data.apply_recommendation] || applyMap.maybe;

  document.getElementById('metricRow').innerHTML = `
    <div class="metric-card">
      <div class="metric-label">Overall Score</div>
      <div class="metric-value ${scoreClass(overall)}">${overall}<span class="unit">/100</span></div>
    </div>
    <div class="metric-card">
      <div class="metric-label">ATS Score</div>
      <div class="metric-value ${scoreClass(ats)}">${ats}<span class="unit">/100</span></div>
    </div>
    <div class="metric-card">
      <div class="metric-label">${matchLabel}</div>
      <div class="metric-value ${scoreClass(match)}">${match}<span class="unit">%</span></div>
      <div class="metric-sub">${matchSub}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">${data.has_jd ? 'Apply?' : 'Outlook'}</div>
      <div class="metric-value ${apply.cls}" style="font-size:18px; padding-top:4px;">${apply.icon}</div>
      ${data.deadline_note ? `<div class="metric-sub">${data.deadline_note}</div>` : ''}
    </div>
  `;
}

function renderVerdict(data) {
  const card = document.getElementById('verdictCard');
  const rec = data.apply_recommendation || 'maybe';
  const iconMap = { yes: '🙂', maybe: '🤔', no: '⚠️' };
  card.className = `verdict-card ${rec}`;
  document.getElementById('verdictIcon').textContent = iconMap[rec] || '🤔';
  document.getElementById('verdictTitle').textContent = data.verdict_title || (data.has_jd ? 'Assessment' : 'Career positioning');
  document.getElementById('verdictText').textContent = data.verdict_text || data.summary_feedback || '';
}

function renderCategoryBars(data) {
  const cats = data.keyword_categories ?? [];
  const container = document.getElementById('categoryBars');
  if (cats.length === 0) { container.innerHTML = ''; return; }

  container.innerHTML = cats.map(c => {
    const pct = c.match_percent ?? 0;
    let color = 'var(--green)';
    if (pct < 40) color = 'var(--red)';
    else if (pct < 70) color = 'var(--orange)';
    return `
      <div class="cat-bar-row">
        <div class="cat-bar-label"><span class="name">${c.name}</span><span class="pct">${pct}%</span></div>
        <div class="cat-bar-track"><div class="cat-bar-fill" style="width:0%; background:${color};" data-target="${pct}%"></div></div>
      </div>`;
  }).join('');

  setTimeout(() => {
    container.querySelectorAll('.cat-bar-fill').forEach(bar => bar.style.width = bar.dataset.target);
  }, 100);
}

function renderKeywordTags(data) {
  const found = data.keywords_found ?? [];
  const weak = data.keywords_weak ?? [];
  const missing = data.keywords_missing ?? [];

  document.getElementById('kwFound').innerHTML = found.map(k => `<span class="keyword-tag found">${k}</span>`).join('') || '<span style="font-size:12px;color:var(--muted)">None detected</span>';

  const weakGroup = document.getElementById('kwWeakGroup');
  if (weak.length > 0) {
    document.getElementById('kwWeak').innerHTML = weak.map(k => `<span class="keyword-tag weak">${k}</span>`).join('');
    weakGroup.style.display = 'block';
  } else {
    weakGroup.style.display = 'none';
  }

  const missingGroup = document.getElementById('kwMissingGroup');
  if (missing.length > 0) {
    document.getElementById('kwMissing').innerHTML = missing.map(k => `<span class="keyword-tag missing">${k}</span>`).join('');
    missingGroup.style.display = 'block';
  } else {
    missingGroup.style.display = 'none';
  }
}

function renderSectionBars(data) {
  const sectionBars = document.getElementById('sectionBars');
  sectionBars.innerHTML = '';
  const scores = data.section_scores ?? {};
  const labels = { contact: 'Contact', experience: 'Experience', skills: 'Skills', education: 'Education', formatting: 'Formatting' };
  Object.entries(labels).forEach(([key, label]) => {
    const val = scores[key] ?? 0;
    sectionBars.innerHTML += `
      <div class="bar-row">
        <div class="bar-label">${label}</div>
        <div class="bar-track"><div class="bar-fill" style="width:0%" data-target="${val}%"></div></div>
        <div class="bar-val">${val}</div>
      </div>`;
  });
  setTimeout(() => {
    sectionBars.querySelectorAll('.bar-fill').forEach(bar => bar.style.width = bar.dataset.target);
  }, 100);
}

function renderSectionsDetected(data) {
  const sectionsDetected = document.getElementById('sectionsDetected');
  sectionsDetected.innerHTML = '';
  const detected = data.sections_detected ?? {};
  const sectionNames = { contact: 'Contact', summary: 'Summary', experience: 'Experience', education: 'Education', skills: 'Skills', projects: 'Projects' };
  Object.entries(sectionNames).forEach(([key, name]) => {
    const found = detected[key];
    sectionsDetected.innerHTML += `<span class="section-tag ${found ? 'found' : 'missing'}">${found ? '✓' : '✗'} ${name}</span>`;
  });
}

function renderAtsChecklist(data) {
  const checks = data.ats_format_checks ?? [];
  const iconMap = { ok: '✓', warn: '⚠', bad: '✕' };
  document.getElementById('atsChecklist').innerHTML = checks.map(c => `
    <li><span class="check-icon ${c.status}">${iconMap[c.status] || '•'}</span><span>${c.text}</span></li>
  `).join('') || '<li><span style="color:var(--muted); font-size:13px;">No format issues detected.</span></li>';
}

function renderStrengthsImprovements(data) {
  document.getElementById('strengthsList').innerHTML = (data.strengths ?? []).map(s => `<li>${s}</li>`).join('');
  document.getElementById('improvementsList').innerHTML = (data.improvements ?? []).map(i => `<li>${i}</li>`).join('');
}

function renderTips(data) {
  const tips = data.tips ?? [];
  const block = document.getElementById('tipsBlock');
  if (tips.length === 0) { block.style.display = 'none'; return; }
  block.style.display = 'block';
  document.getElementById('tipsList').innerHTML = tips.map(t => `
    <div class="tip-card"><strong>${t.title}</strong>${t.body}</div>
  `).join('');
}

function renderBulletRewrites(data) {
  const weak = data.weak_bullets ?? [];
  const rewritten = data.rewritten_bullets ?? [];
  const bulletsBlock = document.getElementById('bulletsBlock');
  const bulletRewrites = document.getElementById('bulletRewrites');
  if (weak.length > 0) {
    bulletRewrites.innerHTML = weak.map((b, i) => `
      <div class="bullet-pair">
        <div class="bullet-before">✗ ${b}</div>
        <div class="bullet-arrow">↓ Suggested rewrite</div>
        <div class="bullet-after">✓ ${rewritten[i] ?? 'N/A'}</div>
      </div>`).join('');
    bulletsBlock.style.display = 'block';
  } else {
    bulletsBlock.style.display = 'none';
  }
}

function renderGrammar(data) {
  const grammar = data.grammar_issues ?? [];
  const grammarBlock = document.getElementById('grammarBlock');
  if (grammar.length > 0) {
    document.getElementById('grammarList').innerHTML = grammar.map(g => `<li>${g}</li>`).join('');
    grammarBlock.style.display = 'block';
  } else {
    grammarBlock.style.display = 'none';
  }
}

function renderInterviewQuestions(data) {
  document.getElementById('interviewList').innerHTML = (data.interview_questions ?? []).map(q => `<li>${q}</li>`).join('');
}

// ── CHAT HANDOFF ──
document.getElementById('chatCtaBtn').addEventListener('click', async () => {
  try {
    const res = await fetch('/chat/start', { method: 'POST' });
    const data = await res.json();
    if (data.error) {
      alert(data.error);
      return;
    }
    window.location.href = '/chat?from_report=1';
  } catch (err) {
    alert('Could not start chat. Please try again.');
  }
});

// ── PDF DOWNLOAD ──
document.getElementById('downloadPdfBtn').addEventListener('click', async () => {
  const btn = document.getElementById('downloadPdfBtn');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Generating PDF...';

  try {
    const res = await fetch('/api/export-pdf');

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert('Error: ' + (data.error || 'Could not generate PDF.'));
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'resumeiq-report.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

  } catch (err) {
    alert('Could not download PDF. Please try again.');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});