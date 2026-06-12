const ClinicalTrialIntegrator = (function() {
    const API_PREFIX = '/efficacy/clinical';

    function init() {
        setupTabSwitching('.clinical-tabs', '.clinical-content');
        ['#btn-load-clinical-trials', '#btn-run-meta', '#btn-run-nma', '#btn-load-clinical-summary']
            .forEach((sel, i) => {
                document.querySelector(sel).addEventListener('click',
                    [loadClinicalTrials, runMetaAnalysis, runNetworkMeta, loadClinicalSummary][i]);
            });
    }

    function loadClinicalTrials() {
        const ind = document.getElementById('clinical-indication').value;
        const n = document.getElementById('clinical-trials-n').value;
        const container = document.getElementById('clinical-trials-container');
        container.innerHTML = '<p class="placeholder-text">检索临床试验数据库...</p>';
        fetch(`${API_BASE}${API_PREFIX}/trials?indication=${encodeURIComponent(ind)}&num_trials=${n}`)
            .then(r => r.json())
            .then(d => {
                let html = `<div class="result-card" style="padding:12px;margin-bottom:12px;background:#e3f2fd">
                    <strong>适应症：</strong>${d.indication} ·
                    <strong>现代方案：</strong>${(d.modern_treatments_available || []).join('、')} ·
                    <strong>经典方：</strong>${(d.classical_formulas_available || []).join('、')}
                </div><table class="data-table"><thead><tr>
                    <th>试验ID</th><th>年份</th><th>标题</th><th>设计</th>
                    <th>治疗组</th><th>对照组</th><th>例数</th><th>疗程</th><th>质量</th></tr></thead><tbody>`;
                (d.trials || []).forEach(t => {
                    const a1 = t.arms[0], a2 = t.arms[1];
                    const qColor = t.quality_score > 0.75 ? '#4caf50' : t.quality_score > 0.6 ? '#ffc107' : '#f44336';
                    html += `<tr>
                    <td style="font-size:11px;color:#1976d2;font-family:monospace">${t.trial_id}</td>
                    <td>${t.year}</td>
                    <td style="font-size:12px;max-width:220px">${t.title}</td>
                    <td style="font-size:11px">${t.design}</td>
                    <td style="font-size:12px">
                        <div><strong>${a1.treatment_name}</strong> <span style="color:#888">(${a1.treatment_type})</span></div>
                        <div style="color:#2e7d32;font-size:11px">疗效 ${(a1.mean_efficacy * 100).toFixed(0)}% · AE ${(a1.adverse_event_rate * 100).toFixed(0)}%</div>
                    </td>
                    <td style="font-size:12px">
                        <div><strong>${a2 ? a2.treatment_name : '-'}</strong> <span style="color:#888">(${a2 ? a2.treatment_type : '-'})</span></div>
                        <div style="color:#e65100;font-size:11px">疗效 ${a2 ? (a2.mean_efficacy * 100).toFixed(0) : '-'}% · AE ${a2 ? (a2.adverse_event_rate * 100).toFixed(0) : '-'}%</div>
                    </td>
                    <td>${t.total_sample_size}</td>
                    <td>${t.duration_weeks}周</td>
                    <td><div style="display:flex;align-items:center;gap:4px">
                        <div style="width:50px;height:6px;background:#eee;border-radius:3px;overflow:hidden">
                            <div style="width:${t.quality_score * 100}%;height:100%;background:${qColor}"></div></div>
                        <span style="font-size:11px">${t.quality_score.toFixed(2)}</span></div>
                    </td>
                </tr>`;
                });
                html += '</tbody></table>';
                container.innerHTML = html;
            });
    }

    function runMetaAnalysis() {
        const ind = document.getElementById('meta-indication').value;
        const container = document.getElementById('clinical-meta-container');
        container.innerHTML = '<p class="placeholder-text">执行逆方差随机效应Meta分析（经典方 vs 现代方案）...</p>';
        fetch(`${API_BASE}${API_PREFIX}/meta-analysis?indication=${encodeURIComponent(ind)}`)
            .then(r => r.json())
            .then(d => {
                const pct = d.i_squared || 0;
                const hetColor = pct < 50 ? '#4caf50' : pct < 75 ? '#ff9800' : '#f44336';
                let rows = '';
                (d.forest_plot_data || []).forEach((fp, i) => {
                    const [lo, hi] = fp.ci;
                    const mid = (lo + hi) / 2;
                    const scale = Math.max(0.01, Math.abs(hi - lo) + 0.5);
                    const barLeft = Math.max(0, 50 + (lo - 0) / scale * 100);
                    const barMid = 50 + (mid - 0) / scale * 100;
                    const barRight = Math.min(100, 50 + (hi - 0) / scale * 100);
                    const isPooled = i === d.forest_plot_data.length - 1;
                    rows += `<div style="display:grid;grid-template-columns:120px 60px 1fr 70px;gap:6px;align-items:center;padding:4px 0;border-bottom:1px dashed #eee;font-size:12px">
                    <div style="font-size:11px">${fp.study}</div>
                    <div style="font-size:11px">${fp.year || ''}</div>
                    <div style="position:relative;height:22px;background:${isPooled ? '#fafafa' : 'transparent'}">
                        <div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#bbb"></div>
                        ${isPooled ? `<div style="position:absolute;left:${barLeft}%;top:4px;right:${100 - barRight}%;height:14px;background:rgba(33,150,243,0.5);border-radius:2px"></div>`
                            : `<div style="position:absolute;left:${barLeft}%;top:8px;right:${100 - barRight}%;height:2px;background:#666"></div>
                               <div style="position:absolute;left:${barMid}%;top:2px;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:${isPooled ? '10px solid #1976d2' : '8px solid #333'};transform:translateX(-50%) rotate(180deg)"></div>`}
                    </div>
                    <div style="font-size:11px;font-family:monospace">${fp.effect_size.toFixed(2)}<br><span style="color:#888">${fp.weight ? fp.weight.toFixed(1) + '%' : ''}</span></div>
                </div>`;
                });
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:#e3f2fd">
                    <h3 style="margin:0 0 10px;color:#1565c0">${d.indication}：${d.comparison}</h3>
                    <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:12px">
                        <div><label style="font-size:11px;color:#888">合并SMD</label>
                            <div style="font-size:20px;font-weight:700;color:${d.p_value < 0.05 ? '#2e7d32' : '#757575'}">${d.pooled_effect_size.toFixed(3)}</div></div>
                        <div><label style="font-size:11px;color:#888">95% CI</label>
                            <div style="font-size:17px;font-weight:700;color:#1976d2">[${d.ci_95[0].toFixed(3)},<br>${d.ci_95[1].toFixed(3)}]</div></div>
                        <div><label style="font-size:11px;color:#888">P值</label>
                            <div style="font-size:20px;font-weight:700;color:${d.p_value < 0.05 ? '#2e7d32' : '#757575'}">${d.p_value < 0.001 ? '<0.001' : d.p_value.toFixed(4)}</div></div>
                        <div><label style="font-size:11px;color:#888">异质性I²</label>
                            <div style="font-size:20px;font-weight:700;color:${hetColor}">${pct.toFixed(1)}%</div></div>
                        <div><label style="font-size:11px;color:#888">纳入研究</label>
                            <div style="font-size:20px;font-weight:700;color:#555">${d.trials_included}</div></div>
                        <div><label style="font-size:11px;color:#888">总患者</label>
                            <div style="font-size:20px;font-weight:700;color:#555">${d.total_patients}</div></div>
                    </div>
                    <div style="padding:10px;background:#fff;border-radius:6px;border-left:4px solid ${d.p_value < 0.05 ? '#2e7d32' : '#78909c'}">
                        <strong>📌 结论：</strong>${d.conclusion}
                    </div>
                </div>
                <h5 style="margin:0 0 6px;color:#455a64">森林图（Forest Plot）</h5>
                <div style="padding:8px;background:#fff;border:1px solid #ddd;border-radius:6px">
                    <div style="display:grid;grid-template-columns:120px 60px 1fr 70px;gap:6px;font-size:11px;color:#888;padding-bottom:4px;border-bottom:2px solid #eee;margin-bottom:4px">
                        <div>研究</div><div>年份</div><div style="text-align:center">效应量 (95% CI)</div><div>SMD</div>
                    </div>
                    ${rows}
                </div>
            `;
            });
    }

    function runNetworkMeta() {
        const ind = document.getElementById('nma-indication').value;
        const container = document.getElementById('clinical-nma-container');
        container.innerHTML = '<p class="placeholder-text">运行贝叶斯网络Meta分析...</p>';
        fetch(`${API_BASE}${API_PREFIX}/network-meta?indication=${encodeURIComponent(ind)}`)
            .then(r => r.json())
            .then(d => {
                let rankHtml = '<ol style="margin:0;padding-left:24px">';
                (d.treatments_ranked || []).forEach((t, i) => {
                    rankHtml += `<li style="margin:6px 0;padding:8px 10px;background:#fff;border:1px solid #eee;border-radius:4px">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div>
                            <strong style="font-size:14px">${t.treatment}</strong>
                            <span style="font-size:11px;color:#888;margin-left:6px">纳入 ${t.studies} 项研究</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:10px">
                            <div style="width:80px;height:8px;background:#eee;border-radius:4px;overflow:hidden">
                                <div style="width:${t.net_score * 100}%;height:100%;background:linear-gradient(90deg,#64b5f6,#1565c0)"></div>
                            </div>
                            <span style="font-weight:700;color:#1976d2">${t.best_prob}%</span>
                        </div>
                    </div></li>`;
                });
                rankHtml += '</ol>';
                let netViz = '';
                if (d.network_edges && d.network_edges.length) {
                    const trts = (d.treatments_ranked || []).map(t => t.treatment);
                    const ang = i => 2 * Math.PI * i / Math.max(1, trts.length) - Math.PI / 2;
                    netViz = `<svg viewBox="0 0 400 400" width="100%" style="background:#fff;border:1px solid #eee;border-radius:8px">`;
                    trts.forEach((t, i) => {
                        const x = 200 + Math.cos(ang(i)) * 150;
                        const y = 200 + Math.sin(ang(i)) * 150;
                        const prob = (d.best_treatment_probability || {})[t] || 0;
                        const r = 10 + prob / 10;
                        netViz += `<circle cx="${x}" cy="${y}" r="${r}" fill="#4fc3f7" stroke="#0288d1" stroke-width="2"/>`;
                        netViz += `<text x="${x}" y="${y + 4}" text-anchor="middle" font-size="11" fill="#fff" font-weight="700">${i + 1}</text>`;
                        netViz += `<text x="${x}" y="${y + (y > 200 ? r + 16 : -r - 6)}" text-anchor="middle" font-size="11" fill="#333">${t.substring(0, 8)}</text>`;
                    });
                    (d.network_edges || []).forEach(e => {
                        const i1 = trts.indexOf(e.from);
                        const i2 = trts.indexOf(e.to);
                        if (i1 < 0 || i2 < 0) return;
                        const x1 = 200 + Math.cos(ang(i1)) * 150;
                        const y1 = 200 + Math.sin(ang(i1)) * 150;
                        const x2 = 200 + Math.cos(ang(i2)) * 150;
                        const y2 = 200 + Math.sin(ang(i2)) * 150;
                        const w = Math.min(5, 1 + e.trials / 2);
                        netViz += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#90a4ae" stroke-width="${w}" opacity="0.6"/>`;
                    });
                    netViz += '</svg>';
                }
                let league = '';
                if (d.league_table && d.league_table.length) {
                    league = '<table class="data-table" style="font-size:12px"><tbody>';
                    d.league_table.forEach((row, ri) => {
                        league += '<tr>';
                        row.forEach(cell => {
                            const isNum = typeof cell === 'number';
                            let bg = '';
                            if (isNum && ri > 0) {
                                if (cell > 0.1) bg = 'background:#e8f5e9;color:#2e7d32';
                                else if (cell < -0.1) bg = 'background:#ffebee;color:#c62828';
                            }
                            league += `<td style="${bg};font-weight:${ri === 0 ? 700 : 400}">${isNum ? cell.toFixed(2) : cell}</td>`;
                        });
                        league += '</tr>';
                    });
                    league += '</tbody></table>';
                }
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:#f3e5f5">
                    <h3 style="margin:0 0 10px;color:#6a1b9a">🏆 网络Meta：${d.indication}</h3>
                    <p style="margin:0 0 8px;font-size:13px;color:#555">
                        共纳入 <strong>${(d.network_edges || []).reduce((s, e) => s + (e.trials || 0), 0)}</strong> 项头对头研究
                        ${d.inconsistency ? ` · 不一致性因子 IF = <strong>${d.inconsistency}</strong>` : ''}
                    </p>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
                    <div>
                        <h5 style="margin:0 0 8px">🥇 疗效排序（SUCRA/best概率）</h5>
                        ${rankHtml}
                    </div>
                    <div>
                        <h5 style="margin:0 0 8px">🕸 证据网络</h5>
                        ${netViz || '<p class="placeholder-text">无足够比较组</p>'}
                    </div>
                </div>
                <h5 style="margin:8px 0">📊 联赛表（每格=行治疗对比列治疗的效应差）</h5>
                ${league || '<p class="placeholder-text">无联赛表数据</p>'}
            `;
            });
    }

    function loadClinicalSummary() {
        const ind = document.getElementById('summary-indication').value;
        const container = document.getElementById('clinical-summary-container');
        container.innerHTML = '<p class="placeholder-text">汇总多维度证据...</p>';
        fetch(`${API_BASE}/efficacy/summary/indication/${encodeURIComponent(ind)}`)
            .then(r => r.json())
            .then(d => {
                const ts = d.trials_summary || {};
                const meta = d.meta_analysis || {};
                const pct = meta.i_squared || 0;
                let formulaRows = '';
                (d.top_formulas_by_value || []).forEach(f => {
                    const rlColor = { "安全": "#4caf50", "低": "#8bc34a", "中": "#ff9800", "高": "#f44336", "极高": "#b71c1c" };
                    const value = f.avg_efficacy_score - f.risk_score / 5;
                    formulaRows += `<tr>
                    <td style="font-weight:600">${f.name}</td>
                    <td>${f.dynasty || '-'}</td>
                    <td style="font-weight:700;color:#2e7d32">${f.avg_efficacy_score.toFixed(1)}</td>
                    <td>${f.avg_days_to_effect.toFixed(1)}天</td>
                    <td><span style="padding:2px 6px;background:${rlColor[f.risk_level] || '#eee'};color:#fff;border-radius:3px;font-size:11px;font-weight:600">${f.risk_level}</span> ${f.risk_score.toFixed(0)}</td>
                    <td style="font-weight:700;color:#1976d2">${value.toFixed(1)}</td>
                </tr>`;
                });
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:#e8f5e9">
                    <h3 style="margin:0 0 10px;color:#2e7d32">📋 ${d.indication} · 综合证据汇总</h3>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:10px">
                        <div><label style="font-size:11px;color:#888">临床试验数</label>
                            <div style="font-size:20px;font-weight:700">${ts.total || '-'}</div></div>
                        <div><label style="font-size:11px;color:#888">总受试者</label>
                            <div style="font-size:20px;font-weight:700">${ts.total_patients || '-'}</div></div>
                        <div><label style="font-size:11px;color:#888">Meta合并SMD</label>
                            <div style="font-size:20px;font-weight:700;color:${(meta.p_value || 1) < 0.05 ? '#2e7d32' : '#757575'}">${meta.pooled_effect_size ? meta.pooled_effect_size.toFixed(3) : '-'}</div></div>
                        <div><label style="font-size:11px;color:#888">异质性I²</label>
                            <div style="font-size:20px;font-weight:700;color:${pct < 50 ? '#2e7d32' : pct < 75 ? '#ff9800' : '#f44336'}">${pct ? pct.toFixed(1) + '%' : '-'}</div></div>
                    </div>
                    <div style="padding:8px;background:#fff;border-radius:4px;font-size:13px">
                        <strong>📌 Meta结论：</strong>${meta.conclusion || '无数据'}
                    </div>
                </div>
                <h4 style="margin:16px 0 8px">🏆 价值最高方剂（疗效-风险 平衡排序）</h4>
                <table class="data-table"><thead><tr>
                    <th>方剂</th><th>朝代</th><th>疗效分</th><th>平均见效</th><th>风险</th><th>净价值分</th></tr></thead>
                    <tbody>${formulaRows || '<tr><td colspan="6" style="text-align:center;color:#888">暂无数据</td></tr>'}</tbody>
                </table>
            `;
            });
    }

    return { init };
})();