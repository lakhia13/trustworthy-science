import type { PaperSummary } from '../../api/client';

interface ReportAnswer {
  question: string;
  answer: string;
  papersUsed: PaperSummary[];
  tookSeconds: number;
}

interface ReportData {
  addedPapers: PaperSummary[];
  excludedPapers: PaperSummary[];
  graphStats: Record<string, number>;
  answers: ReportAnswer[];
}

function tierIcon(tier: string): string {
  if (tier === 'Trusted') return '✅';
  if (tier === 'Caution') return '⚠️';
  return '❌';
}

function tierClass(tier: string): string {
  if (tier === 'Trusted') return 'tier-trusted';
  if (tier === 'Caution') return 'tier-caution';
  return 'tier-untrusted';
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function paperRows(papers: PaperSummary[]): string {
  if (papers.length === 0) return '<tr><td colspan="5" style="color:#9ca3af;text-align:center;padding:16px">No papers</td></tr>';
  return papers.map((p, i) => `
    <tr>
      <td style="color:#9ca3af;font-family:monospace">${String(i + 1).padStart(2, '0')}</td>
      <td><a href="https://doi.org/${escapeHtml(p.doi)}" target="_blank" style="color:#1a1a2e;text-decoration:none;font-weight:500">${escapeHtml(p.title)}</a></td>
      <td class="doi-cell"><a href="https://doi.org/${escapeHtml(p.doi)}" target="_blank" style="color:#6b7280">${escapeHtml(p.doi)}</a></td>
      <td><span class="${tierClass(p.tier)}">${tierIcon(p.tier)} ${escapeHtml(p.tier)}</span></td>
      <td><span class="score-badge ${tierClass(p.tier)}">${p.score}</span><span style="font-size:10px;color:#9ca3af">/100</span></td>
    </tr>
  `).join('');
}

function qaBlocks(answers: ReportAnswer[]): string {
  return answers.map((a, i) => `
    <div class="qa-block">
      <div class="qa-number">Question ${String(i + 1).padStart(2, '0')}</div>
      <div class="qa-question">${escapeHtml(a.question)}</div>
      <div class="qa-answer">${escapeHtml(a.answer)}</div>
      ${a.papersUsed.length > 0 ? `
        <div class="sources-label">Sources cited (${a.papersUsed.length})</div>
        <div>
          ${a.papersUsed.map(p => `
            <div class="source-row">
              <span class="${tierClass(p.tier)}">${tierIcon(p.tier)}</span>
              <a href="https://doi.org/${escapeHtml(p.doi)}" target="_blank" style="color:#1a1a2e;font-weight:500;text-decoration:none">${escapeHtml(p.title)}</a>
              <span style="color:#9ca3af;font-family:monospace;font-size:10px;margin-left:auto">${p.score}/100</span>
            </div>
          `).join('')}
        </div>
      ` : ''}
      <div class="qa-meta">⏱ Generated in ${a.tookSeconds.toFixed(1)}s</div>
    </div>
  `).join('');
}

export function exportReport(data: ReportData): void {
  const { addedPapers, excludedPapers, graphStats, answers } = data;
  const now = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Literature Review Report — Trustworthy Science</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; color: #111; background: #fff; padding: 40px; max-width: 860px; margin: 0 auto; }

    .header { border-bottom: 3px solid #1a1a2e; padding-bottom: 20px; margin-bottom: 28px; }
    .logo { font-size: 13px; font-weight: 700; color: #4d88ff; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 6px; }
    .title { font-size: 26px; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
    .meta { font-size: 12px; color: #666; }

    .section-title { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #666; border-bottom: 1px solid #eee; padding-bottom: 8px; margin: 28px 0 14px; }

    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 8px; }
    .stat-box { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px; }
    .stat-value { font-size: 22px; font-weight: 700; font-family: monospace; }
    .stat-label { font-size: 11px; color: #666; margin-top: 2px; }
    .stat-trusted .stat-value { color: #16a34a; }
    .stat-caution .stat-value { color: #d97706; }
    .stat-excluded .stat-value { color: #dc2626; }
    .stat-default .stat-value { color: #1a1a2e; }

    table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 4px; }
    th { text-align: left; padding: 8px 10px; background: #f9fafb; font-weight: 600; font-size: 11px; color: #374151; border-bottom: 2px solid #e5e7eb; }
    td { padding: 9px 10px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
    tr:last-child td { border-bottom: none; }
    .doi-cell { font-family: monospace; font-size: 10px; color: #6b7280; }
    .score-badge { display: inline-block; font-weight: 700; font-family: monospace; font-size: 12px; }
    .tier-trusted { color: #16a34a; }
    .tier-caution { color: #d97706; }
    .tier-untrusted { color: #dc2626; }

    .qa-block { margin-bottom: 28px; page-break-inside: avoid; }
    .qa-number { font-size: 10px; font-weight: 700; color: #4d88ff; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 4px; }
    .qa-question { font-size: 15px; font-weight: 600; color: #1a1a2e; margin-bottom: 12px; line-height: 1.4; }
    .qa-answer { font-size: 13px; line-height: 1.7; color: #374151; background: #f9fafb; border-left: 3px solid #4d88ff; padding: 14px 16px; border-radius: 0 6px 6px 0; margin-bottom: 12px; white-space: pre-wrap; }
    .sources-label { font-size: 10px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
    .source-row { display: flex; align-items: center; gap: 10px; font-size: 11px; padding: 5px 0; border-bottom: 1px solid #f3f4f6; }
    .source-row:last-child { border-bottom: none; }
    .qa-meta { font-size: 10px; color: #9ca3af; margin-top: 8px; }

    .excluded-row { font-size: 12px; color: #dc2626; padding: 6px 0; border-bottom: 1px solid #fef2f2; display: flex; align-items: center; gap: 8px; }
    .excluded-row:last-child { border-bottom: none; }

    .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #9ca3af; display: flex; justify-content: space-between; }

    @media print {
      body { padding: 20px; }
      .qa-block { page-break-inside: avoid; }
    }
  </style>
</head>
<body>

  <div class="header">
    <div class="logo">🔬 Trustworthy Science</div>
    <div class="title">Literature Review Report</div>
    <div class="meta">Generated: ${now} &nbsp;·&nbsp; AI-powered credibility scoring across 7 dimensions</div>
  </div>

  <div class="section-title">Session Overview</div>
  <div class="stats-grid">
    <div class="stat-box stat-default">
      <div class="stat-value">${graphStats.total_papers ?? addedPapers.length}</div>
      <div class="stat-label">Papers in Graph</div>
    </div>
    <div class="stat-box stat-trusted">
      <div class="stat-value">${graphStats.trusted ?? 0}</div>
      <div class="stat-label">Trusted</div>
    </div>
    <div class="stat-box stat-caution">
      <div class="stat-value">${graphStats.caution ?? 0}</div>
      <div class="stat-label">Caution</div>
    </div>
    <div class="stat-box stat-excluded">
      <div class="stat-value">${excludedPapers.length}</div>
      <div class="stat-label">Excluded (Untrusted)</div>
    </div>
    <div class="stat-box stat-default">
      <div class="stat-value">${graphStats.total_edges ?? 0}</div>
      <div class="stat-label">Connections</div>
    </div>
    <div class="stat-box stat-default">
      <div class="stat-value">${answers.length}</div>
      <div class="stat-label">Research Questions</div>
    </div>
  </div>

  ${addedPapers.length > 0 ? `
  <div class="section-title">Knowledge Graph Papers (${addedPapers.length})</div>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Title</th>
        <th>DOI</th>
        <th>Tier</th>
        <th>Score</th>
      </tr>
    </thead>
    <tbody>
      ${paperRows(addedPapers)}
    </tbody>
  </table>
  ` : ''}

  ${excludedPapers.length > 0 ? `
  <div class="section-title">Excluded Papers (${excludedPapers.length}) — filtered out as Untrusted</div>
  <div>
    ${excludedPapers.map(p => `
      <div class="excluded-row">
        <span>❌</span>
        <a href="https://doi.org/${escapeHtml(p.doi)}" target="_blank" style="color:#dc2626">${escapeHtml(p.title)}</a>
        <span style="margin-left:auto;font-family:monospace;font-size:10px">${p.score}/100</span>
      </div>
    `).join('')}
  </div>
  ` : ''}

  ${answers.length > 0 ? `
  <div class="section-title">Research Findings (${answers.length} question${answers.length !== 1 ? 's' : ''})</div>
  ${qaBlocks(answers)}
  ` : ''}

  <div class="footer">
    <span>Generated by <strong>Trustworthy Science</strong> · AI credibility scoring · 7 agent dimensions</span>
    <span>${now}</span>
  </div>

</body>
</html>`;

  const win = window.open('', '_blank', 'width=900,height=700');
  if (!win) {
    alert('Please allow popups to export the PDF');
    return;
  }
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => { win.print(); win.close(); }, 500);
}
