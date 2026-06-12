const AdverseEventMiner = (function() {
    const API_PREFIX = '/efficacy/adverse-events';

    function init() {
        setupTabSwitching('.risk-tabs', '.risk-content');
        ['#btn-query-herb-risk', '#btn-list-risk-pairs', '#btn-assess-formula-risk', '#btn-load-risk-annotations', '#btn-mine-adverse-text']
            .forEach((sel, i) => {
                document.querySelector(sel).addEventListener('click',
                    [queryHerbRisk, listRiskPairs, assessFormulaRisk, loadRiskAnnotations, mineAdverseFromText][i]);
            });
    }

    function queryHerbRisk() {
        const herb = document.getElementById('risk-herb-name').value.trim();
        if (!herb) return alert('请输入中药名');
        const container = document.getElementById('risk-herb-container');
        container.innerHTML = '<p class="placeholder-text">检索不良反应档案...</p>';
        fetch(`${API_BASE}${API_PREFIX}/herb/${encodeURIComponent(herb)}`)
            .then(r => r.json())
            .then(d => {
                if (!d.toxic_flag) {
                    container.innerHTML = `
                    <div class="result-card" style="padding:20px;background:#e8f5e9">
                        <h3 style="margin:0 0 8px;color:#2e7d32">🌿 ${d.herb_name}</h3>
                        <p style="margin:0;color:#388e3c;font-size:14px">✅ ${d.message}</p>
                    </div>`;
                    return;
                }
                const sevColor = { "轻度": "#ffc107", "中度": "#ff9800", "严重": "#f44336" };
                let arHtml = '';
                (d.adverse_reactions || []).forEach(ar => {
                    arHtml += `<div style="padding:10px;background:#fff;border:1px solid #eee;border-left:4px solid ${sevColor[ar.severity] || '#999'};border-radius:4px;margin-bottom:8px">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <strong style="color:#333">${ar.reaction_type}</strong>
                        <span style="font-size:11px;padding:2px 6px;background:${sevColor[ar.severity] || '#999'};color:#fff;border-radius:3px">${ar.severity}</span>
                    </div>
                    <p style="margin:2px 0;font-size:12px;color:#555">症状：${ar.symptoms.join('、')}</p>
                    <p style="margin:2px 0;font-size:11px;color:#888">
                        发生率${ar.frequency ? (ar.frequency * 100).toFixed(0) + '%' : '未统计'}
                        ${ar.onset_hours ? ' · 发作中位时间 ' + ar.onset_hours + 'h' : ''}
                    </p>
                </div>`;
                });
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:#fff3e0;border-left:5px solid #e65100">
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px">
                        <div><label style="font-size:11px;color:#888">中药</label>
                            <div style="font-size:18px;font-weight:700;color:#bf360c">☠️ ${d.herb_name}</div></div>
                        <div><label style="font-size:11px;color:#888">LD50 (mg/kg)</label>
                            <div style="font-size:18px;font-weight:700;color:#c62828">${d.ld50_mgkg || '-'}</div></div>
                        <div><label style="font-size:11px;color:#888">最大安全剂量</label>
                            <div style="font-size:18px;font-weight:700;color:#ef6c00">≤${d.max_safe_dose_g || '-'}g</div></div>
                        <div><label style="font-size:11px;color:#888">妊娠风险</label>
                            <div style="font-size:18px;font-weight:700;color:#ad1457">${d.pregnancy_risk || '-'}</div></div>
                    </div>
                    <p style="margin:8px 0;font-size:13px"><strong>⚠️ 禁忌证：</strong>${d.contraindications.join('；') || '未记录'}</p>
                    <p style="margin:8px 0;font-size:13px"><strong>🧪 毒性成分：</strong>${d.toxic_ingredients.join('、') || '未记录'}</p>
                </div>
                <h4 style="margin:8px 0">已报道不良反应</h4>
                ${arHtml || '<p class="placeholder-text">无具体不良反应记录</p>'}
            `;
            });
    }

    function listRiskPairs() {
        const level = document.getElementById('risk-pair-level').value;
        const container = document.getElementById('risk-pairs-container');
        container.innerHTML = '<p class="placeholder-text">加载风险药对总览...</p>';
        fetch(`${API_BASE}${API_PREFIX}/risk-pairs?risk_level=${encodeURIComponent(level)}&limit=500`)
            .then(r => r.json())
            .then(d => {
                const lvlColor = { "极高": "#b71c1c", "高": "#e53935", "中": "#fb8c00", "低": "#fdd835" };
                const lvlBg = { "极高": "#ffebee", "高": "#ffebee", "中": "#fff8e1", "低": "#fffde7" };
                let html = `<div style="margin-bottom:12px;padding:10px;background:#fafafa;border-radius:6px;font-size:13px">
                    总计 <strong>${d.total}</strong> 对风险配伍 · 交互类型：${(d.interaction_types || []).join('、')}
                </div><table class="data-table"><thead><tr>
                    <th>药物A</th><th>药物B</th><th>等级</th><th>风险分</th>
                    <th>交互类型</th><th>机制</th><th>证据</th></tr></thead><tbody>`;
                (d.pairs || []).forEach(p => {
                    html += `<tr style="background:${lvlBg[p.risk_level] || '#fff'}">
                    <td style="font-weight:600;color:#4a148c">${p.herb_a}</td>
                    <td style="font-weight:600;color:#4a148c">${p.herb_b}</td>
                    <td><span style="padding:2px 6px;background:${lvlColor[p.risk_level] || '#999'};color:#fff;border-radius:3px;font-size:11px;font-weight:600">${p.risk_level}</span></td>
                    <td style="font-weight:700;color:${lvlColor[p.risk_level] || '#333'}">${p.risk_score}</td>
                    <td><strong>${p.interaction_type}</strong></td>
                    <td style="font-size:12px;color:#555;max-width:260px">${p.mechanism}</td>
                    <td style="font-size:11px;color:#1976d2">${(p.references || []).join('；')}</td>
                </tr>`;
                });
                html += '</tbody></table>';
                container.innerHTML = html;
            });
    }

    function assessFormulaRisk() {
        const fname = document.getElementById('risk-formula-name').value.trim() || '自定义方剂';
        const herbsRaw = document.getElementById('risk-formula-herbs').value.trim();
        if (!herbsRaw) return alert('请输入药物列表（逗号分隔）');
        const herbs = herbsRaw.split(/[,，、\s]+/).filter(x => x);
        const container = document.getElementById('risk-formula-container');
        container.innerHTML = '<p class="placeholder-text">综合评估方剂风险...</p>';
        fetch(`${API_BASE}${API_PREFIX}/assess-formula`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ formula_name: fname, herbs })
        })
            .then(r => r.json())
            .then(d => {
                const rlColor = { "安全": "#4caf50", "低": "#8bc34a", "中": "#ff9800", "高": "#f44336", "极高": "#b71c1c" };
                const rlBg = { "安全": "#e8f5e9", "低": "#e8f5e9", "中": "#fff3e0", "高": "#ffebee", "极高": "#ffebee" };
                const lvlColor = { "极高": "#b71c1c", "高": "#e53935", "中": "#fb8c00", "低": "#fdd835" };
                let pairsHtml = '';
                (d.risk_pairs || []).forEach(p => {
                    pairsHtml += `<div style="padding:10px;background:#fff;border:1px solid #eee;border-left:4px solid ${lvlColor[p.risk_level] || '#999'};border-radius:4px;margin-bottom:6px">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                        <strong style="color:#333">💥 ${p.herb_a} + ${p.herb_b}
                            <span style="font-size:11px;padding:2px 6px;background:${lvlColor[p.risk_level] || '#999'};color:#fff;border-radius:3px;margin-left:6px">${p.risk_level} · ${p.risk_score}</span>
                        </strong>
                        <span style="font-size:11px;background:#1976d2;color:#fff;padding:2px 6px;border-radius:3px">${p.interaction_type}</span>
                    </div>
                    <p style="margin:4px 0 2px;font-size:12px;color:#555">机制：${p.mechanism}</p>
                    <p style="margin:0;font-size:11px;color:#888">证据级别：${p.evidence_level} · ${(p.references || []).join('；')}</p>
                </div>`;
                });
                let indivHtml = '';
                for (const [h, info] of Object.entries(d.individual_risks || {})) {
                    indivHtml += `<div style="padding:8px;background:#fff;border:1px solid #eee;border-radius:4px;margin-bottom:6px">
                    <div style="font-weight:600;color:#4a148c">☠️ ${h}</div>
                    <div style="font-size:11px;color:#666;margin-top:2px">
                        毒性：${(info.toxic_ingredients || []).join('、') || '无'} ·
                        LD₅₀：${info.ld50_mgkg || '-'}mg/kg ·
                        上限：${info.max_safe_dose_g || '-'}g ·
                        妊娠：${info.pregnancy_risk || '无标注'}
                    </div>
                </div>`;
                }
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:${rlBg[d.overall_risk_level]};border-left:5px solid ${rlColor[d.overall_risk_level]}">
                    <div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;align-items:center">
                        <div>
                            <h3 style="margin:0 0 8px;color:#333">${d.formula_name}</h3>
                            <div style="display:flex;align-items:center;gap:12px">
                                <div style="width:110px;height:110px;border-radius:50%;background:conic-gradient(${rlColor[d.overall_risk_level]} 0% ${d.overall_risk_score}%, #e0e0e0 ${d.overall_risk_score}% 100%);display:flex;align-items:center;justify-content:center">
                                    <div style="width:90px;height:90px;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center">
                                        <span style="font-size:24px;font-weight:700;color:${rlColor[d.overall_risk_level]}">${d.overall_risk_score}</span>
                                        <span style="font-size:10px;color:#888">风险分</span>
                                    </div>
                                </div>
                                <div>
                                    <div style="font-size:24px;font-weight:700;color:${rlColor[d.overall_risk_level]}">${d.overall_risk_level}</div>
                                    <div style="font-size:12px;color:#666;margin-top:4px">风险药对：${(d.risk_pairs || []).length} 对</div>
                                    <div style="font-size:12px;color:#666">含毒性中药：${Object.keys(d.individual_risks || {}).length} 味</div>
                                </div>
                            </div>
                        </div>
                        <div>
                            ${d.warnings && d.warnings.length ? `<div style="margin-bottom:8px">
                                <h5 style="margin:0 0 6px;color:#b71c1c">⚠️ 风险警示</h5>
                                <ul style="margin:0;padding-left:18px;font-size:12px;color:#c62828">${d.warnings.map(w => `<li>${w}</li>`).join('')}</ul>
                            </div>` : ''}
                            ${d.safe_use_guidance && d.safe_use_guidance.length ? `<div>
                                <h5 style="margin:0 0 6px;color:#2e7d32">📋 安全用药指导</h5>
                                <ul style="margin:0;padding-left:18px;font-size:12px;color:#2e7d32">${d.safe_use_guidance.map(w => `<li>${w}</li>`).join('')}</ul>
                            </div>` : ''}
                        </div>
                    </div>
                </div>
                ${pairsHtml ? `<h4 style="margin:16px 0 8px">💥 风险药对（${(d.risk_pairs || []).length}对）</h4>${pairsHtml}` : ''}
                ${indivHtml ? `<h4 style="margin:16px 0 8px">☠️ 单药毒性档案</h4>${indivHtml}` : ''}
            `;
            });
    }

    function loadRiskAnnotations() {
        const min = document.getElementById('risk-annot-min').value;
        const container = document.getElementById('risk-annotations-container');
        container.innerHTML = '<p class="placeholder-text">加载网络风险标注...</p>';
        fetch(`${API_BASE}${API_PREFIX}/network-annotations?min_risk_level=${encodeURIComponent(min)}&limit=500`)
            .then(r => r.json())
            .then(d => {
                const lvlColor = d.color_map || {};
                let html = `<div style="margin-bottom:12px;padding:10px;background:#fafafa;border-radius:6px;font-size:13px">
                    阈值 <strong>${d.query_threshold}</strong> · 总计风险边 <strong>${d.total_risk_edges}</strong>
                </div><table class="data-table"><thead><tr>
                    <th style="width:60px">绘制</th><th>药物A</th><th>药物B</th>
                    <th>交互类型</th><th>等级</th><th>得分</th></tr></thead><tbody>`;
                (d.risk_edges || []).forEach(e => {
                    html += `<tr>
                    <td><div style="width:30px;height:6px;background:${e.stroke || '#ff9800'};border-radius:3px"></div></td>
                    <td style="font-weight:600">${e.source}</td>
                    <td style="font-weight:600">${e.target}</td>
                    <td>${e.label}</td>
                    <td>${e.risk_level}</td>
                    <td style="font-weight:700;color:#d32f2f">${e.risk_score}</td>
                </tr>`;
                });
                html += '</tbody></table>';
                html += `<p style="margin-top:12px;font-size:12px;color:#666">
                💡 可在"关联网络图"视图中叠加显示以上风险边（虚线+红色系标注）。
                <button class="btn btn-xs" style="margin-left:8px" onclick="applyRiskEdgesToGraph()">
                    传送到网络图
                </button>
            </p>`;
                window.riskEdges = d.risk_edges;
                container.innerHTML = html;
            });
    }

    function mineAdverseFromText() {
        const text = document.getElementById('risk-text-input').value.trim();
        if (!text) return alert('请输入医案文本');
        const herbsRaw = document.getElementById('risk-text-herbs').value.trim();
        const herbs = herbsRaw ? herbsRaw.split(/[,，、\s]+/).filter(x => x) : null;
        const container = document.getElementById('risk-textmine-container');
        container.innerHTML = '<p class="placeholder-text">正在挖掘不良反应信息...</p>';
        const body = { text };
        if (herbs) body.herbs_context = herbs;
        fetch(`${API_BASE}/text-mining/adverse/extract`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
            .then(r => r.json())
            .then(d => {
                const sevColor = { "轻度": "#ffc107", "中度": "#ff9800", "严重": "#f44336" };
                let reactionsHtml = '';
                (d.extracted_reactions || []).forEach(r => {
                    reactionsHtml += `<div style="padding:10px;background:#fff;border:1px solid #eee;border-left:4px solid ${sevColor[r.severity] || '#999'};border-radius:4px;margin-bottom:8px">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                        <strong style="color:#333">${r.reaction_type}</strong>
                        <div>
                            <span style="font-size:11px;padding:2px 6px;background:${sevColor[r.severity] || '#999'};color:#fff;border-radius:3px">${r.severity}</span>
                            <span style="font-size:11px;color:#888;margin-left:6px">匹配词: "${r.matched_term}"</span>
                        </div>
                    </div>
                </div>`;
                });

                const noReactions = !d.extracted_reactions || d.extracted_reactions.length === 0;
                const count = (d.extracted_reactions || []).length;
                const summary = count === 0 ? "未从文本中检出明确的不良反应描述。" :
                    `从文本中检出 ${count} 项不良反应${herbs ? `，结合${herbs.length}味上下文药物` : ''}。`;
                const sevDist = {};
                (d.extracted_reactions || []).forEach(r => {
                    sevDist[r.severity] = (sevDist[r.severity] || 0) + 1;
                });
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:${noReactions ? '#e8f5e9' : '#fff3e0'};border-left:5px solid ${noReactions ? '#4caf50' : '#e65100'}">
                    <div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;align-items:center">
                        <div>
                            <h3 style="margin:0 0 8px;color:#333">📄 医案文本挖掘</h3>
                            <div style="font-size:36px;font-weight:700;color:${noReactions ? '#4caf50' : '#e65100'}">${count}</div>
                            <div style="font-size:12px;color:#888">检出不良反应项</div>
                        </div>
                        <div>
                            <div style="padding:8px;background:#fff;border-radius:4px;font-size:13px;color:#555">
                                <strong>📌 风险摘要：</strong>${summary}
                            </div>
                            <div style="margin-top:8px;display:flex;gap:8px;font-size:12px">
                                ${Object.entries(sevDist).map(([k, v]) =>
                                    `<span style="padding:2px 8px;background:${sevColor[k] || '#eee'};color:#fff;border-radius:3px;font-weight:600">${k}: ${v}</span>`
                                ).join('')}
                            </div>
                        </div>
                    </div>
                </div>
                ${reactionsHtml ? `<h4 style="margin:12px 0 8px">🔍 提取的不良反应</h4>${reactionsHtml}` : ''}
            `;
            })
            .catch(err => container.innerHTML = `<p class="placeholder-text" style="color:#e74c3c">${err.message}</p>`);
    }

    return { init };
})();
