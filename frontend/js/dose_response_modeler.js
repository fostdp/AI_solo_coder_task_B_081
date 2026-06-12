const DoseResponseModeler = (function() {
    const API_PREFIX = '/efficacy/dose-response';

    function init() {
        setupTabSwitching('.dose-tabs', '.dose-content');
        document.getElementById('btn-compute-dose-curve').addEventListener('click', computeDoseCurve);
        document.getElementById('btn-run-dose-meta').addEventListener('click', runDoseMeta);
        document.getElementById('btn-cross-formula-dose').addEventListener('click', runCrossFormulaDose);
    }

    function computeDoseCurve() {
        const herb = document.getElementById('dose-herb-name').value.trim();
        if (!herb) return alert('请输入中药名称');
        const container = document.getElementById('dose-curve-container');
        container.innerHTML = '<p class="placeholder-text">计算限制性立方样条模型...</p>';
        fetch(`${API_BASE}${API_PREFIX}/${encodeURIComponent(herb)}`)
            .then(r => { if (!r.ok) throw new Error('中药未找到'); return r.json(); })
            .then(d => {
                const opt = d.optimal_dose_range;
                const points = d.points;
                let svg = `<svg viewBox="0 0 600 300" width="100%" style="background:#fff;border:1px solid #eee;border-radius:8px">`;
                svg += `<line x1="50" y1="250" x2="580" y2="250" stroke="#ddd"/>`;
                svg += `<line x1="50" y1="30" x2="50" y2="250" stroke="#ddd"/>`;
                for (let i = 0; i <= 5; i++) {
                    svg += `<text x="30" y="${250 - i * 44}" font-size="10" fill="#888">${(i * 0.2).toFixed(1)}</text>`;
                }
                const xs = points.map(p => p.dosage_g);
                const minX = Math.min(...xs), maxX = Math.max(...xs);
                const xScale = x => 50 + (x - minX) / (maxX - minX || 1) * 520;
                const yScale = y => 250 - y * 220;
                let path = '';
                points.forEach((p, i) => {
                    const x = xScale(p.dosage_g), y = yScale(p.avg_efficacy);
                    if (i === 0) path += `M ${x} ${y}`;
                    else path += ` L ${x} ${y}`;
                    if (p.sample_size > 0) {
                        svg += `<circle cx="${x}" cy="${y}" r="${Math.max(3, Math.min(8, p.sample_size / 4))}"
                        fill="#2196f3" fill-opacity="0.5" stroke="#1976d2"/>`;
                    }
                });
                svg += `<path d="${path}" fill="none" stroke="#1976d2" stroke-width="2.5"/>`;
                const x1 = xScale(opt[0]), x2 = xScale(opt[1]);
                svg += `<rect x="${x1}" y="30" width="${x2 - x1}" height="220" fill="#8bc34a" fill-opacity="0.12" stroke="#4caf50" stroke-dasharray="4,2"/>`;
                svg += `<text x="${(x1 + x2) / 2}" y="24" text-anchor="middle" font-size="11" fill="#2e7d32" font-weight="600">最优剂量范围 [${opt[0]}-${opt[1]}g]</text>`;
                svg += `<text x="315" y="280" text-anchor="middle" font-size="11" fill="#888">剂量 (g)</text>`;
                svg += `<text transform="rotate(-90)" x="-130" y="15" font-size="11" fill="#888">平均疗效</text>`;
                svg += `</svg>`;
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:#f1f8e9">
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
                        <div><label style="font-size:11px;color:#888">中药</label>
                            <div style="font-size:18px;font-weight:700;color:#2c5530">${d.herb_name}</div></div>
                        <div><label style="font-size:11px;color:#888">最优剂量区间</label>
                            <div style="font-size:18px;font-weight:700;color:#2e7d32">${opt[0]}-${opt[1]} g</div></div>
                        <div><label style="font-size:11px;color:#888">模型 R²</label>
                            <div style="font-size:18px;font-weight:700;color:#1976d2">${d.r_squared.toFixed(3)}</div></div>
                        <div><label style="font-size:11px;color:#888">节点数</label>
                            <div style="font-size:18px;font-weight:700;color:#ff9800">${d.knots ? d.knots.length : '-'}</div></div>
                    </div>
                    ${d.warnings ? `<p style="margin-top:10px;color:#d32f2f;font-size:13px">⚠️ ${d.warnings.join('；')}</p>` : ''}
                </div>
                ${svg}
                <p style="margin-top:8px;font-size:12px;color:#757575;text-align:right">
                    模型：${d.model_type} · 绿色区域为90%最高疗效区间
                </p>
            `;
            })
            .catch(err => container.innerHTML = `<p class="placeholder-text" style="color:#e74c3c">${err.message}</p>`);
    }

    function runDoseMeta() {
        const herb = document.getElementById('dose-meta-herb').value.trim();
        const n = document.getElementById('dose-meta-n').value;
        if (!herb) return alert('请输入中药名');
        const container = document.getElementById('dose-meta-container');
        container.innerHTML = '<p class="placeholder-text">执行逆方差随机效应Meta分析...</p>';
        fetch(`${API_BASE}${API_PREFIX}/meta/${encodeURIComponent(herb)}?num_studies=${n}`)
            .then(r => r.json())
            .then(d => {
                const pct = Math.min(100, (d.i_squared || 0));
                const hetColor = pct < 50 ? '#4caf50' : pct < 75 ? '#ff9800' : '#f44336';
                let forest = `<table class="data-table" style="font-size:12px"><thead><tr>
                <th>研究</th><th>年份</th><th>剂量(g)</th><th>效应量</th><th>95% CI</th><th>权重</th></tr></thead><tbody>`;
                (d.input_studies || []).forEach(s => {
                    const es = s.effect_size, low = es - 1.96 * Math.sqrt(s.variance), high = es + 1.96 * Math.sqrt(s.variance);
                    forest += `<tr><td>${s.study_id}</td><td>${s.year}</td>
                    <td>${s.dose_range_g[0]}-${s.dose_range_g[1]}</td>
                    <td>${es.toFixed(3)}</td><td>[${low.toFixed(3)}, ${high.toFixed(3)}]</td>
                    <td>${(s.variance ? (1 / s.variance).toFixed(0) : '-')}</td></tr>`;
                });
                forest += '</tbody></table>';
                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px">
                    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:12px">
                        <div><label style="font-size:11px;color:#888">中药</label>
                            <div style="font-size:18px;font-weight:700;color:#2c5530">${d.herb_name}</div></div>
                        <div><label style="font-size:11px;color:#888">合并SMD</label>
                            <div style="font-size:18px;font-weight:700;color:${d.p_value < 0.05 ? '#2e7d32' : '#757575'}">${d.pooled_effect_size.toFixed(3)}</div></div>
                        <div><label style="font-size:11px;color:#888">95% CI</label>
                            <div style="font-size:16px;font-weight:700;color:#1976d2">[${d.ci_95[0].toFixed(3)}, ${d.ci_95[1].toFixed(3)}]</div></div>
                        <div><label style="font-size:11px;color:#888">异质性 I²</label>
                            <div style="font-size:18px;font-weight:700;color:${hetColor}">${pct.toFixed(1)}%</div></div>
                        <div><label style="font-size:11px;color:#888">P值</label>
                            <div style="font-size:18px;font-weight:700;color:${d.p_value < 0.05 ? '#2e7d32' : '#757575'}">${d.p_value < 0.001 ? '<0.001' : d.p_value.toFixed(4)}</div></div>
                    </div>
                    <p style="padding:10px;background:#f5f5f5;border-radius:6px;font-size:13px;margin:0">
                        <strong>结论：</strong>${d.p_value < 0.05 ?
                            (d.pooled_effect_size > 0 ? '该中药干预组疗效显著优于对照' : '对照组显著优于中药组') :
                            '未观察到统计学显著差异'}
                        （SMD=${d.pooled_effect_size.toFixed(3)}, P=${d.p_value < 0.001 ? '<0.001' : d.p_value.toFixed(4)}，
                        I²=${pct.toFixed(1)}%${pct > 75 ? '，异质性高，结果需谨慎解读' : ''}）
                    </p>
                </div>
                ${forest}
            `;
            });
    }

    function runCrossFormulaDose() {
        const herb = document.getElementById('dose-cross-herb').value.trim();
        if (!herb) return alert('请输入中药名称');
        const container = document.getElementById('dose-cross-container');
        container.innerHTML = '<p class="placeholder-text">查询跨方剂剂量数据...</p>';
        fetch(`${API_BASE}${API_PREFIX}/cross-formula/${encodeURIComponent(herb)}`)
            .then(r => { if (!r.ok) throw new Error('查询失败'); return r.json(); })
            .then(d => {
                const opt = d.optimal_dose_range;
                const stats = d.dose_statistics || {};
                let dotChart = '<svg viewBox="0 0 600 200" width="100%" style="background:#fff;border:1px solid #eee;border-radius:8px">';
                const allFormulas = [
                    ...(d.within_optimal.formulas || []),
                    ...(d.above_optimal.formulas || []),
                    ...(d.below_optimal.formulas || [])
                ];
                if (allFormulas.length && stats.min !== undefined) {
                    const range = Math.max(stats.max - stats.min, 1);
                    const pad = 60;
                    const xScale = v => pad + ((v - stats.min) / range) * (520 - pad);
                    const x1 = xScale(opt[0]), x2 = xScale(opt[1]);
                    dotChart += `<rect x="${x1}" y="20" width="${x2 - x1}" height="160" fill="#c8e6c9" fill-opacity="0.4" stroke="#4caf50" stroke-dasharray="4,2"/>`;
                    dotChart += `<text x="${(x1 + x2) / 2}" y="16" text-anchor="middle" font-size="10" fill="#2e7d32">最优区间 [${opt[0]}-${opt[1]}g]</text>`;
                    allFormulas.forEach((f, i) => {
                        if (f.herb_dose_g === null) return;
                        const x = xScale(f.herb_dose_g);
                        const y = 40 + (i % 8) * 18;
                        const isWithin = f.herb_dose_g >= opt[0] && f.herb_dose_g <= opt[1];
                        const color = isWithin ? '#4caf50' : f.herb_dose_g > opt[1] ? '#f44336' : '#ff9800';
                        dotChart += `<circle cx="${x}" cy="${y}" r="5" fill="${color}" opacity="0.8"/>`;
                        dotChart += `<text x="${x + 8}" y="${y + 4}" font-size="9" fill="#555">${f.formula_name}(${f.herb_dose_g}g)</text>`;
                    });
                    dotChart += `<line x1="${pad}" y1="185" x2="520" y2="185" stroke="#ddd"/>`;
                }
                dotChart += '</svg>';

                let formulaTable = '<table class="data-table" style="font-size:12px"><thead><tr>' +
                    '<th>方剂</th><th>朝代</th><th>主治</th><th>剂量(g)</th><th>区间判定</th></tr></thead><tbody>';
                allFormulas.forEach(f => {
                    if (f.herb_dose_g === null) return;
                    const isWithin = f.herb_dose_g >= opt[0] && f.herb_dose_g <= opt[1];
                    const isAbove = f.herb_dose_g > opt[1];
                    const tag = isWithin ? '<span style="color:#2e7d32;font-weight:600">✅ 最优区间内</span>'
                        : isAbove ? '<span style="color:#c62828;font-weight:600">⚠ 超出上限</span>'
                        : '<span style="color:#e65100;font-weight:600">低于下限</span>';
                    formulaTable += `<tr>
                    <td style="font-weight:600">${f.formula_name}</td>
                    <td>${f.dynasty || '-'}</td>
                    <td>${(f.indications || []).join('、') || '-'}</td>
                    <td style="font-weight:700">${f.herb_dose_g}</td>
                    <td>${tag}</td>
                </tr>`;
                });
                formulaTable += '</tbody></table>';

                container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:#f1f8e9">
                    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">
                        <div><label style="font-size:11px;color:#888">中药</label>
                            <div style="font-size:18px;font-weight:700;color:#2c5530">${d.herb_name}</div></div>
                        <div><label style="font-size:11px;color:#888">最优区间</label>
                            <div style="font-size:18px;font-weight:700;color:#2e7d32">${opt[0]}-${opt[1]} g</div></div>
                        <div><label style="font-size:11px;color:#888">含药方剂数</label>
                            <div style="font-size:18px;font-weight:700">${d.total_formulas_found}</div></div>
                        <div><label style="font-size:11px;color:#888">平均剂量</label>
                            <div style="font-size:18px;font-weight:700;color:#1976d2">${stats.mean || '-'} g</div></div>
                        <div><label style="font-size:11px;color:#888">区间内占比</label>
                            <div style="font-size:18px;font-weight:700;color:${d.within_optimal.count > d.formulas_with_dose_data / 2 ? '#2e7d32' : '#ff9800'}">
                                ${d.formulas_with_dose_data ? Math.round(d.within_optimal.count / d.formulas_with_dose_data * 100) : 0}%
                            </div></div>
                    </div>
                    <div style="margin-top:8px;display:flex;gap:16px;font-size:12px;color:#555">
                        <span>✅ 区间内: <strong>${d.within_optimal.count}</strong></span>
                        <span>⚠ 超上限: <strong style="color:#c62828">${d.above_optimal.count}</strong></span>
                        <span>⬇ 低于下限: <strong style="color:#e65100">${d.below_optimal.count}</strong></span>
                        <span>模型 R²: <strong>${d.r_squared.toFixed(3)}</strong></span>
                    </div>
                </div>
                <h5 style="margin:12px 0 6px">剂量分布图</h5>
                ${dotChart}
                <h5 style="margin:16px 0 6px">方剂详情</h5>
                ${formulaTable}
            `;
            })
            .catch(err => container.innerHTML = `<p class="placeholder-text" style="color:#e74c3c">${err.message}</p>`);
    }

    return { init };
})();
