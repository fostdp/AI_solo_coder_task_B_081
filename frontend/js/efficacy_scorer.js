const EfficacyScorer = (function() {
    const API_PREFIX = '/efficacy/scorer';

    function init() {
        setupTabSwitching('.efficacy-tabs', '.efficacy-content');
        ['#btn-load-efficacy-rank', '#btn-analyze-formula-efficacy', '#btn-analyze-efficacy-text']
            .forEach((sel, idx) => {
                const el = document.querySelector(sel);
                if (el) el.addEventListener('click', [loadEfficacyRanked, analyzeFormulaEfficacy, analyzeEfficacyText][idx]);
            });
    }

    function loadEfficacyRanked() {
        const dynasty = document.getElementById('efficacy-dynasty').value;
        const mincases = document.getElementById('efficacy-mincases').value;
        const limit = document.getElementById('efficacy-limit').value;
        const container = document.getElementById('efficacy-ranked-container');
        container.innerHTML = '<p class="placeholder-text">正在计算疗效数据...</p>';
        fetch(`${API_BASE}${API_PREFIX}/formulas/ranked?dynasty=${encodeURIComponent(dynasty)}&min_total_cases=${mincases}&limit=${limit}&skip=0`)
            .then(r => r.json())
            .then(data => {
                if (!data.formulas || data.formulas.length === 0) {
                    container.innerHTML = '<p class="placeholder-text">未找到数据</p>';
                    return;
                }
                let html = `<div class="mining-controls" style="background:#f8fff7;border:1px solid #c8e6c9;">
                <span style="font-size:13px;color:#2e7d32">
                    共 <strong>${data.total}</strong> 个方剂 · 按平均疗效分降序 · 置信区间95%
                </span></div><table class="data-table"><thead><tr>
                    <th>排名</th><th>方剂名</th><th>朝代</th><th>主治</th>
                    <th>疗效评分</th><th>等级分布</th><th>医案数</th>
                    <th>平均见效天数</th><th>操作</th></tr></thead><tbody>`;
                data.formulas.forEach((f, i) => {
                    const rankColor = i === 0 ? '#f39c12' : i < 3 ? '#e67e22' : i < 10 ? '#27ae60' : '#607d8b';
                    const gd = f.efficacy_grade_distribution || {};
                    const gradeHtml = [0, 1, 2, 3, 4].map(g =>
                        `<span style="display:inline-block;font-size:11px;padding:1px 4px;border-radius:3px;background:${
                            ['#bdbdbd','#ffc107','#8bc34a','#4caf50','#2e7d32'][g] || '#eee'
                        };color:#fff;margin:0 1px">${gd[g] || 0}</span>`
                    ).join('');
                    html += `<tr>
                    <td style="color:${rankColor};font-weight:700">#${i + 1}</td>
                    <td><a onclick="viewFormulaDetail('${f.name.replace(/'/g, "\\'")}')"
                         style="color:#2c5530;cursor:pointer;font-weight:600">${f.name}</a></td>
                    <td>${f.dynasty || '-'}</td>
                    <td>${(f.indications || []).join('、') || '-'}</td>
                    <td>
                        <div style="display:flex;align-items:center;gap:6px">
                            <strong style="color:#2e7d32;font-size:14px">${f.avg_efficacy_score.toFixed(1)}</strong>
                            <span style="font-size:11px;color:#999">
                                [${(f.confidence_interval || [0, 0]).map(x => x.toFixed(1)).join(',')}]
                            </span>
                        </div>
                        <div style="width:90px;height:6px;background:#eee;border-radius:3px;margin-top:3px;overflow:hidden">
                            <div style="width:${f.avg_efficacy_score}%;height:100%;background:linear-gradient(90deg,#81c784,#2e7d32)"></div>
                        </div>
                    </td>
                    <td>${gradeHtml}</td>
                    <td>${f.total_cases}</td>
                    <td>${f.avg_days_to_effect.toFixed(1)}天</td>
                    <td><button class="btn btn-xs" onclick="viewFormulaDetail('${f.name.replace(/'/g, "\\'")}')">详情</button></td>
                </tr>`;
                });
                html += '</tbody></table>';
                container.innerHTML = html;
            })
            .catch(err => {
                container.innerHTML = `<p class="placeholder-text" style="color:#e74c3c">加载失败：${err.message}</p>`;
            });
    }

    function analyzeFormulaEfficacy() {
        const name = document.getElementById('efficacy-formula-name').value.trim();
        const n = document.getElementById('efficacy-num-cases').value;
        if (!name) return alert('请输入方剂名称');
        const container = document.getElementById('efficacy-single-container');
        container.innerHTML = '<p class="placeholder-text">正在分析疗效数据...</p>';
        fetch(`${API_BASE}${API_PREFIX}/formula/${encodeURIComponent(name)}?num_cases=${n}`)
            .then(r => { if (!r.ok) throw new Error('方剂未找到'); return r.json(); })
            .then(data => {
                const gd = data.efficacy_grade_distribution || {};
                const total = Object.values(gd).reduce((a, b) => a + b, 0);
                let chartHtml = '<div style="display:flex;gap:6px;align-items:flex-end;height:140px;margin:16px 0;padding:16px;background:#fafafa;border-radius:8px">';
                ['无效', '一般', '良好', '优秀', '神效'].forEach((label, i) => {
                    const val = gd[i] || 0;
                    const h = total ? (val / total * 100) : 0;
                    chartHtml += `<div style="flex:1;display:flex;flex-direction:column;align-items:center">
                    <div style="font-size:12px;color:#555;margin-bottom:4px">${val}</div>
                    <div style="width:80%;height:${h}%;background:${['#bdbdbd','#ffc107','#8bc34a','#4caf50','#2e7d32'][i]};border-radius:4px 4px 0 0"></div>
                    <div style="font-size:12px;margin-top:6px;color:#444">${label}</div>
                </div>`;
                });
                chartHtml += '</div>';
                let casesHtml = '<div style="max-height:260px;overflow-y:auto"><table class="data-table"><thead><tr>' +
                    '<th>医案</th><th>描述</th><th>情感分</th><th>等级</th><th>天数</th></tr></thead><tbody>';
                (data.case_records || []).forEach(c => {
                    casesHtml += `<tr>
                    <td style="font-size:11px;max-width:180px;color:#555">${c.medical_case.substring(0, 30)}...</td>
                    <td style="color:#2c5530">${c.raw_description}</td>
                    <td>${c.sentiment_score.toFixed(2)}</td>
                    <td>${c.efficacy_grade}</td>
                    <td>${c.days_to_effect}天</td></tr>`;
                });
                casesHtml += '</tbody></table></div>';
                container.innerHTML = `
                <div style="display:grid;grid-template-columns:1fr 2fr;gap:20px;margin-bottom:16px">
                    <div class="result-card" style="padding:20px;background:linear-gradient(135deg,#e8f5e9,#c8e6c9)">
                        <h3 style="margin:0 0 10px;color:#2e7d32">${data.formula_name}</h3>
                        <div style="font-size:48px;font-weight:700;color:#2c5530;margin:12px 0">
                            ${data.avg_efficacy_score.toFixed(1)}
                            <span style="font-size:16px;color:#666">/100</span>
                        </div>
                        <div style="font-size:13px;color:#555">
                            <p>👥 医案总数：<strong>${data.total_cases}</strong> 例</p>
                            <p>⏱ 平均见效：<strong>${data.avg_days_to_effect.toFixed(1)}</strong> 天</p>
                            <p>📊 95% CI: <strong>[${(data.confidence_interval || [0,0]).map(x=>x.toFixed(1)).join(', ')}]</strong></p>
                        </div>
                    </div>
                    <div>
                        <h4 style="margin:0 0 10px">疗效等级分布</h4>
                        ${chartHtml}
                    </div>
                </div>
                <h4 style="margin:16px 0 8px">医案记录明细</h4>
                ${casesHtml}
            `;
            })
            .catch(err => {
                container.innerHTML = `<p class="placeholder-text" style="color:#e74c3c">${err.message}</p>`;
            });
    }

    function analyzeEfficacyText() {
        const text = document.getElementById('efficacy-text-input').value.trim();
        if (!text) return alert('请输入医案文本');
        const container = document.getElementById('efficacy-text-result');
        container.innerHTML = '<p class="placeholder-text">分析中...</p>';
        fetch(`${API_BASE}/text-mining/efficacy/analyze`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        })
            .then(r => r.json())
            .then(d => {
                const colors = ['#9e9e9e', '#ffc107', '#8bc34a', '#4caf50', '#2e7d32'];
                const grade = Math.min(4, Math.max(0, Math.floor((d.sentiment_score + 1) / 2 * 5)));
                const gradeLabels = ['无效', '一般', '良好', '优秀', '神效'];
                const score0_100 = Math.max(0, Math.min(100, (d.sentiment_score + 1) / 2 * 100));
                container.innerHTML = `
                <div class="result-card" style="padding:20px;margin-top:10px;background:#f5f5f5;border-left:5px solid ${colors[grade] || '#4caf50'}">
                    <p style="margin:0 0 10px;font-size:13px;color:#666">原文：<em style="color:#333">"${text}"</em></p>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
                        <div><label style="font-size:11px;color:#888">情感评分</label>
                            <div style="font-size:22px;font-weight:700;color:#2c5530">${d.sentiment_score.toFixed(2)}</div></div>
                        <div><label style="font-size:11px;color:#888">疗效等级</label>
                            <div style="font-size:22px;font-weight:700;color:${colors[grade]}">${gradeLabels[grade]}</div></div>
                        <div><label style="font-size:11px;color:#888">整体置信度</label>
                            <div style="font-size:22px;font-weight:700;color:#1976d2">${(d.overall_confidence * 100).toFixed(0)}%</div></div>
                        <div><label style="font-size:11px;color:#888">量化评分</label>
                            <div style="font-size:22px;font-weight:700;color:#2e7d32">${score0_100.toFixed(1)}</div></div>
                    </div>
                </div>`;
            });
    }

    return { init };
})();
