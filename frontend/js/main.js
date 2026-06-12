let graphVis = null;
let panelManager = null;

let formulaPage = 0;
let formulaTotal = 0;
let herbPage = 0;
let herbTotal = 0;
const pageSize = 20;

document.addEventListener('DOMContentLoaded', () => {
    initGraph();
    initPanel();
    initNavigation();
    initStats();
    initGraphControls();
    initFormulaView();
    initHerbView();
    initDiseaseView();
    initMiningView();
    initDiscoveryView();
    EfficacyScorer.init();
    DoseResponseModeler.init();
    AdverseEventMiner.init();
    ClinicalTrialIntegrator.init();
    loadInitialData();
});

function initGraph() {
    graphVis = new HerbNetwork('#graph-svg', '#graph-canvas');
    window.graphVis = graphVis;
}

function initPanel() {
    panelManager = new FormulaDetail('#detail-panel');
    window.panelManager = panelManager;
}

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            switchView(view);
        });
    });
}

function switchView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewName}`).classList.add('active');
    
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.dataset.view === viewName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    if (viewName === 'graph') {
        setTimeout(() => {
            graphVis.resize();
            graphVis.updateSimulation();
        }, 100);
    }
}

function initStats() {
    fetch(`${API_BASE}/api/stats`)
        .then(response => response.json())
        .then(data => {
            animateNumber('stat-formulas', data.formulas_count);
            animateNumber('stat-herbs', data.herbs_count);
            animateNumber('stat-diseases', data.diseases_count);
        })
        .catch(err => {
            console.error('加载统计数据失败:', err);
        });
}

function animateNumber(elementId, target) {
    const element = document.getElementById(elementId);
    const duration = 1000;
    const start = 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (target - start) * easeOut);
        element.textContent = current.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

function initGraphControls() {
    document.getElementById('btn-refresh-graph').addEventListener('click', refreshGraph);
    
    document.getElementById('btn-zoom-in').addEventListener('click', () => {
        graphVis.zoomIn();
    });
    
    document.getElementById('btn-zoom-out').addEventListener('click', () => {
        graphVis.zoomOut();
    });
    
    document.getElementById('btn-zoom-reset').addEventListener('click', () => {
        graphVis.zoomReset();
    });
    
    document.getElementById('node-type-filter').addEventListener('change', refreshGraph);
    document.getElementById('node-limit').addEventListener('change', refreshGraph);

    document.getElementById('btn-toggle-risk-overlay').addEventListener('click', toggleRiskOverlay);
}

function refreshGraph() {
    const nodeType = document.getElementById('node-type-filter').value;
    const limit = parseInt(document.getElementById('node-limit').value);
    
    graphVis.loadData(nodeType, limit);
}

function toggleRiskOverlay() {
    const btn = document.getElementById('btn-toggle-risk-overlay');
    if (graphVis.riskEdgesVisible) {
        graphVis.clearRiskEdges();
        btn.classList.remove('active');
        btn.style.background = '';
        btn.style.color = '';
        const leg = document.getElementById('legend-risk-edge');
        if (leg) leg.style.display = 'none';
        return;
    }
    btn.textContent = '⚠ 加载中...';
    fetch(`${API_BASE}/efficacy/adverse/network-annotations?min_risk_level=中&limit=500`)
        .then(r => r.json())
        .then(d => {
            const edges = d.risk_edges || [];
            if (!edges.length) {
                btn.textContent = '⚠ 风险';
                alert('当前无匹配风险药对');
                return;
            }
            graphVis.overlayRiskEdges(edges);
            btn.textContent = '⚠ 风险 ✓';
            btn.classList.add('active');
            btn.style.background = '#ff4444';
            btn.style.color = '#fff';
            const leg = document.getElementById('legend-risk-edge');
            if (leg) leg.style.display = '';
            window.riskEdges = edges;
        })
        .catch(() => {
            btn.textContent = '⚠ 风险';
            alert('加载风险标注失败');
        });
}

function loadInitialData() {
    graphVis.loadData('all', 50);
    loadHerbCategories();
    loadDiseaseCategories();
    loadDynastyOptions();
    loadDiseaseGrid();
    loadTopPairs();
    loadTopTriplets();
    loadTargets();
}

function initFormulaView() {
    document.getElementById('btn-search-formula').addEventListener('click', () => {
        formulaPage = 0;
        const sortBy = document.getElementById('formula-sort-filter').value;
        if (sortBy === 'efficacy') {
            loadFormulasWithEfficacy();
        } else {
            loadFormulas();
        }
    });
    
    document.getElementById('formula-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            formulaPage = 0;
            const sortBy = document.getElementById('formula-sort-filter').value;
            if (sortBy === 'efficacy') {
                loadFormulasWithEfficacy();
            } else {
                loadFormulas();
            }
        }
    });
    
    document.getElementById('formula-dynasty-filter').addEventListener('change', () => {
        formulaPage = 0;
        const sortBy = document.getElementById('formula-sort-filter').value;
        if (sortBy === 'efficacy') {
            loadFormulasWithEfficacy();
        } else {
            loadFormulas();
        }
    });

    document.getElementById('formula-sort-filter').addEventListener('change', () => {
        formulaPage = 0;
        const sortBy = document.getElementById('formula-sort-filter').value;
        if (sortBy === 'efficacy') {
            loadFormulasWithEfficacy();
        } else {
            loadFormulas();
        }
    });

    document.getElementById('th-efficacy-score').addEventListener('click', () => {
        document.getElementById('formula-sort-filter').value = 'efficacy';
        formulaPage = 0;
        loadFormulasWithEfficacy();
    });
}

function loadFormulas(page = 0, size = 20, keyword = null, disease = null, herb = null) {
    const searchKeyword = keyword !== null ? keyword : document.getElementById('formula-search').value;
    const dynasty = document.getElementById('formula-dynasty-filter').value;
    const diseaseFilter = disease !== null ? disease : '';
    const herbFilter = herb !== null ? herb : '';
    
    const skip = page * size;
    let url = `${API_BASE}/formulas/?skip=${skip}&limit=${size}`;
    
    if (searchKeyword) url += `&keyword=${encodeURIComponent(searchKeyword)}`;
    if (dynasty) url += `&dynasty=${encodeURIComponent(dynasty)}`;
    if (diseaseFilter) url += `&disease=${encodeURIComponent(diseaseFilter)}`;
    if (herbFilter) url += `&herb=${encodeURIComponent(herbFilter)}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const names = data.map(f => f.name).join(',');
            fetch(`${API_BASE}/efficacy/clinical/formula-evidence-batch?names=${encodeURIComponent(names)}`)
                .then(r => r.json()).catch(() => ({ evidence: {} }))
                .then(evidenceData => {
                    const evidenceMap = {};
                    const ev = evidenceData.evidence || evidenceData;
                    Object.entries(ev).forEach(([name, val]) => {
                        if (val && val.has_evidence) evidenceMap[name] = val;
                    });
                    renderFormulaTable(data, {}, evidenceMap);
                })
                .catch(() => renderFormulaTable(data));
            formulaPage = page;
            
            let countUrl = `${API_BASE}/formulas/count`;
            const params = [];
            if (searchKeyword) params.push(`keyword=${encodeURIComponent(searchKeyword)}`);
            if (dynasty) params.push(`dynasty=${encodeURIComponent(dynasty)}`);
            if (diseaseFilter) params.push(`disease=${encodeURIComponent(diseaseFilter)}`);
            if (herbFilter) params.push(`herb=${encodeURIComponent(herbFilter)}`);
            if (params.length) countUrl += '?' + params.join('&');
            
            return fetch(countUrl);
        })
        .then(response => response.json())
        .then(data => {
            formulaTotal = data.count;
            renderPagination('formula-pagination', formulaPage, formulaTotal, pageSize, (p) => loadFormulas(p, size, keyword, disease, herb));
        })
        .catch(err => {
            console.error('加载方剂数据失败:', err);
        });
}

