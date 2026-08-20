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

// ── DEEP AGENT PIPELINE (Resume Optimizer + Market Intel + Skill Roadmap) ──
const runAgentsBtn = document.getElementById('runAgentsBtn');
const agentsBtnText = document.getElementById('agentsBtnText');
const agentsBtnLoader = document.getElementById('agentsBtnLoader');
const agentsResults = document.getElementById('agentsResults');

runAgentsBtn.addEventListener('click', async () => {
  runAgentsBtn.disabled = true;
  agentsBtnText.style.display = 'none';
  agentsBtnLoader.style.display = 'inline';

  try {
    const res = await fetch('/agents/pipeline', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const data = await res.json();

    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }

    renderAgentsResults(data);
    agentsResults.style.display = 'block';
    runAgentsBtn.style.display = 'none';

  } catch (err) {
    alert('Something went wrong running the agent pipeline. Please try again.');
    console.error(err);
  } finally {
    agentsBtnText.style.display = 'inline';
    agentsBtnLoader.style.display = 'none';
    runAgentsBtn.disabled = false;
  }
});

function renderAgentsResults(data) {
  const opt = data.optimized_resume || {};
  const mi = data.market_intel || {};
  const gap = data.skill_gap || {};
  const roadmap = data.roadmap || {};
  const errors = data.errors || [];

  let html = '';

  if (errors.length > 0) {
    html += `<div class="agent-error-box">${errors.map(e => `<div>⚠ ${e}</div>`).join('')}</div>`;
  }

  // ── Resume Optimizer ──
  html += `<div class="agent-subsection">
    <div class="agent-subtitle">✏️ Resume Optimizer <span class="agent-tag">Generator + Critic</span></div>`;

  if (opt.note) {
    html += `<p class="agent-note">${opt.note}</p>`;
  } else if (opt.optimized_text) {
    const delta = opt.ats_formula_score_delta;
    const deltaCls = delta > 0 ? 'score-green' : (delta < 0 ? 'score-red' : '');
    html += `
      <div class="agent-score-row">
        <span class="agent-score-pill">ATS fit before: <strong>${opt.ats_formula_score_before ?? '—'}</strong></span>
        <span class="agent-score-pill">after: <strong>${opt.ats_formula_score_after ?? '—'}</strong></span>
        <span class="agent-score-pill ${deltaCls}">Δ ${delta > 0 ? '+' : ''}${delta ?? '—'}</span>
        <span class="agent-score-pill">${opt.approved ? '✓ Critic approved' : '⚠ Critic flagged issues'} · ${opt.rounds ?? 0} round(s)</span>
      </div>`;

    if ((opt.fabrication_flags || []).length > 0) {
      html += `<div class="agent-note warn">Fabrication flags: ${opt.fabrication_flags.join('; ')}</div>`;
    }

    html += `<details class="agent-details"><summary>View optimized resume text</summary><pre class="agent-pre">${escapeHtml(opt.optimized_text)}</pre></details>`;

    if ((opt.changes || []).length > 0) {
      html += `<div class="agent-changes">` + opt.changes.map(c => `
        <div class="bullet-pair">
          <div class="bullet-before">✗ [${c.section || 'General'}] ${c.before || ''}</div>
          <div class="bullet-arrow">↓ ${c.reason || 'Suggested rewrite'}</div>
          <div class="bullet-after">✓ ${c.after || ''}</div>
        </div>`).join('') + `</div>`;
    }
  } else {
    html += `<p class="agent-note">No optimization result available.</p>`;
  }
  html += `</div>`;

  // ── Market Intel ──
  html += `<div class="agent-subsection">
    <div class="agent-subtitle">📈 Job Market Intelligence <span class="agent-tag">${mi.match_method === 'llm_fallback' ? 'LLM match' : 'Keyword match'}</span></div>`;

  if (mi.matched_role) {
    html += `<p class="agent-note">Matched role: <strong>${mi.matched_role}</strong>${mi.taxonomy_last_updated ? ` · taxonomy updated ${mi.taxonomy_last_updated}` : ''}</p>`;
    html += `<div class="keyword-tags">` + (mi.in_demand_skills || []).map(s =>
      `<span class="keyword-tag skill-demand" title="Demand score: ${s.demand_score}/100 · ${s.category}">${s.name} <span class="demand-score">${s.demand_score}</span></span>`
    ).join('') + `</div>`;
  } else {
    html += `<p class="agent-note">No market intel available.</p>`;
  }
  html += `</div>`;

  // ── Skill Gap + Roadmap ──
  html += `<div class="agent-subsection">
    <div class="agent-subtitle">🗺️ Skill Gap &amp; Learning Roadmap <span class="agent-tag">Coverage ${gap.coverage_percent ?? 0}%</span></div>`;

  if ((gap.covered_skills || []).length > 0 || (gap.missing_skills || []).length > 0) {
    html += `<div class="kw-group"><div class="kw-label">Covered</div><div class="keyword-tags">` +
      (gap.covered_skills || []).map(s => `<span class="keyword-tag found">${s.name}</span>`).join('') +
      `</div></div>`;
    html += `<div class="kw-group"><div class="kw-label">Missing</div><div class="keyword-tags">` +
      (gap.missing_skills || []).map(s => `<span class="keyword-tag missing">${s.name}</span>`).join('') +
      `</div></div>`;
  }

  if ((roadmap.phases || []).length > 0) {
    if (roadmap.summary) html += `<p class="agent-note">${roadmap.summary}</p>`;
    html += `<div class="roadmap-phases">` + roadmap.phases.map((p, i) => `
      <div class="phase-card">
        <div class="phase-header"><span class="phase-num">${i + 1}</span><span class="phase-title">${p.title || ''}</span><span class="phase-duration">${p.duration_weeks ?? '?'} wk</span></div>
        <div class="phase-skills">${(p.skills || []).map(s => `<span class="keyword-tag weak">${s}</span>`).join('')}</div>
        ${p.milestone ? `<div class="phase-milestone">🏁 ${p.milestone}</div>` : ''}
        ${(p.resource_suggestions || []).length > 0 ? `<ul class="phase-resources">${p.resource_suggestions.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
      </div>`).join('') + `</div>`;
  } else if (roadmap.summary) {
    html += `<p class="agent-note">${roadmap.summary}</p>`;
  }
  html += `</div>`;

  agentsResults.innerHTML = html;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

// ── LIVE MOCK INTERVIEW (Interviewer + Evaluator agents) ──
const startInterviewBtn = document.getElementById('startInterviewBtn');
const startInterviewBtnText = document.getElementById('startInterviewBtnText');
const startInterviewBtnLoader = document.getElementById('startInterviewBtnLoader');
const interviewIntro = document.getElementById('interviewIntro');
const interviewSession = document.getElementById('interviewSession');
const interviewQuestionCard = document.getElementById('interviewQuestionCard');
const interviewAnswerArea = document.getElementById('interviewAnswerArea');
const interviewEvaluation = document.getElementById('interviewEvaluation');
const submitAnswerBtn = document.getElementById('submitAnswerBtn');
const submitAnswerBtnText = document.getElementById('submitAnswerBtnText');
const submitAnswerBtnLoader = document.getElementById('submitAnswerBtnLoader');
const finishInterviewBtn = document.getElementById('finishInterviewBtn');
const interviewSummary = document.getElementById('interviewSummary');

function renderQuestionCard(q) {
  const typeTag = q.question_type === 'technical' ? '⚙️ Technical' : '💬 Behavioral';
  interviewQuestionCard.innerHTML = `
    <div class="q-meta"><span class="agent-tag">${typeTag}</span>${q.focus_area ? `<span class="agent-tag">${q.focus_area}</span>` : ''}</div>
    <div class="q-text">${q.question || ''}</div>`;
}

startInterviewBtn.addEventListener('click', async () => {
  startInterviewBtn.disabled = true;
  startInterviewBtnText.style.display = 'none';
  startInterviewBtnLoader.style.display = 'inline';

  try {
    const res = await fetch('/agents/interview/start', { method: 'POST' });
    const data = await res.json();
    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }
    renderQuestionCard(data.current_question || {});
    interviewAnswerArea.value = '';
    interviewEvaluation.innerHTML = '';
    interviewIntro.style.display = 'none';
    interviewSession.style.display = 'block';
    interviewSummary.style.display = 'none';
  } catch (err) {
    alert('Could not start the mock interview. Please try again.');
    console.error(err);
  } finally {
    startInterviewBtnText.style.display = 'inline';
    startInterviewBtnLoader.style.display = 'none';
    startInterviewBtn.disabled = false;
  }
});

submitAnswerBtn.addEventListener('click', async () => {
  const answer = interviewAnswerArea.value.trim();
  if (!answer) { alert('Please type an answer before submitting.'); return; }

  submitAnswerBtn.disabled = true;
  submitAnswerBtnText.style.display = 'none';
  submitAnswerBtnLoader.style.display = 'inline';

  try {
    const res = await fetch('/agents/interview/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer })
    });
    const data = await res.json();
    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }
    renderEvaluation(data.evaluation);
    renderQuestionCard(data.current_question || {});
    interviewAnswerArea.value = '';
  } catch (err) {
    alert('Could not submit your answer. Please try again.');
    console.error(err);
  } finally {
    submitAnswerBtnText.style.display = 'inline';
    submitAnswerBtnLoader.style.display = 'none';
    submitAnswerBtn.disabled = false;
  }
});

function renderEvaluation(evaluation) {
  if (!evaluation) { interviewEvaluation.innerHTML = ''; return; }
  const scores = evaluation.scores || {};
  const dimLabels = { structure_star: 'Structure (STAR)', specificity: 'Specificity', relevance_to_role: 'Relevance', confidence_clarity: 'Clarity' };

  let html = `<div class="eval-card">
    <div class="eval-header">Previous answer &middot; overall <strong>${evaluation.overall_score ?? '—'}/10</strong></div>
    <div class="bar-grid">`;
  Object.entries(dimLabels).forEach(([key, label]) => {
    const val = scores[key];
    const pct = val != null ? val * 10 : 0;
    html += `
      <div class="bar-row">
        <div class="bar-label">${label}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="bar-val">${val ?? '—'}</div>
      </div>`;
  });
  html += `</div>`;

  if ((evaluation.strengths || []).length > 0) {
    html += `<div class="kw-group"><div class="kw-label">Strengths</div><ul class="result-list green">${evaluation.strengths.map(s => `<li>${s}</li>`).join('')}</ul></div>`;
  }
  if ((evaluation.improvements || []).length > 0) {
    html += `<div class="kw-group"><div class="kw-label">Improvements</div><ul class="result-list orange">${evaluation.improvements.map(s => `<li>${s}</li>`).join('')}</ul></div>`;
  }
  if (evaluation.ideal_answer_sketch) {
    html += `<div class="tip-card"><strong>What a stronger answer would include</strong>${evaluation.ideal_answer_sketch}</div>`;
  }
  html += `</div>`;

  interviewEvaluation.innerHTML = html;
}

finishInterviewBtn.addEventListener('click', async () => {
  finishInterviewBtn.disabled = true;
  try {
    const res = await fetch('/agents/interview/summary');
    const data = await res.json();
    if (data.error) {
      alert('Error: ' + data.error);
      return;
    }
    renderInterviewSummary(data);
    interviewSession.style.display = 'none';
    interviewSummary.style.display = 'block';
  } catch (err) {
    alert('Could not generate the interview summary. Please try again.');
    console.error(err);
  } finally {
    finishInterviewBtn.disabled = false;
  }
});

function renderInterviewSummary(data) {
  const dimLabels = { structure_star: 'Structure (STAR)', specificity: 'Specificity', relevance_to_role: 'Relevance', confidence_clarity: 'Clarity' };
  const dims = data.dimension_averages || {};

  let html = `
    <div class="verdict-card maybe">
      <div class="verdict-icon">🎤</div>
      <div class="verdict-body">
        <div class="verdict-title">Interview Summary &middot; ${data.questions_answered ?? 0} question(s) answered</div>
        <div class="verdict-text">${data.summary || ''}</div>
      </div>
    </div>
    <div class="metric-row">
      <div class="metric-card">
        <div class="metric-label">Average Score</div>
        <div class="metric-value ${scoreClass((data.average_overall_score ?? 0) * 10)}">${data.average_overall_score ?? '—'}<span class="unit">/10</span></div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Weakest Area</div>
        <div class="metric-value" style="font-size:16px; padding-top:6px;">${dimLabels[data.weakest_dimension] || '—'}</div>
      </div>
    </div>
    <div class="bar-grid">`;
  Object.entries(dimLabels).forEach(([key, label]) => {
    const val = dims[key];
    const pct = val != null ? val * 10 : 0;
    html += `
      <div class="bar-row">
        <div class="bar-label">${label}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="bar-val">${val ?? '—'}</div>
      </div>`;
  });
  html += `</div><button class="agent-run-btn ghost" id="restartInterviewBtn" style="margin-top:16px;">Start Over</button>`;

  interviewSummary.innerHTML = html;

  document.getElementById('restartInterviewBtn').addEventListener('click', async () => {
    try {
      await fetch('/agents/interview/reset', { method: 'POST' });
    } catch (err) { console.error(err); }
    interviewSummary.style.display = 'none';
    interviewIntro.style.display = 'block';
  });
}