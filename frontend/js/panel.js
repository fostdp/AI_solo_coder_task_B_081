class PanelManager {
    constructor(panelSelector) {
        this.panel = document.querySelector(panelSelector);
        this.content = this.panel.querySelector('#panel-content');
        this.isVisible = false;

        this.setupCloseButton();
    }

    setupCloseButton() {
        const closeBtn = this.panel.querySelector('#close-panel');
        closeBtn.addEventListener('click', () => {
            this.hide();
        });
    }

    show() {
        this.panel.style.display = 'block';
        this.isVisible = true;
    }

    hide() {
        this.panel.style.display = 'none';
        this.isVisible = false;
    }

    setContent(html) {
        this.content.innerHTML = html;
    }

    showNodeDetail(node) {
        this.show();

        if (node.type === 'herb') {
            this.showHerbDetail(node);
        } else if (node.type === 'formula') {
            this.showFormulaDetail(node);
        } else if (node.type === 'disease') {
            this.showDiseaseDetail(node);
        }
    }

    showHerbDetail(node) {
        const props = node.properties || {};
        const nature = props.nature || '';
        const natureClass = this.getNatureClass(nature);

        let basicHtml = `
            <h3>${node.label}</h3>
            <div class="panel-section">
                <h4>基本信息</h4>
                <div class="info-item">
                    <span class="info-label">类别</span>
                    <span class="info-value">${props.category || '-'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">药性</span>
                    <span class="info-value">
                        <span class="tag ${natureClass}">${nature || '-'}</span>
                    </span>
                </div>
            </div>
            <div class="panel-section">
                <h4>药味</h4>
                <div class="tag-list">
                    ${(props.flavor || []).map(f => `<span class="tag">${f}</span>`).join('') || '<span style="color:#999">暂无</span>'}
                </div>
            </div>
            <div class="panel-section">
                <h4>归经</h4>
                <div class="tag-list">
                    ${(props.meridians || []).map(m => `<span class="tag">${m}经</span>`).join('') || '<span style="color:#999">暂无</span>'}
                </div>
            </div>
            <div id="herb-v2-section" class="panel-section" style="display:none"></div>
            <div class="panel-section">
                <h4>相关操作</h4>
                <button class="btn btn-primary btn-sm" onclick="PanelManager.viewHerbGraph('${node.label}')">
                    查看关联图谱
                </button>
                <button class="btn btn-sm" style="margin-top:8px" onclick="PanelManager.searchHerbFormulas('${node.label}')">
                    查找含此药的方剂
                </button>
                <button class="btn btn-sm" style="margin-top:8px" onclick="PanelManager.viewHerbDoseCurve('${node.label}')">
                    📊 剂量-效应曲线
                </button>
            </div>
        `;

        this.setContent(basicHtml);

        fetch(`${API_BASE}/efficacy/herb/${encodeURIComponent(node.label)}/profile`)
            .then(r => r.json())
            .then(profile => {
                const v2Section = document.getElementById('herb-v2-section');
                if (!v2Section) return;

                let v2Html = '<h4>✨ 药物分析</h4>';

                if (profile.dose_response) {
                    const dr = profile.dose_response;
                    v2Html += `
                        <div style="padding:8px 10px;background:#f1f8e9;border-radius:6px;margin-bottom:8px;border-left:3px solid #4caf50">
                            <div style="font-size:12px;color:#2e7d32;font-weight:600;margin-bottom:4px">📊 剂量-效应</div>
                            <div style="font-size:12px;color:#555">最优剂量：<strong>${dr.optimal_dose_range[0]}-${dr.optimal_dose_range[1]}g</strong></div>
                            <div style="font-size:12px;color:#555">模型拟合 R²：<strong>${dr.r_squared.toFixed(3)}</strong></div>
                            ${dr.max_safe_dose_g ? `<div style="font-size:12px;color:#c62828">⚠ 安全上限：<strong>${dr.max_safe_dose_g}g</strong></div>` : ''}
                        </div>
                    `;
                }

                if (profile.is_toxic && profile.toxicity) {
                    const tx = profile.toxicity;
                    const sevColor = { "轻度": "#ffc107", "中度": "#ff9800", "严重": "#f44336" };
                    v2Html += `
                        <div style="padding:8px 10px;background:#fff3e0;border-radius:6px;margin-bottom:8px;border-left:3px solid #e65100">
                            <div style="font-size:12px;color:#bf360c;font-weight:600;margin-bottom:4px">☠️ 毒性档案</div>
                            <div style="font-size:12px;color:#555">LD₅₀：<strong>${tx.ld50_mgkg || '-'} mg/kg</strong></div>
                            <div style="font-size:12px;color:#555">安全剂量：<strong>≤${tx.max_safe_dose_g || '-'}g</strong></div>
                            <div style="font-size:12px;color:#555">妊娠风险：<strong style="color:${tx.pregnancy_risk === '禁用' ? '#c62828' : '#e65100'}">${tx.pregnancy_risk || '无标注'}</strong></div>
                            <div style="font-size:12px;color:#555;margin-top:4px">毒性成分：${(tx.toxic_ingredients || []).join('、') || '无'}</div>
                            ${(tx.adverse_reactions || []).map(ar =>
                                `<div style="font-size:11px;color:#666;margin-top:3px;padding-left:8px;border-left:2px solid ${sevColor[ar.severity] || '#999'}">${ar.type}(${ar.severity})：${(ar.symptoms || []).join('、')}</div>`
                            ).join('')}
                        </div>
                    `;
                }

                if (!profile.is_toxic) {
                    v2Html += `
                        <div style="padding:8px 10px;background:#e8f5e9;border-radius:6px;margin-bottom:8px;border-left:3px solid #4caf50">
                            <div style="font-size:12px;color:#2e7d32">✅ 常规安全用药，无记录毒性成分</div>
                        </div>
                    `;
                }

                v2Section.innerHTML = v2Html;
                v2Section.style.display = 'block';
            })
            .catch(() => {});
    }

    showFormulaDetail(node) {
        const props = node.properties || {};

        fetch(`${API_BASE}/formulas/by-name/${encodeURIComponent(node.label)}`)
            .then(response => response.json())
            .then(data => {
                const herbsHtml = (data.herbs || []).map(h => {
                    const isToxic = false;
                    return `<span class="tag">${h.name} <small>${h.dosage}</small></span>`;
                }).join('');

                const indicationsHtml = (data.indications || []).map(d =>
                    `<span class="tag">${d}</span>`
                ).join('');

                const html = `
                    <h3>${node.label}</h3>

                    <div class="panel-section">
                        <h4>基本信息</h4>
                        <div class="info-item">
                            <span class="info-label">朝代</span>
                            <span class="info-value">${data.dynasty || '-'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">作者</span>
                            <span class="info-value">${data.author || '-'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">来源</span>
                            <span class="info-value">${data.source || '-'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">剂型</span>
                            <span class="info-value">${data.form || '-'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">使用频率</span>
                            <span class="info-value" style="color:#4caf50;font-weight:600">${data.frequency || 0} 次</span>
                        </div>
                    </div>

                    <div class="panel-section">
                        <h4>主治病症</h4>
                        <div class="tag-list">
                            ${indicationsHtml || '<span style="color:#999">暂无</span>'}
                        </div>
                    </div>

                    <div class="panel-section">
                        <h4>药物组成（${data.herbs ? data.herbs.length : 0}味）</h4>
                        <div class="tag-list" id="formula-herbs-tags">
                            ${herbsHtml || '<span style="color:#999">暂无</span>'}
                        </div>
                    </div>

                    <div class="panel-section">
                        <h4>用法</h4>
                        <p style="font-size:13px;color:#555">${data.usage || '暂无'}</p>
                    </div>

                    <div id="formula-v2-section" class="panel-section" style="display:none">
                        <p style="font-size:12px;color:#999">正在加载疗效评估...</p>
                    </div>

                    <div class="panel-section">
                        <button class="btn btn-primary btn-sm" onclick="PanelManager.viewFormulaGraph('${node.label}')">
                            查看方剂图谱
                        </button>
                        <button class="btn btn-sm" style="margin-top:8px" onclick="PanelManager.viewFormulaEfficacy('${node.label}')">
                            💯 查看疗效详情
                        </button>
                        <button class="btn btn-sm" style="margin-top:8px" onclick="PanelManager.viewFormulaRisk('${node.label}')">
                            ⚠️ 查看风险评估
                        </button>
                    </div>
                `;

                this.setContent(html);

                fetch(`${API_BASE}/efficacy/formula/${encodeURIComponent(node.label)}/quick-score`)
                    .then(r => r.json())
                    .then(score => {
                        const v2Section = document.getElementById('formula-v2-section');
                        if (!v2Section) return;

                        if (!score.efficacy_score && score.efficacy_score !== 0) {
                            v2Section.innerHTML = '<h4>✨ 综合评估</h4><p style="font-size:12px;color:#999">暂无疗效数据</p>';
                            v2Section.style.display = 'block';
                            return;
                        }

                        const rlColor = { "安全": "#4caf50", "低": "#8bc34a", "中": "#ff9800", "高": "#f44336", "极高": "#b71c1c" };
                        let v2Html = '<h4>✨ 综合评估</h4>';

                        v2Html += `
                            <div style="display:flex;gap:8px;margin-bottom:8px">
                                <div style="flex:1;padding:8px;background:linear-gradient(135deg,#e8f5e9,#c8e6c9);border-radius:6px;text-align:center">
                                    <div style="font-size:11px;color:#666">疗效评分</div>
                                    <div style="font-size:22px;font-weight:700;color:#2c5530">${score.efficacy_score.toFixed(1)}</div>
                                    <div style="font-size:10px;color:#888">/100</div>
                                </div>
                                <div style="flex:1;padding:8px;background:${rlColor[score.risk_level] || '#eee'}22;border-radius:6px;text-align:center;border:1px solid ${rlColor[score.risk_level] || '#ddd'}">
                                    <div style="font-size:11px;color:#666">风险等级</div>
                                    <div style="font-size:22px;font-weight:700;color:${rlColor[score.risk_level] || '#999'}">${score.risk_level || '-'}</div>
                                    <div style="font-size:10px;color:#888">${score.risk_score || 0}分</div>
                                </div>
                            </div>
                        `;

                        if (score.avg_days_to_effect) {
                            v2Html += `<div style="font-size:12px;color:#555;margin-bottom:4px">⏱ 平均见效：<strong>${score.avg_days_to_effect.toFixed(1)}天</strong></div>`;
                        }

                        if (score.has_clinical_evidence) {
                            v2Html += `<div style="font-size:12px;color:#1565c0;margin-bottom:4px">🏆 有临床证据支持：${(score.clinical_indications || []).join('、')}</div>`;
                        }

                        if (score.risk_pairs_count > 0) {
                            v2Html += `<div style="font-size:12px;color:#c62828;margin-bottom:4px">⚠ 含风险药对：<strong>${score.risk_pairs_count}对</strong></div>`;
                        }

                        if (score.warnings && score.warnings.length > 0) {
                            v2Html += `<div style="padding:6px 8px;background:#fff3e0;border-radius:4px;margin-top:6px;font-size:11px;color:#e65100">⚠ ${score.warnings[0]}${score.warnings.length > 1 ? ` 等${score.warnings.length}项` : ''}</div>`;
                        }

                        v2Section.innerHTML = v2Html;
                        v2Section.style.display = 'block';
                    })
                    .catch(() => {});
            })
            .catch(() => {
                const html = `
                    <h3>${node.label}</h3>
                    <div class="panel-section">
                        <div class="info-item">
                            <span class="info-label">朝代</span>
                            <span class="info-value">${props.dynasty || '-'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">作者</span>
                            <span class="info-value">${props.author || '-'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">使用频率</span>
                            <span class="info-value" style="color:#4caf50;font-weight:600">${props.frequency || 0} 次</span>
                        </div>
                    </div>
                    <p style="color:#999;font-size:12px">详细信息加载失败</p>
                `;
                this.setContent(html);
            });
    }

    showDiseaseDetail(node) {
        const props = node.properties || {};

        fetch(`${API_BASE}/diseases/by-name/${encodeURIComponent(node.label)}`)
            .then(response => response.json())
            .then(data => {
                const symptomsHtml = (data.symptoms || []).map(s =>
                    `<span class="tag">${s}</span>`
                ).join('');

                const html = `
                    <h3>${node.label}</h3>

                    <div class="panel-section">
                        <h4>基本信息</h4>
                        <div class="info-item">
                            <span class="info-label">类别</span>
                            <span class="info-value">${data.category || '-'}</span>
                        </div>
                    </div>

                    <div class="panel-section">
                        <h4>常见症状</h4>
                        <div class="tag-list">
                            ${symptomsHtml || '<span style="color:#999">暂无</span>'}
                        </div>
                    </div>

                    <div id="disease-v2-section" class="panel-section" style="display:none">
                        <p style="font-size:12px;color:#999">正在加载临床证据...</p>
                    </div>

                    <div class="panel-section">
                        <h4>相关操作</h4>
                        <button class="btn btn-primary btn-sm" onclick="PanelManager.viewDiseaseGraph('${node.label}')">
                            查看疾病图谱
                        </button>
                        <button class="btn btn-sm" style="margin-top:8px" onclick="PanelManager.searchDiseaseFormulas('${node.label}')">
                            反向查找方剂
                        </button>
                        <button class="btn btn-sm" style="margin-top:8px" onclick="PanelManager.viewDiseaseClinical('${node.label}')">
                            🏆 临床证据
                        </button>
                    </div>
                `;

                this.setContent(html);

                const indication = node.label;
                const validIndications = ['感冒', '咳嗽', '胃痛', '失眠', '高血压', '糖尿病'];
                if (validIndications.includes(indication)) {
                    fetch(`${API_BASE}/efficacy/clinical/meta-analysis?indication=${encodeURIComponent(indication)}&num_trials=6`)
                        .then(r => r.json())
                        .then(meta => {
                            const v2Section = document.getElementById('disease-v2-section');
                            if (!v2Section) return;
                            let v2Html = '<h4>🏆 临床证据</h4>';
                            v2Html += `
                                <div style="padding:8px 10px;background:#e3f2fd;border-radius:6px;margin-bottom:6px">
                                    <div style="font-size:12px;color:#1565c0">Meta合并SMD：<strong>${meta.pooled_effect_size ? meta.pooled_effect_size.toFixed(3) : '-'}</strong></div>
                                    <div style="font-size:12px;color:#555">纳入研究：<strong>${meta.trials_included || 0}</strong>项</div>
                                    <div style="font-size:12px;color:#555">总患者：<strong>${meta.total_patients || 0}</strong>例</div>
                                    <div style="font-size:11px;color:#666;margin-top:4px">${meta.conclusion || '无数据'}</div>
                                </div>
                            `;
                            v2Section.innerHTML = v2Html;
                            v2Section.style.display = 'block';
                        })
                        .catch(() => {});
                }
            })
            .catch(() => {
                const html = `
                    <h3>${node.label}</h3>
                    <div class="panel-section">
                        <div class="info-item">
                            <span class="info-label">类别</span>
                            <span class="info-value">${props.category || '-'}</span>
                        </div>
                    </div>
                    <p style="color:#999;font-size:12px">详细信息加载失败</p>
                `;
                this.setContent(html);
            });
    }

    getNatureClass(nature) {
        if (nature.includes('温') || nature.includes('热')) return 'warm';
        if (nature.includes('寒') || nature.includes('凉')) return 'cold';
        return 'neutral';
    }

    static viewHerbGraph(herbName) {
        if (window.graphVis) {
            window.graphVis.loadHerbGraph(herbName);
        }
        switchView('graph');
    }

    static viewFormulaGraph(formulaName) {
        if (window.graphVis) {
            window.graphVis.loadFormulaGraph(formulaName);
        }
        switchView('graph');
    }

    static viewDiseaseGraph(diseaseName) {
        if (window.graphVis) {
            window.graphVis.loadDiseaseGraph(diseaseName);
        }
        switchView('graph');
    }

    static searchHerbFormulas(herbName) {
        switchView('formulas');
        const input = document.querySelector('#formula-search');
        if (input) {
            input.value = '';
        }
        loadFormulas(0, 20, null, null, herbName);
    }

    static searchDiseaseFormulas(diseaseName) {
        switchView('formulas');
        loadFormulas(0, 20, null, diseaseName, null);
    }

    static viewFormulaEfficacy(formulaName) {
        switchView('efficacy');
        setTimeout(() => {
            const nameInput = document.getElementById('efficacy-formula-name');
            if (nameInput) nameInput.value = formulaName;
            const btn = document.getElementById('btn-analyze-formula-efficacy');
            if (btn) btn.click();
        }, 200);
    }

    static viewFormulaRisk(formulaName) {
        switchView('risk');
        setTimeout(() => {
            const nameInput = document.getElementById('risk-formula-name');
            if (nameInput) nameInput.value = formulaName;
            fetch(`${API_BASE}/formulas/by-name/${encodeURIComponent(formulaName)}`)
                .then(r => r.json())
                .then(data => {
                    const herbs = (data.herbs || []).map(h => h.name || h);
                    const herbsInput = document.getElementById('risk-formula-herbs');
                    if (herbsInput) herbsInput.value = herbs.join(',');
                    const btn = document.getElementById('btn-assess-formula-risk');
                    if (btn) btn.click();
                });
        }, 200);
    }

    static viewHerbDoseCurve(herbName) {
        switchView('dose');
        setTimeout(() => {
            const nameInput = document.getElementById('dose-herb-name');
            if (nameInput) nameInput.value = herbName;
            const btn = document.getElementById('btn-compute-dose-curve');
            if (btn) btn.click();
        }, 200);
    }

    static viewDiseaseClinical(diseaseName) {
        switchView('clinical');
        setTimeout(() => {
            const validIndications = ['感冒', '咳嗽', '胃痛', '失眠', '高血压', '糖尿病'];
            if (validIndications.includes(diseaseName)) {
                const selects = ['clinical-indication', 'meta-indication', 'nma-indication', 'summary-indication'];
                selects.forEach(id => {
                    const sel = document.getElementById(id);
                    if (sel) sel.value = diseaseName;
                });
                const btn = document.getElementById('btn-load-clinical-trials');
                if (btn) btn.click();
            }
        }, 200);
    }
}