function loadFormulasWithEfficacy(page = 0, size = 20) {
    const searchKeyword = document.getElementById('formula-search').value;
    const dynasty = document.getElementById('formula-dynasty-filter').value;

    const skip = page * size;
    let url = `${API_BASE}/formulas/?skip=${skip}&limit=${size}`;

    if (searchKeyword) url += `&keyword=${encodeURIComponent(searchKeyword)}`;
    if (dynasty) url += `&dynasty=${encodeURIComponent(dynasty)}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            const names = data.map(f => f.name).join(',');
            Promise.all([
                fetch(`${API_BASE}/efficacy/formulas/scores-batch?names=${encodeURIComponent(names)}`)
                    .then(r => r.json()).catch(() => ({})),
                fetch(`${API_BASE}/efficacy/clinical/formula-evidence-batch?names=${encodeURIComponent(names)}`)
                    .then(r => r.json()).catch(() => ({ evidence: {} }))
            ])
            .then(([scoresData, evidenceData]) => {
                const scoresMap = {};
                (scoresData.scores || []).forEach(s => {
                    scoresMap[s.name] = s.score;
                });
                Object.entries(scoresData).forEach(([name, val]) => {
                    if (val && typeof val === 'object' && val.efficacy_score !== undefined) {
                        scoresMap[name] = val.efficacy_score;
                    }
                });
                const evidenceMap = {};
                const ev = evidenceData.evidence || evidenceData;
                Object.entries(ev).forEach(([name, val]) => {
                    if (val && val.has_evidence) evidenceMap[name] = val;
                });
                data.sort((a, b) => (scoresMap[b.name] || 0) - (scoresMap[a.name] || 0));
                renderFormulaTable(data, scoresMap, evidenceMap);
                return data;
            })
            .catch(() => {
                renderFormulaTable(data);
                return data;
            });
        })
        .then(() => {
            formulaPage = page;
            let countUrl = `${API_BASE}/formulas/count`;
            const params = [];
            if (searchKeyword) params.push(`keyword=${encodeURIComponent(searchKeyword)}`);
            if (dynasty) params.push(`dynasty=${encodeURIComponent(dynasty)}`);
            if (params.length) countUrl += '?' + params.join('&');
            return fetch(countUrl);
        })
        .then(response => response.json())
        .then(data => {
            formulaTotal = data.count;
            renderPagination('formula-pagination', formulaPage, formulaTotal, pageSize, (p) => loadFormulasWithEfficacy(p, size));
        })
        .catch(err => {
            console.error('加载方剂疗效数据失败:', err);
        });
}

function renderFormulaTable(formulas, efficacyScores = {}, evidenceMap = {}) {
    const tbody = document.getElementById('formula-table-body');
    tbody.innerHTML = formulas.map(f => {
        const score = efficacyScores[f.name];
        const scoreDisplay = score !== undefined
            ? `<span style="color:#2e7d32;font-weight:600">${score.toFixed(1)}</span>`
            : '-';
        const evidence = evidenceMap[f.name];
        const evidenceBadge = evidence
            ? `<span style="display:inline-block;padding:1px 6px;background:#e3f2fd;color:#1565c0;border-radius:3px;font-size:10px;font-weight:600;cursor:pointer" title="有临床证据：${(evidence.clinical_indications || []).join('、')}" onclick="PanelManager.viewDiseaseClinical('${(evidence.clinical_indications || [])[0] || ''}')">🏆 RCT</span>`
            : '';
        return `
        <tr>
            <td><strong style="color:#2c5530">${f.name}</strong> ${evidenceBadge}</td>
            <td>${f.dynasty}</td>
            <td>${f.author}</td>
            <td>${(f.indications || []).slice(0, 2).map(i => `<span class="tag" style="padding:1px 6px;font-size:11px">${i}</span>`).join(' ')}</td>
            <td>${f.herbs ? f.herbs.length : 0}味</td>
            <td><span style="color:#4caf50;font-weight:600">${f.frequency}</span></td>
            <td>${scoreDisplay}</td>
            <td>
                <button class="btn btn-sm" onclick="viewFormulaDetail('${f.name}')">详情</button>
            </td>
        </tr>
    `}).join('');
}

function viewFormulaDetail(name) {
    const mockNode = {
        id: `formula_${name}`,
        label: name,
        type: 'formula',
        properties: {}
    };
    panelManager.showFormulaDetail(mockNode);
    panelManager.show();
}

function loadDynastyOptions() {
    const dynasties = ['东汉', '唐代', '宋代', '金元', '明代', '清代'];
    const select = document.getElementById('formula-dynasty-filter');
    dynasties.forEach(d => {
        const option = document.createElement('option');
        option.value = d;
        option.textContent = d;
        select.appendChild(option);
    });
}

function initHerbView() {
    document.getElementById('btn-search-herb').addEventListener('click', () => {
        herbPage = 0;
        loadHerbs();
    });
    
    document.getElementById('herb-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            herbPage = 0;
            loadHerbs();
        }
    });
    
    document.getElementById('herb-category-filter').addEventListener('change', () => {
        herbPage = 0;
        loadHerbs();
    });
    
    document.getElementById('herb-nature-filter').addEventListener('change', () => {
        herbPage = 0;
        loadHerbs();
    });
}

function loadHerbs(page = 0, size = 20) {
    const keyword = document.getElementById('herb-search').value;
    const category = document.getElementById('herb-category-filter').value;
    const nature = document.getElementById('herb-nature-filter').value;
    
    const skip = page * size;
    let url = `${API_BASE}/herbs/?skip=${skip}&limit=${size}`;
    
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
    if (category) url += `&category=${encodeURIComponent(category)}`;
    if (nature) url += `&nature=${encodeURIComponent(nature)}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            renderHerbTable(data);
            herbPage = page;
            
            let countUrl = `${API_BASE}/herbs/count`;
            const params = [];
            if (category) params.push(`category=${encodeURIComponent(category)}`);
            if (nature) params.push(`nature=${encodeURIComponent(nature)}`);
            if (params.length) countUrl += '?' + params.join('&');
            
            return fetch(countUrl);
        })
        .then(response => response.json())
        .then(data => {
            herbTotal = data.count;
            renderPagination('herb-pagination', herbPage, herbTotal, pageSize, (p) => loadHerbs(p, size));
        })
        .catch(err => {
            console.error('加载中药数据失败:', err);
        });
}

