var HerbNetwork = (function() {
    var API_BASE = 'http://localhost:8000';
    var AGGREGATION_THRESHOLD = 150;
    var WORKER_NODE_THRESHOLD = 50;

    function HerbNetwork(svgSelector, canvasSelector) {
        this.svg = d3.select(svgSelector);
        this.canvas = document.querySelector(canvasSelector);
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.nodes = [];
        this.edges = [];
        this.rawNodes = [];
        this.rawEdges = [];
        this.aggregated = false;
        this.simulation = null;
        this.worker = null;
        this.useWorker = typeof Worker !== 'undefined';
        this.workerRunning = false;
        this.zoom = null;
        this.g = null;
        this.linkGroup = null;
        this.nodeGroup = null;
        this.labelGroup = null;
        this.width = 0;
        this.height = 0;
        this.colorMap = {
            '温': '#e74c3c', '热': '#c0392b', '微温': '#e67e22',
            '平': '#95a5a6', '凉': '#3498db', '寒': '#2980b9',
            '大寒': '#1a5276', '微寒': '#5dade2'
        };
        this._init();
    }

    HerbNetwork.prototype._init = function() {
        this._resize();
        this._setupZoom();
        this._setupGroups();
        if (this.useWorker) this._initWorker();
        var self = this;
        window.addEventListener('resize', function() { self._resize(); self._updateSimulation(); });
    };

    HerbNetwork.prototype._initWorker = function() {
        var self = this;
        try {
            this.worker = new Worker('js/force-worker.js');
            this.worker.onmessage = function(e) {
                var data = e.data;
                if (data.type === 'tick') {
                    self._applyWorkerPositions(data.nodes);
                    self._updatePositions();
                    if (data.converged) {
                        self.workerRunning = false;
                    } else if (self.workerRunning) {
                        self.worker.postMessage({
                            type: 'tick', nodes: self.nodes, ticks: 30,
                            chargeStrength: -80, linkDistance: 100, linkStrength: 0.2, collisionRadius: 12
                        });
                    }
                }
            };
        } catch (e) {
            this.useWorker = false;
            this.worker = null;
        }
    };

    HerbNetwork.prototype._applyWorkerPositions = function(positions) {
        var posMap = new Map();
        for (var i = 0; i < positions.length; i++) posMap.set(positions[i].id, positions[i]);
        for (var i = 0; i < this.nodes.length; i++) {
            var node = this.nodes[i];
            var pos = posMap.get(node.id);
            if (pos) { node.x = pos.x; node.y = pos.y; node.vx = pos.vx; node.vy = pos.vy; }
        }
    };

    HerbNetwork.prototype._updatePositions = function() {
        if (!this.linkGroup) return;
        var self = this;
        this.linkGroup.selectAll('line')
            .attr('x1', function(d) { var s = typeof d.source === 'object' ? d.source : self._findNode(d.source); return s ? s.x : 0; })
            .attr('y1', function(d) { var s = typeof d.source === 'object' ? d.source : self._findNode(d.source); return s ? s.y : 0; })
            .attr('x2', function(d) { var t = typeof d.target === 'object' ? d.target : self._findNode(d.target); return t ? t.x : 0; })
            .attr('y2', function(d) { var t = typeof d.target === 'object' ? d.target : self._findNode(d.target); return t ? t.y : 0; });
        this.nodeGroup.selectAll('.node').attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
        this.labelGroup.selectAll('text').attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
    };

    HerbNetwork.prototype._findNode = function(id) {
        for (var i = 0; i < this.nodes.length; i++) { if (this.nodes[i].id === id) return this.nodes[i]; }
        return null;
    };

    HerbNetwork.prototype._resize = function() {
        var container = this.svg.node().parentElement;
        this.width = container.clientWidth;
        this.height = container.clientHeight;
        this.svg.attr('width', this.width).attr('height', this.height);
        if (this.canvas) { this.canvas.width = this.width; this.canvas.height = this.height; }
    };

    HerbNetwork.prototype._setupZoom = function() {
        var self = this;
        this.zoom = d3.zoom().scaleExtent([0.1, 5]).on('zoom', function(event) {
            if (self.g) self.g.attr('transform', event.transform);
        });
        this.svg.call(this.zoom);
    };

    HerbNetwork.prototype._setupGroups = function() {
        this.g = this.svg.append('g').attr('class', 'graph-group');
        this.linkGroup = this.g.append('g').attr('class', 'links');
        this.nodeGroup = this.g.append('g').attr('class', 'nodes');
        this.labelGroup = this.g.append('g').attr('class', 'labels');
    };

    HerbNetwork.prototype._getHerbColor = function(nature) { return this.colorMap[nature] || '#95a5a6'; };

    HerbNetwork.prototype._getNodeSize = function(node) {
        if (node.type === 'formula') return Math.max(8, Math.min(40, 5 + Math.sqrt(node.size || 1) * 2));
        if (node.type === 'disease') return 14;
        if (node.type === 'aggregate') return Math.max(12, Math.min(30, 6 + Math.sqrt(node.count || 1) * 3));
        return 10;
    };

    HerbNetwork.prototype._aggregateNodes = function(nodes, edges, threshold) {
        if (nodes.length <= threshold) return { nodes: nodes, edges: edges, aggregated: false };
        var herbNodes = nodes.filter(function(n) { return n.type === 'herb'; });
        var formulaNodes = nodes.filter(function(n) { return n.type === 'formula'; });
        var diseaseNodes = nodes.filter(function(n) { return n.type === 'disease'; });
        var categoryGroups = {};
        for (var i = 0; i < herbNodes.length; i++) {
            var node = herbNodes[i];
            var cat = (node.properties && node.properties.category) || '其他';
            if (!categoryGroups[cat]) categoryGroups[cat] = [];
            categoryGroups[cat].push(node);
        }
        var aggregatedNodes = [];
        var nodeToAggId = new Map();
        for (var i = 0; i < formulaNodes.length; i++) aggregatedNodes.push(formulaNodes[i]);
        for (var i = 0; i < diseaseNodes.length; i++) aggregatedNodes.push(diseaseNodes[i]);
        var aggId = 0;
        for (var cat in categoryGroups) {
            var group = categoryGroups[cat];
            var aggNodeId = 'agg_herb_' + aggId;
            var natureCounts = {};
            for (var j = 0; j < group.length; j++) {
                nodeToAggId.set(group[j].id, aggNodeId);
                var nature = (group[j].properties && group[j].properties.nature) || '平';
                natureCounts[nature] = (natureCounts[nature] || 0) + 1;
            }
            var dominantNature = '平', maxCount = 0;
            for (var n in natureCounts) { if (natureCounts[n] > maxCount) { maxCount = natureCounts[n]; dominantNature = n; } }
            aggregatedNodes.push({ id: aggNodeId, label: cat + '(' + group.length + ')', type: 'aggregate', count: group.length,
                properties: { nature: dominantNature, category: cat, originalIds: group.map(function(n) { return n.id; }) } });
            aggId++;
        }
        var aggEdges = [], edgeSet = new Set();
        for (var i = 0; i < edges.length; i++) {
            var edge = edges[i];
            var srcId = typeof edge.source === 'object' ? edge.source.id : edge.source;
            var tgtId = typeof edge.target === 'object' ? edge.target.id : edge.target;
            var aggSrc = nodeToAggId.get(srcId) || srcId;
            var aggTgt = nodeToAggId.get(tgtId) || tgtId;
            var key = aggSrc + '|' + aggTgt;
            if (!edgeSet.has(key) && aggSrc !== aggTgt) {
                edgeSet.add(key);
                aggEdges.push({ source: aggSrc, target: aggTgt, type: edge.type || '', weight: edge.weight || 1 });
            }
        }
        return { nodes: aggregatedNodes, edges: aggEdges, aggregated: true };
    };

    HerbNetwork.prototype.loadData = function(nodeType, limit) {
        limit = limit || 50;
        var self = this;
        return fetch(API_BASE + '/graph/network?limit_per_type=' + limit)
            .then(function(r) { return r.json(); })
            .then(function(data) { self.rawNodes = data.nodes; self.rawEdges = data.edges; self.render(); return data; });
    };

    HerbNetwork.prototype.loadDiseaseGraph = function(name) {
        var self = this;
        return fetch(API_BASE + '/graph/disease-formulas/' + encodeURIComponent(name))
            .then(function(r) { return r.json(); })
            .then(function(data) { self.rawNodes = data.nodes; self.rawEdges = data.edges; self.render(); return data; });
    };

    HerbNetwork.prototype.loadHerbGraph = function(name) {
        var self = this;
        return fetch(API_BASE + '/graph/herb-formulas/' + encodeURIComponent(name))
            .then(function(r) { return r.json(); })
            .then(function(data) { self.rawNodes = data.nodes; self.rawEdges = data.edges; self.render(); return data; });
    };

    HerbNetwork.prototype.loadFormulaGraph = function(name) {
        var self = this;
        return fetch(API_BASE + '/graph/formula-detail/' + encodeURIComponent(name))
            .then(function(r) { return r.json(); })
            .then(function(data) { self.rawNodes = data.nodes; self.rawEdges = data.edges; self.render(); return data; });
    };

    HerbNetwork.prototype.render = function() {
        if (!this.rawNodes.length) return;
        var aggResult = this._aggregateNodes(this.rawNodes, this.rawEdges, AGGREGATION_THRESHOLD);
        this.nodes = aggResult.nodes;
        this.edges = aggResult.edges;
        this.aggregated = aggResult.aggregated;
        this.linkGroup.selectAll('*').remove();
        this.nodeGroup.selectAll('*').remove();
        this.labelGroup.selectAll('*').remove();

        this.linkGroup.selectAll('line').data(this.edges).enter().append('line')
            .attr('class', function(d) { return 'link ' + (d.type || ''); })
            .attr('stroke-width', function(d) { return d.weight ? Math.max(0.5, Math.min(3, d.weight / 100)) : 1; });

        var self = this;
        var node = this.nodeGroup.selectAll('g').data(this.nodes).enter().append('g')
            .attr('class', function(d) { return 'node ' + d.type + '-node'; })
            .call(this._drag());

        node.each(function(d) {
            var sel = d3.select(this);
            var size = self._getNodeSize(d);
            if (d.type === 'herb') {
                sel.append('circle').attr('r', size).attr('fill', self._getHerbColor((d.properties && d.properties.nature) || ''));
            } else if (d.type === 'aggregate') {
                sel.append('circle').attr('r', size).attr('fill', self._getHerbColor((d.properties && d.properties.nature) || ''))
                    .attr('stroke', '#333').attr('stroke-width', 2).attr('stroke-dasharray', '3,2');
            } else if (d.type === 'formula') {
                sel.append('circle').attr('r', size).attr('fill', '#f39c12');
            } else if (d.type === 'disease') {
                sel.append('circle').attr('r', size).attr('fill', '#9b59b6');
            }
        });

        this.labelGroup.selectAll('text').data(this.nodes).enter().append('text')
            .attr('class', 'node-label').text(function(d) { return d.label; })
            .attr('dy', function(d) { return self._getNodeSize(d) + 12; });

        node.on('click', function(event, d) { event.stopPropagation(); self._onNodeClick(d); });
        node.on('mouseover', function(event, d) { self._highlightNode(d); });
        node.on('mouseout', function() { self._resetHighlight(); });

        if (this.useWorker && this.nodes.length > WORKER_NODE_THRESHOLD) {
            this._startWorkerSimulation();
        } else {
            this._startD3Simulation();
        }
        this._drawCanvasBackground();
    };

    HerbNetwork.prototype._startWorkerSimulation = function() {
        if (this.simulation) this.simulation.stop();
        var workerNodes = this.nodes.map(function(n) { return { id: n.id, x: n.x, y: n.y, vx: 0, vy: 0 }; });
        var workerEdges = this.edges.map(function(e) {
            return { source: typeof e.source === 'object' ? e.source.id : e.source,
                     target: typeof e.target === 'object' ? e.target.id : e.target, type: e.type || '', weight: e.weight || 1 };
        });
        this.worker.postMessage({ type: 'init', nodes: workerNodes, edges: workerEdges, width: this.width, height: this.height });
        this.workerRunning = true;
        this.worker.postMessage({ type: 'tick', nodes: workerNodes, ticks: 50, chargeStrength: -80, linkDistance: 100, linkStrength: 0.2, collisionRadius: 12 });
    };

    HerbNetwork.prototype._startD3Simulation = function() {
        this.workerRunning = false;
        var self = this;
        this.simulation = d3.forceSimulation(this.nodes)
            .force('link', d3.forceLink(this.edges).id(function(d) { return d.id; })
                .distance(function(d) { if (d.type === 'co_occurs') return 80; if (d.type === 'contains') return 100; if (d.type === 'treats') return 120; return 100; })
                .strength(function(d) { return d.type === 'co_occurs' ? 0.5 : 0.3; }))
            .force('charge', d3.forceManyBody().strength(function(d) { if (d.type === 'formula') return -200; if (d.type === 'disease') return -150; if (d.type === 'aggregate') return -300; return -100; }))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(function(d) { return self._getNodeSize(d) + 5; }))
            .alphaDecay(0.03);

        var link = this.linkGroup.selectAll('line');
        var node = this.nodeGroup.selectAll('.node');
        var labels = this.labelGroup.selectAll('text');
        this.simulation.on('tick', function() {
            link.attr('x1', function(d) { return d.source.x; }).attr('y1', function(d) { return d.source.y; })
                .attr('x2', function(d) { return d.target.x; }).attr('y2', function(d) { return d.target.y; });
            node.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
            labels.attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; });
        });
    };

    HerbNetwork.prototype._drawCanvasBackground = function() {
        if (!this.ctx) return;
        this.ctx.clearRect(0, 0, this.width, this.height);
        var gradient = this.ctx.createRadialGradient(this.width / 2, this.height / 2, 0, this.width / 2, this.height / 2, Math.max(this.width, this.height) / 2);
        gradient.addColorStop(0, 'rgba(250,252,250,1)');
        gradient.addColorStop(1, 'rgba(240,245,240,1)');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.width, this.height);
        this.ctx.strokeStyle = 'rgba(200,220,200,0.3)';
        this.ctx.lineWidth = 1;
        for (var x = 0; x < this.width; x += 50) { this.ctx.beginPath(); this.ctx.moveTo(x, 0); this.ctx.lineTo(x, this.height); this.ctx.stroke(); }
        for (var y = 0; y < this.height; y += 50) { this.ctx.beginPath(); this.ctx.moveTo(0, y); this.ctx.lineTo(this.width, y); this.ctx.stroke(); }
    };

    HerbNetwork.prototype._updateSimulation = function() {
        if (this.simulation) { this.simulation.force('center', d3.forceCenter(this.width / 2, this.height / 2)); this.simulation.alpha(0.3).restart(); }
    };

    HerbNetwork.prototype._drag = function() {
        var self = this;
        function dragstarted(event, d) { if (self.simulation) { if (!event.active) self.simulation.alphaTarget(0.3).restart(); } d.fx = d.x; d.fy = d.y; }
        function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
        function dragended(event, d) { if (self.simulation) { if (!event.active) self.simulation.alphaTarget(0); } d.fx = null; d.fy = null; }
        return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
    };

    HerbNetwork.prototype._highlightNode = function(d) {
        var connectedIds = new Set([d.id]);
        this.edges.forEach(function(edge) {
            var srcId = typeof edge.source === 'object' ? edge.source.id : edge.source;
            var tgtId = typeof edge.target === 'object' ? edge.target.id : edge.target;
            if (srcId === d.id) connectedIds.add(tgtId);
            if (tgtId === d.id) connectedIds.add(srcId);
        });
        this.nodeGroup.selectAll('.node').classed('dimmed', function(node) { return !connectedIds.has(node.id); });
        this.labelGroup.selectAll('text').style('opacity', function(d) { return connectedIds.has(d.id) ? 1 : 0.3; });
        this.linkGroup.selectAll('.link')
            .classed('dimmed', function(edge) { var s = typeof edge.source === 'object' ? edge.source.id : edge.source; var t = typeof edge.target === 'object' ? edge.target.id : edge.target; return !(s === d.id || t === d.id); })
            .classed('highlight', function(edge) { var s = typeof edge.source === 'object' ? edge.source.id : edge.source; var t = typeof edge.target === 'object' ? edge.target.id : edge.target; return s === d.id || t === d.id; });
    };

    HerbNetwork.prototype._resetHighlight = function() {
        this.nodeGroup.selectAll('.node').classed('dimmed', false);
        this.labelGroup.selectAll('text').style('opacity', 1);
        this.linkGroup.selectAll('.link').classed('dimmed', false).classed('highlight', false);
    };

    HerbNetwork.prototype._onNodeClick = function(node) {
        if (window.panelManager) window.panelManager.showNodeDetail(node);
    };

    HerbNetwork.prototype.zoomIn = function() { this.svg.transition().duration(300).call(this.zoom.scaleBy, 1.3); };
    HerbNetwork.prototype.zoomOut = function() { this.svg.transition().duration(300).call(this.zoom.scaleBy, 0.7); };
    HerbNetwork.prototype.zoomReset = function() { this.svg.transition().duration(500).call(this.zoom.transform, d3.zoomIdentity); };

    return HerbNetwork;
})();
