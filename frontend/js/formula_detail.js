var FormulaDetail = (function() {
    var API_BASE = 'http://localhost:8000';

    function FormulaDetail(panelSelector) {
        this.panel = document.querySelector(panelSelector);
        this.content = this.panel.querySelector('#panel-content');
        this.isVisible = false;
        this._setupCloseButton();
    }

    FormulaDetail.prototype._setupCloseButton = function() {
        var self = this;
        this.panel.querySelector('#close-panel').addEventListener('click', function() { self.hide(); });
    };

    FormulaDetail.prototype.show = function() { this.panel.style.display = 'block'; this.isVisible = true; };
    FormulaDetail.prototype.hide = function() { this.panel.style.display = 'none'; this.isVisible = false; };
    FormulaDetail.prototype.setContent = function(html) { this.content.innerHTML = html; };

    FormulaDetail.prototype.showNodeDetail = function(node) {
        this.show();
        if (node.type === 'herb') this.showHerbDetail(node);
        else if (node.type === 'formula') this.showFormulaDetail(node);
        else if (node.type === 'disease') this.showDiseaseDetail(node);
        else if (node.type === 'aggregate') this.showAggregateDetail(node);
    };

    FormulaDetail.prototype.showHerbDetail = function(node) {
        var props = node.properties || {};
        var nature = props.nature || '';
        var natureClass = this._getNatureClass(nature);
        var flavors = (props.flavor || []).map(function(f) { return '<span class="tag">' + f + '</span>'; }).join('') || '<span style="color:#999">暂无</span>';
        var meridians = (props.meridians || []).map(function(m) { return '<span class="tag">' + m + '经</span>'; }).join('') || '<span style="color:#999">暂无</span>';
        var html = '<h3>' + node.label + '</h3>' +
            '<div class="panel-section"><h4>基本信息</h4>' +
            '<div class="info-item"><span class="info-label">类别</span><span class="info-value">' + (props.category || '-') + '</span></div>' +
            '<div class="info-item"><span class="info-label">药性</span><span class="info-value"><span class="tag ' + natureClass + '">' + (nature || '-') + '</span></span></div></div>' +
            '<div class="panel-section"><h4>药味</h4><div class="tag-list">' + flavors + '</div></div>' +
            '<div class="panel-section"><h4>归经</h4><div class="tag-list">' + meridians + '</div></div>' +
            '<div class="panel-section"><h4>相关操作</h4>' +
            '<button class="btn btn-primary btn-sm" onclick="FormulaDetail.viewHerbGraph(\'' + node.label + '\')">查看关联图谱</button> ' +
            '<button class="btn btn-sm" style="margin-top:8px" onclick="FormulaDetail.searchHerbFormulas(\'' + node.label + '\')">查找含此药的方剂</button></div>';
        this.setContent(html);
    };

    FormulaDetail.prototype.showFormulaDetail = function(node) {
        var self = this;
        var props = node.properties || {};
        fetch(API_BASE + '/formulas/by-name/' + encodeURIComponent(node.label))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var herbsHtml = (data.herbs || []).map(function(h) { return '<span class="tag">' + h.name + ' <small>' + h.dosage + '</small></span>'; }).join('');
                var indicationsHtml = (data.indications || []).map(function(d) { return '<span class="tag">' + d + '</span>'; }).join('');
                var html = '<h3>' + node.label + '</h3>' +
                    '<div class="panel-section"><h4>基本信息</h4>' +
                    '<div class="info-item"><span class="info-label">朝代</span><span class="info-value">' + (data.dynasty || '-') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">作者</span><span class="info-value">' + (data.author || '-') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">来源</span><span class="info-value">' + (data.source || '-') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">剂型</span><span class="info-value">' + (data.form || '-') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">使用频率</span><span class="info-value" style="color:#4caf50;font-weight:600">' + (data.frequency || 0) + ' 次</span></div></div>' +
                    '<div class="panel-section"><h4>主治病症</h4><div class="tag-list">' + (indicationsHtml || '<span style="color:#999">暂无</span>') + '</div></div>' +
                    '<div class="panel-section"><h4>药物组成（' + (data.herbs ? data.herbs.length : 0) + '味）</h4><div class="tag-list">' + (herbsHtml || '<span style="color:#999">暂无</span>') + '</div></div>' +
                    '<div class="panel-section"><h4>用法</h4><p style="font-size:13px;color:#555">' + (data.usage || '暂无') + '</p></div>' +
                    '<div class="panel-section"><button class="btn btn-primary btn-sm" onclick="FormulaDetail.viewFormulaGraph(\'' + node.label + '\')">查看方剂图谱</button></div>';
                self.setContent(html);
            })
            .catch(function() {
                var html = '<h3>' + node.label + '</h3><div class="panel-section">' +
                    '<div class="info-item"><span class="info-label">朝代</span><span class="info-value">' + (props.dynasty || '-') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">使用频率</span><span class="info-value" style="color:#4caf50;font-weight:600">' + (props.frequency || 0) + ' 次</span></div></div>' +
                    '<p style="color:#999;font-size:12px">详细信息加载失败</p>';
                self.setContent(html);
            });
    };

    FormulaDetail.prototype.showDiseaseDetail = function(node) {
        var self = this;
        var props = node.properties || {};
        fetch(API_BASE + '/diseases/by-name/' + encodeURIComponent(node.label))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var symptomsHtml = (data.symptoms || []).map(function(s) { return '<span class="tag">' + s + '</span>'; }).join('');
                var html = '<h3>' + node.label + '</h3>' +
                    '<div class="panel-section"><h4>基本信息</h4><div class="info-item"><span class="info-label">类别</span><span class="info-value">' + (data.category || '-') + '</span></div></div>' +
                    '<div class="panel-section"><h4>常见症状</h4><div class="tag-list">' + (symptomsHtml || '<span style="color:#999">暂无</span>') + '</div></div>' +
                    '<div class="panel-section"><h4>相关操作</h4>' +
                    '<button class="btn btn-primary btn-sm" onclick="FormulaDetail.viewDiseaseGraph(\'' + node.label + '\')">查看疾病图谱</button> ' +
                    '<button class="btn btn-sm" style="margin-top:8px" onclick="FormulaDetail.searchDiseaseFormulas(\'' + node.label + '\')">反向查找方剂</button></div>';
                self.setContent(html);
            })
            .catch(function() {
                var html = '<h3>' + node.label + '</h3><div class="panel-section">' +
                    '<div class="info-item"><span class="info-label">类别</span><span class="info-value">' + (props.category || '-') + '</span></div></div>' +
                    '<p style="color:#999;font-size:12px">详细信息加载失败</p>';
                self.setContent(html);
            });
    };

    FormulaDetail.prototype.showAggregateDetail = function(node) {
        var props = node.properties || {};
        var html = '<h3>' + node.label + '</h3>' +
            '<div class="panel-section"><h4>聚合信息</h4>' +
            '<div class="info-item"><span class="info-label">分类</span><span class="info-value">' + (props.category || '-') + '</span></div>' +
            '<div class="info-item"><span class="info-label">数量</span><span class="info-value">' + (node.count || 0) + ' 味药</span></div>' +
            '<div class="info-item"><span class="info-label">主流药性</span><span class="info-value">' + (props.nature || '-') + '</span></div></div>' +
            '<p style="font-size:12px;color:#888">此为聚合节点，缩小范围后可查看单味药详情</p>';
        this.setContent(html);
    };

    FormulaDetail.prototype._getNatureClass = function(nature) {
        if (nature.indexOf('温') >= 0 || nature.indexOf('热') >= 0) return 'warm';
        if (nature.indexOf('寒') >= 0 || nature.indexOf('凉') >= 0) return 'cold';
        return 'neutral';
    };

    FormulaDetail.viewHerbGraph = function(herbName) {
        if (window.graphVis) window.graphVis.loadHerbGraph(herbName);
        if (typeof switchView === 'function') switchView('graph');
    };

    FormulaDetail.viewFormulaGraph = function(formulaName) {
        if (window.graphVis) window.graphVis.loadFormulaGraph(formulaName);
        if (typeof switchView === 'function') switchView('graph');
    };

    FormulaDetail.viewDiseaseGraph = function(diseaseName) {
        if (window.graphVis) window.graphVis.loadDiseaseGraph(diseaseName);
        if (typeof switchView === 'function') switchView('graph');
    };

    FormulaDetail.searchHerbFormulas = function(herbName) {
        if (typeof switchView === 'function') switchView('formulas');
        if (typeof loadFormulas === 'function') loadFormulas(0, 20, null, null, herbName);
    };

    FormulaDetail.searchDiseaseFormulas = function(diseaseName) {
        if (typeof switchView === 'function') switchView('formulas');
        if (typeof loadFormulas === 'function') loadFormulas(0, 20, null, diseaseName, null);
    };

    return FormulaDetail;
})();