function renderHerbTable(herbs) {
    const tbody = document.getElementById('herb-table-body');
    tbody.innerHTML = herbs.map(h => {
        const natureClass = h.nature && (h.nature.includes('温') || h.nature.includes('热')) ? 'warm' :
                          h.nature && (h.nature.includes('寒') || h.nature.includes('凉')) ? 'cold' : 'neutral';
        return `
        <tr>
            <td><strong style="color:#2c5530">${h.name}</strong></td>
            <td>${h.category}</td>
            <td><span class="tag ${natureClass}" style="padding:2px 8px;font-size:11px">${h.nature}</span></td>
            <td>${(h.flavor || []).map(f => f).join('、')}</td>
            <td>${(h.meridians || []).map(m => m).join('、')}</td>
            <td>
                <button class="btn btn-sm" onclick="viewHerbDetail('${h.name}')">详情</button>
            </td>
        </tr>
    `}).join('');
}

function viewHerbDetail(name) {
    const mockNode = {
        id: `herb_${name}`,
        label: name,
        type: 'herb',
        properties: {}
    };
    panelManager.show();
    panelManager.showHerbDetail(mockNode);
    
    fetch(`${API_BASE}/herbs/by-name/${encodeURIComponent(name)}`)
        .then(response => response.json())
        .then(data => {
            mockNode.properties = data;
            panelManager.showHerbDetail(mockNode);
        });
}

function loadHerbCategories() {
    fetch(`${API_BASE}/herbs/stats/categories`)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('herb-category-filter');
            data.forEach(item => {
                const option = document.createElement('option');
                option.value = item.category;
                option.textContent = `${item.category} (${item.count})`;
                select.appendChild(option);
            });
        })
        .catch(err => {
            console.error('加载药物分类失败:', err);
        });
}

function initDiseaseView() {
    document.getElementById('btn-search-disease').addEventListener('click', loadDiseaseGrid);
    
    document.getElementById('disease-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loadDiseaseGrid();
    });
    
    document.getElementById('disease-category-filter').addEventListener('change', loadDiseaseGrid);
}

