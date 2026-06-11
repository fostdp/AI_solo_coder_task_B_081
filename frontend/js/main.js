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
}

function refreshGraph() {
    const nodeType = document.getElementById('node-type-filter').value;
    const limit = parseInt(document.getElementById('node-limit').value);
    
    graphVis.loadData(nodeType, limit);
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
        loadFormulas();
    });
    
    document.getElementById('formula-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            formulaPage = 0;
            loadFormulas();
        }
    });
    
    document.getElementById('formula-dynasty-filter').addEventListener('change', () => {
        formulaPage = 0;
        loadFormulas();
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
            renderFormulaTable(data);
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

function renderFormulaTable(formulas) {
    const tbody = document.getElementById('formula-table-body');
    tbody.innerHTML = formulas.map(f => `
        <tr>
            <td><strong style="color:#2c5530">${f.name}</strong></td>
            <td>${f.dynasty}</td>
            <td>${f.author}</td>
            <td>${(f.indications || []).slice(0, 2).map(i => `<span class="tag" style="padding:1px 6px;font-size:11px">${i}</span>`).join(' ')}</td>
            <td>${f.herbs ? f.herbs.length : 0}味</td>
            <td><span style="color:#4caf50;font-weight:600">${f.frequency}</span></td>
            <td>
                <button class="btn btn-sm" onclick="viewFormulaDetail('${f.name}')">详情</button>
            </td>
        </tr>
    `).join('');
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