function loadDiseaseGrid() {
    const keyword = document.getElementById('disease-search').value;
    const category = document.getElementById('disease-category-filter').value;
    
    let url = `${API_BASE}/diseases/?limit=100`;
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
    if (category) url += `&category=${encodeURIComponent(category)}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            renderDiseaseGrid(data);
        })
        .catch(err => {
            console.error('加载病症数据失败:', err);
        });
}

function renderDiseaseGrid(diseases) {
    const grid = document.getElementById('disease-grid');
    grid.innerHTML = diseases.map(d => `
        <div class="disease-card" onclick="viewDiseaseDetail('${d.name}')">
            <h3>${d.name}</h3>
            <div class="disease-category">${d.category}</div>
            <div class="disease-symptoms">
                ${(d.symptoms || []).slice(0, 3).map(s => `<span>${s}</span>`).join('')}
            </div>
        </div>
    `).join('');
}

function viewDiseaseDetail(name) {
    const mockNode = {
        id: `disease_${name}`,
        label: name,
        type: 'disease',
        properties: {}
    };
    panelManager.showDiseaseDetail(mockNode);
    panelManager.show();
}

function loadDiseaseCategories() {
    fetch(`${API_BASE}/diseases/stats/categories`)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('disease-category-filter');
            data.forEach(item => {
                const option = document.createElement('option');
                option.value = item.category;
                option.textContent = `${item.category} (${item.count})`;
                select.appendChild(option);
            });
        })
        .catch(err => {
            console.error('加载病症分类失败:', err);
        });
}

function renderPagination(containerId, currentPage, total, pageSize, onPageChange) {
    const container = document.getElementById(containerId);
    const totalPages = Math.ceil(total / pageSize);
    
    let html = '';
    
    if (currentPage > 0) {
        html += `<button class="page-btn" onclick="(${onPageChange.toString()})(${currentPage - 1})">上一页</button>`;
    }
    
    const startPage = Math.max(0, currentPage - 2);
    const endPage = Math.min(totalPages - 1, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === currentPage ? ' active' : '';
        html += `<button class="page-btn${activeClass}" onclick="pageChange_${containerId}(${i})">${i + 1}</button>`;
    }
    
    if (currentPage < totalPages - 1) {
        html += `<button class="page-btn" onclick="pageChange_${containerId}(${currentPage + 1})">下一页</button>`;
    }
    
    container.innerHTML = html;
    
    window[`pageChange_${containerId}`] = function(page) {
        onPageChange(page);
    };
}

function initMiningView() {
    document.querySelectorAll('.mining-tabs .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchMiningTab(tab);
        });
    });
    
    document.getElementById('min-support').addEventListener('input', (e) => {
        document.getElementById('min-support-val').textContent = e.target.value;
    });
    
    document.getElementById('min-confidence').addEventListener('input', (e) => {
        document.getElementById('min-confidence-val').textContent = e.target.value;
    });
    
    document.getElementById('min-lift').addEventListener('input', (e) => {
        document.getElementById('min-lift-val').textContent = e.target.value;
    });
    
    document.getElementById('resolution').addEventListener('input', (e) => {
        document.getElementById('resolution-val').textContent = e.target.value;
    });
    
    document.getElementById('btn-run-apriori').addEventListener('click', runApriori);
    document.getElementById('btn-run-rules').addEventListener('click', runAssociationRules);
    document.getElementById('btn-run-louvain').addEventListener('click', runLouvain);
}

function switchMiningTab(tabName) {
    document.querySelectorAll('.mining-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.mining-content .tab-content').forEach(c => c.classList.remove('active'));
    
    document.querySelector(`.mining-tabs .tab-btn[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
}

function runApriori() {
    const minSupport = parseFloat(document.getElementById('min-support').value);
    
    const container = document.getElementById('frequent-itemsets-container');
    container.innerHTML = '<p class="placeholder-text">正在计算...</p>';
    
    fetch(`${API_BASE}/mining/frequent-itemsets?min_support=${minSupport}&max_items=5&limit=50`)
        .then(response => response.json())
        .then(data => {
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                共 <strong>${data.total_transactions}</strong> 首方剂，最小支持度: <strong>${minSupport}</strong>
            </p>`;
            
            for (const [key, items] of Object.entries(data.itemsets)) {
                html += `
                    <div class="itemset-size-group">
                        <h4>${key} (${items.length}个)</h4>
                        <div class="itemset-list">
                            ${items.map(item => `
                                <span class="itemset-chip">
                                    ${item.items.join(' + ')}
                                    <span class="support">${item.support}</span>
                                </span>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">计算失败，请检查后端服务</p>';
            console.error(err);
        });
}

function runAssociationRules() {
    const minSupport = parseFloat(document.getElementById('min-support').value);
    const minConfidence = parseFloat(document.getElementById('min-confidence').value);
    const minLift = parseFloat(document.getElementById('min-lift').value);
    
    const container = document.getElementById('association-rules-container');
    container.innerHTML = '<p class="placeholder-text">正在生成关联规则...</p>';
    
    fetch(`${API_BASE}/mining/association-rules?min_support=${minSupport}&min_confidence=${minConfidence}&min_lift=${minLift}&limit=100`)
        .then(response => response.json())
        .then(data => {
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                共找到 <strong>${data.total_rules}</strong> 条规则，最小置信度: <strong>${minConfidence}</strong>
            </p>`;
            
            if (data.rules.length > 0) {
                html += `<table class="rules-table">
                    <thead>
                        <tr>
                            <th>前件</th>
                            <th>后件</th>
                            <th>支持度</th>
                            <th>置信度</th>
                            <th>提升度</th>
                        </tr>
                    </thead>
                    <tbody>
                `;
                
                data.rules.forEach(rule => {
                    html += `
                        <tr>
                            <td>${rule.antecedent.map(a => `<span class="rule-antecedent">${a}</span>`).join('')}</td>
                            <td>${rule.consequent.map(c => `<span class="rule-consequent">${c}</span>`).join('')}</td>
                            <td>${rule.support}</td>
                            <td><strong>${(rule.confidence * 100).toFixed(1)}%</strong></td>
                            <td>${rule.lift.toFixed(2)}</td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
            } else {
                html += '<p class="placeholder-text">未找到符合条件的规则</p>';
            }
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">计算失败，请检查后端服务</p>';
            console.error(err);
        });
}

function loadTopPairs() {
    const container = document.getElementById('top-pairs-container');
    container.innerHTML = '<p class="placeholder-text">加载中...</p>';
    
    fetch(`${API_BASE}/mining/top-herb-pairs?n=50`)
        .then(response => response.json())
        .then(data => {
            if (data.pairs.length === 0) {
                container.innerHTML = '<p class="placeholder-text">暂无数据，可能需要先导入方剂数据</p>';
                return;
            }
            
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                高频药对 Top ${data.pairs.length}
            </p>`;
            
            data.pairs.forEach((pair, index) => {
                html += `
                    <div class="pair-item">
                        <div class="pair-herbs">
                            <span style="color:#888;margin-right:8px;width:24px;text-align:right">${index + 1}</span>
                            <span class="pair-herb">${pair.herb_a}</span>
                            <span class="pair-plus">+</span>
                            <span class="pair-herb">${pair.herb_b}</span>
                        </div>
                        <div class="pair-stats">
                            <span>共现: <strong>${pair.count}</strong>次</span>
                            <span>支持度: <strong>${pair.support}</strong></span>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">加载失败</p>';
            console.error(err);
        });
}

function loadTopTriplets() {
    const container = document.getElementById('top-triplets-container');
    container.innerHTML = '<p class="placeholder-text">加载中...</p>';
    
    fetch(`${API_BASE}/mining/top-herb-triplets?n=30`)
        .then(response => response.json())
        .then(data => {
            if (data.triplets.length === 0) {
                container.innerHTML = '<p class="placeholder-text">暂无数据</p>';
                return;
            }
            
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                角药组合 Top ${data.triplets.length}
            </p>`;
            
            data.triplets.forEach((triplet, index) => {
                html += `
                    <div class="pair-item">
                        <div class="triplet-herbs">
                            <span style="color:#888;margin-right:8px;width:24px;text-align:right">${index + 1}</span>
                            ${triplet.herbs.map(h => `<span class="triplet-herb">${h}</span>`).join(' + ')}
                        </div>
                        <div class="pair-stats">
                            <span>共现: <strong>${triplet.count}</strong>次</span>
                            <span>支持度: <strong>${triplet.support}</strong></span>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">加载失败</p>';
            console.error(err);
        });
}

function runLouvain() {
    const minCooccurrence = parseInt(document.getElementById('min-cooccurrence').value);
    const resolution = parseFloat(document.getElementById('resolution').value);
    
    const container = document.getElementById('communities-container');
    container.innerHTML = '<p class="placeholder-text">正在发现社区...</p>';
    
    fetch(`${API_BASE}/mining/communities?min_co_occurrence=${minCooccurrence}&resolution=${resolution}`)
        .then(response => response.json())
        .then(data => {
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                共发现 <strong>${data.num_communities}</strong> 个药物社区，
                包含 <strong>${data.total_nodes}</strong> 味药物，
                模块度: <strong>${data.modularity}</strong>
            </p>`;
            
            data.communities.forEach(community => {
                html += `
                    <div class="community-card">
                        <div class="community-header">
                            <span class="community-name">社区 #${community.community_id + 1}</span>
                            <span class="community-size">${community.size} 味药</span>
                        </div>
                        <div class="community-herbs">
                            ${community.herbs.map(h => `
                                <span class="community-herb-tag" onclick="viewHerbDetail('${h.name}')">
                                    ${h.name}
                                </span>
                            `).join('')}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">计算失败，请检查后端服务</p>';
            console.error(err);
        });
}

function initDiscoveryView() {
    document.querySelectorAll('.discovery-tabs .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchDiscoveryTab(tab);
        });
    });
    
    document.getElementById('btn-run-prediction').addEventListener('click', runLinkPrediction);
    document.getElementById('btn-discover-pairs').addEventListener('click', discoverNewPairs);
    document.getElementById('btn-analyze-pair').addEventListener('click', analyzePair);
    document.getElementById('btn-target-search').addEventListener('click', targetBasedSearch);
}

function switchDiscoveryTab(tabName) {
    document.querySelectorAll('.discovery-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.discovery-content .tab-content').forEach(c => c.classList.remove('active'));
    
    document.querySelector(`.discovery-tabs .tab-btn[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
}

function runLinkPrediction() {
    const method = document.getElementById('prediction-method').value;
    const topN = parseInt(document.getElementById('prediction-topn').value);
    
    const container = document.getElementById('prediction-results');
    container.innerHTML = '<p class="placeholder-text">正在预测...</p>';
    
    fetch(`${API_BASE}/discovery/link-prediction?method=${method}&top_n=${topN}`)
        .then(response => response.json())
        .then(data => {
            if (data.predictions.length === 0) {
                container.innerHTML = '<p class="placeholder-text">暂无预测结果</p>';
                return;
            }
            
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                方法: <strong>${method}</strong>，预测 <strong>${data.predictions.length}</strong> 个新药对
            </p>`;
            
            data.predictions.forEach((pred, index) => {
                html += `
                    <div class="prediction-item">
                        <div class="pair-herbs">
                            <span style="color:#888;margin-right:8px;width:24px;text-align:right">${index + 1}</span>
                            <span class="pair-herb">${pred.herb_a}</span>
                            <span class="pair-plus">+</span>
                            <span class="pair-herb">${pred.herb_b}</span>
                        </div>
                        <span class="prediction-score">${pred.score.toFixed(4)}</span>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">预测失败，请检查后端服务</p>';
            console.error(err);
        });
}

function discoverNewPairs() {
    const container = document.getElementById('new-pairs-results');
    container.innerHTML = '<p class="placeholder-text">正在发现新药对...</p>';
    
    fetch(`${API_BASE}/discovery/new-pairs?top_n=50`)
        .then(response => response.json())
        .then(data => {
            if (data.predictions.length === 0) {
                container.innerHTML = '<p class="placeholder-text">暂无结果</p>';
                return;
            }
            
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                基于共现网络和药理靶点综合预测，发现 <strong>${data.predictions.length}</strong> 个潜在新药对
            </p>`;
            
            data.predictions.forEach((pred, index) => {
                html += `
                    <div class="prediction-item" style="flex-direction:column;align-items:flex-start">
                        <div style="display:flex;justify-content:space-between;width:100%;margin-bottom:6px">
                            <div class="pair-herbs">
                                <span style="color:#888;margin-right:8px;width:24px;text-align:right">${index + 1}</span>
                                <span class="pair-herb">${pred.herb_a}</span>
                                <span class="pair-plus">+</span>
                                <span class="pair-herb">${pred.herb_b}</span>
                            </div>
                            <span class="prediction-score">${pred.score.toFixed(4)}</span>
                        </div>
                        <div style="font-size:12px;color:#888">
                            共同靶点: ${pred.common_targets} 个 | 
                            靶点相似度: ${(pred.target_similarity * 100).toFixed(1)}% | 
                            Adamic-Adar: ${pred.adamic_adar.toFixed(4)}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">发现失败，请检查后端服务</p>';
            console.error(err);
        });
}

function analyzePair() {
    const herbA = document.getElementById('pair-herb-a').value.trim();
    const herbB = document.getElementById('pair-herb-b').value.trim();
    
    if (!herbA || !herbB) {
        alert('请输入两味药物名称');
        return;
    }
    
    const container = document.getElementById('pair-analysis-results');
    container.innerHTML = '<p class="placeholder-text">正在分析...</p>';
    
    fetch(`${API_BASE}/discovery/pair-detail?herb_a=${encodeURIComponent(herbA)}&herb_b=${encodeURIComponent(herbB)}`)
        .then(response => {
            if (!response.ok) throw new Error('分析失败');
            return response.json();
        })
        .then(data => {
            const html = renderPairAnalysis(data);
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">分析失败，请检查药物名称</p>';
            console.error(err);
        });
}

function renderPairAnalysis(data) {
    const a = data.herb_a;
    const b = data.herb_b;
    const analysis = data.pair_analysis;
    
    const aNatureClass = a.nature && (a.nature.includes('温') || a.nature.includes('热')) ? 'warm' :
                        a.nature && (a.nature.includes('寒') || a.nature.includes('凉')) ? 'cold' : 'neutral';
    const bNatureClass = b.nature && (b.nature.includes('温') || b.nature.includes('热')) ? 'warm' :
                        b.nature && (b.nature.includes('寒') || b.nature.includes('凉')) ? 'cold' : 'neutral';
    
    return `
        <div class="pair-analysis-header">
            <div class="pair-analysis-herb">
                <h4>${a.name}</h4>
                <span class="herb-nature ${aNatureClass}">${a.nature}</span>
                <p style="font-size:12px;color:#888;margin-top:6px">${a.category}</p>
            </div>
            <div style="display:flex;align-items:center;font-size:24px;color:#4caf50">+</div>
            <div class="pair-analysis-herb">
                <h4>${b.name}</h4>
                <span class="herb-nature ${bNatureClass}">${b.nature}</span>
                <p style="font-size:12px;color:#888;margin-top:6px">${b.category}</p>
            </div>
        </div>
        
        <div class="panel-section">
            <h4>统计指标</h4>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">${analysis.is_known_pair ? '是' : '否'}</div>
                    <div class="metric-label">已知药对</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${analysis.co_occurrence_count}</div>
                    <div class="metric-label">共现次数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${(analysis.support * 100).toFixed(2)}%</div>
                    <div class="metric-label">支持度</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${(analysis.confidence_a_to_b * 100).toFixed(1)}%</div>
                    <div class="metric-label">置信度(A→B)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${analysis.lift.toFixed(2)}</div>
                    <div class="metric-label">提升度</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${analysis.common_target_count}</div>
                    <div class="metric-label">共同靶点</div>
                </div>
            </div>
        </div>
        
        <div class="panel-section">
            <h4>共同药理靶点</h4>
            <div class="tag-list">
                ${analysis.common_targets.map(t => `<span class="tag">${t}</span>`).join('') || '<span style="color:#999">无</span>'}
            </div>
        </div>
        
        ${analysis.is_known_pair ? `
        <div class="panel-section">
            <h4>同时含此二药的方剂</h4>
            ${data.formulas_with_both.slice(0, 5).map(f => `
                <div style="padding:6px 0;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between">
                    <span>${f.name}</span>
                    <span style="color:#4caf50;font-size:12px">${f.frequency}次</span>
                </div>
            `).join('')}
        </div>
        ` : `
        <div class="panel-section">
            <h4>预测评分</h4>
            <p style="font-size:13px;color:#666">
                预测得分: <strong style="color:#e65100;font-size:16px">${analysis.prediction_score.toFixed(6)}</strong>
            </p>
            <p style="font-size:12px;color:#888;margin-top:4px">
                这是一个潜在的新药对组合，建议进一步研究验证
            </p>
        </div>
        `}
    `;
}

function loadTargets() {
    fetch(`${API_BASE}/discovery/all-targets`)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('target-select');
            data.targets.forEach(t => {
                const option = document.createElement('option');
                option.value = t.target;
                option.textContent = `${t.target} (${t.herb_count}味药)`;
                select.appendChild(option);
            });
        })
        .catch(err => {
            console.error('加载靶点数据失败:', err);
        });
}

function targetBasedSearch() {
    const target = document.getElementById('target-select').value;
    
    if (!target) {
        alert('请选择靶点');
        return;
    }
    
    const container = document.getElementById('target-results');
    container.innerHTML = '<p class="placeholder-text">正在筛选...</p>';
    
    fetch(`${API_BASE}/discovery/target-based?target=${encodeURIComponent(target)}`)
        .then(response => response.json())
        .then(data => {
            if (data.herbs.length === 0) {
                container.innerHTML = '<p class="placeholder-text">未找到相关药物</p>';
                return;
            }
            
            let html = `<p style="margin-bottom:12px;font-size:13px;color:#666">
                靶点 <strong>${data.target}</strong>，共找到 <strong>${data.total_herbs}</strong> 味相关药物
            </p>`;
            
            data.herbs.forEach(herb => {
                const affinityPercent = (herb.affinity * 100).toFixed(0);
                html += `
                    <div class="target-herb-item" onclick="viewHerbDetail('${herb.herb_name}')" style="cursor:pointer">
                        <div class="target-herb-info">
                            <span class="target-herb-name">${herb.herb_name}</span>
                            <span class="target-herb-detail">${herb.category} · ${herb.effect_type}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <div class="affinity-bar">
                                <div class="affinity-fill" style="width:${affinityPercent}%"></div>
                            </div>
                            <span style="font-size:12px;color:#4caf50;font-weight:600">${herb.affinity}</span>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            container.innerHTML = '<p class="placeholder-text" style="color:#e74c3c">筛选失败</p>';
            console.error(err);
        });
}

/* =============================== v2.0 疗效量化视图 =============================== */
function initEfficacyView() {
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
    fetch(`${API_BASE}/efficacy/formulas/ranked?dynasty=${encodeURIComponent(dynasty)}&min_total_cases=${mincases}&limit=${limit}&skip=0`)
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
    fetch(`${API_BASE}/efficacy/formula/${encodeURIComponent(name)}?num_cases=${n}`)
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
    fetch(`${API_BASE}/efficacy/analyze-text`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    })
        .then(r => r.json())
        .then(d => {
            const colors = ['#9e9e9e', '#ffc107', '#8bc34a', '#4caf50', '#2e7d32'];
            container.innerHTML = `
                <div class="result-card" style="padding:20px;margin-top:10px;background:#f5f5f5;border-left:5px solid ${colors[d.efficacy_grade] || '#4caf50'}">
                    <p style="margin:0 0 10px;font-size:13px;color:#666">原文：<em style="color:#333">"${d.raw_text}"</em></p>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
                        <div><label style="font-size:11px;color:#888">情感评分</label>
                            <div style="font-size:22px;font-weight:700;color:#2c5530">${d.sentiment_score.toFixed(2)}</div></div>
                        <div><label style="font-size:11px;color:#888">疗效等级</label>
                            <div style="font-size:22px;font-weight:700;color:${colors[d.efficacy_grade]}">${d.efficacy_grade_label}</div></div>
                        <div><label style="font-size:11px;color:#888">见效天数</label>
                            <div style="font-size:22px;font-weight:700;color:#e67e22">${d.days_to_effect || '未提及'}${d.days_to_effect ? '天' : ''}</div></div>
                        <div><label style="font-size:11px;color:#888">量化评分</label>
                            <div style="font-size:22px;font-weight:700;color:#2e7d32">${d.efficacy_score_0_100.toFixed(1)}</div></div>
                    </div>
                </div>`;
        });
}

/* =============================== v2.0 剂量-效应视图 =============================== */
function initDoseView() {
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
    fetch(`${API_BASE}/efficacy/dose-response/${encodeURIComponent(herb)}`)
        .then(r => { if (!r.ok) throw new Error('中药未找到'); return r.json(); })
        .then(d => {
            const opt = d.optimal_dose_range;
            const points = d.points;
            let maxY = 1.0;
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
    fetch(`${API_BASE}/efficacy/dose-response/meta/${encodeURIComponent(herb)}?num_studies=${n}`)
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
    fetch(`${API_BASE}/efficacy/dose-response/cross-formula/${encodeURIComponent(herb)}`)
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

/* =============================== v2.0 不良反应视图 =============================== */
function initRiskView() {
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
    fetch(`${API_BASE}/efficacy/adverse/herb/${encodeURIComponent(herb)}`)
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
    fetch(`${API_BASE}/efficacy/adverse/risk-pairs?risk_level=${encodeURIComponent(level)}&limit=500`)
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
    fetch(`${API_BASE}/efficacy/adverse/assess-formula`, {
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
    fetch(`${API_BASE}/efficacy/adverse/network-annotations?min_risk_level=${encodeURIComponent(min)}&limit=500`)
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
    fetch(`${API_BASE}/efficacy/adverse/extract-from-text`, {
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

            let herbCtxHtml = '';
            if (d.herb_context_reactions && d.herb_context_reactions.total_reactions > 0) {
                const hcr = d.herb_context_reactions;
                herbCtxHtml = `<div style="margin-top:16px;padding:12px;background:#fff3e0;border-radius:6px;border-left:3px solid #e65100">
                    <h4 style="margin:0 0 8px;color:#bf360c">🌿 上下文药物不良反应汇总</h4>
                    <p style="margin:4px 0;font-size:12px;color:#555">共 <strong>${hcr.total_reactions}</strong> 条已知不良反应</p>
                    <div style="display:flex;gap:8px;font-size:12px">
                        ${Object.entries(hcr.severity_distribution || {}).map(([k, v]) =>
                            `<span style="padding:2px 8px;background:${sevColor[k] || '#eee'}22;color:${sevColor[k] || '#333'};border-radius:3px">${k}: ${v}项</span>`
                        ).join('')}
                    </div>
                    ${(hcr.all_reactions || []).slice(0, 8).map(r =>
                        `<div style="font-size:11px;color:#555;margin-top:4px;padding-left:8px;border-left:2px solid ${sevColor[r.severity] || '#999'}">${r.herb} - ${r.reaction_type}(${r.severity})：${(r.symptoms || []).join('、')}</div>`
                    ).join('')}
                </div>`;
            }

            const noReactions = !d.extracted_reactions || d.extracted_reactions.length === 0;
            container.innerHTML = `
                <div class="result-card" style="padding:16px;margin-bottom:12px;background:${noReactions ? '#e8f5e9' : '#fff3e0'};border-left:5px solid ${noReactions ? '#4caf50' : '#e65100'}">
                    <div style="display:grid;grid-template-columns:1fr 2fr;gap:16px;align-items:center">
                        <div>
                            <h3 style="margin:0 0 8px;color:#333">📄 医案文本挖掘</h3>
                            <div style="font-size:36px;font-weight:700;color:${noReactions ? '#4caf50' : '#e65100'}">${d.reactions_found}</div>
                            <div style="font-size:12px;color:#888">检出不良反应项</div>
                        </div>
                        <div>
                            <div style="padding:8px;background:#fff;border-radius:4px;font-size:13px;color:#555">
                                <strong>📌 风险摘要：</strong>${d.risk_summary}
                            </div>
                            <div style="margin-top:8px;display:flex;gap:8px;font-size:12px">
                                ${Object.entries(d.severity_distribution || {}).map(([k, v]) =>
                                    `<span style="padding:2px 8px;background:${sevColor[k] || '#eee'};color:#fff;border-radius:3px;font-weight:600">${k}: ${v}</span>`
                                ).join('')}
                            </div>
                        </div>
                    </div>
                </div>
                ${reactionsHtml ? `<h4 style="margin:12px 0 8px">🔍 提取的不良反应</h4>${reactionsHtml}` : ''}
                ${herbCtxHtml}
            `;
        })
        .catch(err => container.innerHTML = `<p class="placeholder-text" style="color:#e74c3c">${err.message}</p>`);
}

function applyRiskEdgesToGraph() {
    const edges = window.riskEdges || [];
    if (!edges.length) {
        alert('无风险边数据，请先加载风险标注');
        return;
    }
    switchView('graph');
    setTimeout(() => {
        if (graphVis) {
            graphVis.overlayRiskEdges(edges);
            const btn = document.getElementById('btn-toggle-risk-overlay');
            if (btn) {
                btn.textContent = '⚠ 风险 ✓';
                btn.classList.add('active');
                btn.style.background = '#ff4444';
                btn.style.color = '#fff';
            }
            const leg = document.getElementById('legend-risk-edge');
            if (leg) leg.style.display = '';
        }
    }, 500);
}

/* =============================== v2.0 临床证据视图 =============================== */
function initClinicalView() {
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
    fetch(`${API_BASE}/efficacy/clinical/trials?indication=${encodeURIComponent(ind)}&num_trials=${n}`)
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
    fetch(`${API_BASE}/efficacy/clinical/meta-analysis?indication=${encodeURIComponent(ind)}`)
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
    fetch(`${API_BASE}/efficacy/clinical/network-meta?indication=${encodeURIComponent(ind)}`)
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

/* =============================== Tab切换辅助 =============================== */
function setupTabSwitching(tabSelector, contentSelector) {
    const tabs = document.querySelectorAll(tabSelector + ' .tab-btn');
    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            tabs.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const parent = btn.closest('.view');
            parent.querySelectorAll(contentSelector + ' .tab-content').forEach(c => c.classList.remove('active'));
            const target = document.getElementById('tab-' + tab);
            if (target) target.classList.add('active');
        });
    });
}
