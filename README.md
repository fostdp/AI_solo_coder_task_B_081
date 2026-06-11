# 古代中医药方剂配伍规律挖掘系统

> 基于 FastAPI + MongoDB + Neo4j + Redis 的中医药方剂数据挖掘与新药发现辅助系统

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green)
![Neo4j](https://img.shields.io/badge/Neo4j-5.16-blue)
![Redis](https://img.shields.io/badge/Redis-7.2-red)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)

---

## 目录

- [系统架构](#系统架构)
- [功能模块](#功能模块)
- [技术栈](#技术栈)
- [快速部署](#快速部署)
- [数据模拟器](#数据模拟器)
- [API 文档](#api-文档)
- [开发指南](#开发指南)

---

## 系统架构

```
                        ┌─────────────┐
                        │   Nginx     │  (Gzip + 静态前端 + API反代)
                        │  :80        │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   Gateway   │  (API 网关 + 路由分发)
                        │   :8000     │
                        └──────┬──────┘
                               │
          ┌──────────┬─────────┼───────────┬──────────┐
          │          │         │           │          │
     ┌────▼───┐ ┌────▼────┐ ┌──▼─────┐ ┌───▼─────┐ ┌▼───────┐
     │ formula│ │ pattern │ │ drug  │ │ graph   │ │ data  │
     │ loader │ │  miner  │ │ discov │ │  api    │ │ sim   │
     │ :8001  │ │ :8002   │ │ :8003 │ │ :8004   │ │ ulator│
     └───┬────┘ └────┬────┘ └───┬────┘ └───────┘  └───────┘
         │           │          │
   ┌─────▼───────────▼──────────▼─────┐
   │      Redis 消息总线 / 缓存        │
   │         :6379                     │
   └─────┬───────────────┬────────────┘
         │               │
    ┌────▼─────┐   ┌────▼──────┐
    │ MongoDB  │   │   Neo4j   │
    │ 副本集   │   │  因果集群 │
    │ :27017   │   │  :7687    │
    └──────────┘   └───────────┘
```

### 微服务划分

| 服务 | 端口 | 职责 |
|------|------|------|
| **formula_loader** | 8001 | 方剂/中药/病症 CRUD、数据导入导出、全文搜索 |
| **pattern_miner** | 8002 | FP-Growth 关联规则、Louvain 社区发现 |
| **drug_discoverer** | 8003 | 链路预测、靶点筛选、药对分析 |
| **graph_api** | 8004 | Neo4j 图查询、子图提取、共现网络 |
| **gateway** | 8000 | 统一入口、路由分发、前端静态服务 |

### Redis 通信通道

- `formula:transactions` — 方剂事务列表缓存（30min TTL）
- `formula:updated` — 方剂变更通知（Pub/Sub）
- `graph:network` — 图谱数据缓存（10min TTL）
- `mining:result` — 挖掘结果缓存
- `community:result` — 社区发现结果缓存

---

## 功能模块

### 1. 配伍规律挖掘

- **FP-Growth 关联规则挖掘**：替代 Apriori，避免组合爆炸
  - 支持 `max_itemset_length` 参数限制项集长度（默认 3）
  - 输出药对（2-item）、角药（3-item）和关联规则
- **Louvain 社区发现**：识别药物社区
  - 大图自动启用图分区 + 增量计算
  - 支持 `partition_size` 参数（默认 100）

### 2. 新药发现辅助

- 5 种链路预测算法：
  - 共同邻居 (Common Neighbors)
  - Jaccard 系数
  - Adamic-Adar 指数
  - 资源分配 (Resource Allocation)
  - 优先连接 (Preferential Attachment)
- 靶点相似度融合：综合评分 = 0.4×AA + 0.3×Jaccard + 0.3×靶点相似度
- 药对深度分析：支持度、置信度、提升度、共同靶点

### 3. 关联网络图

- D3.js 力导向布局
- **WebWorker 离屏计算**：大图不阻塞 UI
- **节点聚合**：按中药分类聚合，>150 节点自动触发
- 药物节点按性味归经着色
- 方剂节点大小表示使用频率
- 点击节点弹出详情面板

### 4. 数据模拟

- 按朝代权重生成方剂（汉代/唐代/宋代/金元/明代/清代）
- 每朝代有独立作者池、来源典籍、方剂风格
- 药理靶点数据模拟（10 类靶点 × 6 种作用类型）

---

## 技术栈

### 后端
- **框架**: FastAPI + Gunicorn + Uvicorn Workers
- **数据库**: MongoDB 7.0（3 节点副本集）
- **图数据库**: Neo4j 5.16（3 核心因果集群）
- **缓存/消息**: Redis 7.2
- **算法**: NetworkX + 自研 FP-Growth/Louvain

### 前端
- **可视化**: D3.js v7 + SVG + Canvas
- **布局**: 原生 CSS + 响应式设计
- **性能**: WebWorker 离屏力导向计算

### 运维
- **容器化**: Docker Compose
- **反向代理**: Nginx + Gzip 压缩
- **健康检查**: Docker 内置 healthcheck

---

## 快速部署

### 前置要求

- Docker ≥ 24.0
- Docker Compose ≥ 2.0
- 至少 4GB 可用内存（推荐 8GB）

### 一键部署

```bash
# 1. 克隆项目
git clone <repo-url>
cd tcm-formula-system

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 修改密码等配置

# 3. 构建并启动基础服务（MongoDB + Neo4j + Redis）
docker compose up -d mongodb-primary mongodb-secondary1 mongodb-secondary2 \
    mongodb-init neo4j-core1 neo4j-core2 neo4j-core3 redis

# 4. 等待数据库就绪（约 60-90 秒）
docker compose ps

# 5. 启动 API 服务
docker compose up -d tcm-api

# 6. 运行数据模拟器（生成 5000 首方剂）
docker compose run --rm data-simulator

# 7. 启动前端 Nginx
docker compose up -d frontend-nginx
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost/ | 主页面 |
| API 文档 | http://localhost/docs | Swagger UI |
| API 根路径 | http://localhost/api/ | 网关入口 |
| Neo4j Browser | http://localhost:7474 | 图数据库控制台 |
| Mongo Express | http://localhost:8081 | MongoDB 管理（需 `--profile admin`） |

### 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f tcm-api
docker compose logs -f data-simulator

# 重新生成数据
docker compose run --rm data-simulator --formulas 3000 --seed 12345

# 停止所有服务
docker compose down

# 停止并删除数据卷（谨慎！）
docker compose down -v
```

---

## 数据模拟器

### 功能特性

- ✅ 按朝代权重生成方剂
- ✅ 每朝代独立作者池（30+ 位古代医家）
- ✅ 方剂风格差异化（经方/大方/和剂/攻邪/温补/温病）
- ✅ 药理靶点模拟（GPCR/离子通道/酶/激酶 等 10 类）
- ✅ 剂量单位多样化（g/两/钱/分）
- ✅ 炮制方法（生用/酒炙/醋炙/蜜炙/炒/煅/蒸 等 13 种）

### Docker 方式运行

```bash
# 默认生成 5000 首
docker compose run --rm data-simulator

# 自定义数量和种子
docker compose run --rm data-simulator \
    --formulas 10000 \
    --seed 2024

# 按朝代权重生成（重汉代）
docker compose run -e SIM_DYNASTY_WEIGHTS='{"汉代":0.5,"唐代":0.2,"宋代":0.15,"金元":0.1,"明代":0.03,"清代":0.02}' \
    --rm data-simulator

# 不清空现有数据，追加
docker compose run -e SIM_CLEAR_BEFORE=false --rm data-simulator --formulas 1000
```

### 本地方式运行

```bash
cd backend
python -m data.simulator --formulas 5000 --seed 42
```

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--formulas` | int | 5000 | 生成方剂数量 |
| `--targets` | int | 100 | 靶点数量上限 |
| `--seed` | int | 42 | 随机种子 |
| `--dynasty-weights` | JSON str | 均匀分布 | 朝代权重 |
| `--no-clear` | flag | - | 不清空现有数据 |
| `--no-neo4j` | flag | - | 不导入 Neo4j |

### 朝代分布

| 朝代 | 代表作者 | 风格 | 药味数范围 |
|------|----------|------|-----------|
| 汉代 | 张仲景、华佗、王叔和 | 经方 | 3-10 味 |
| 唐代 | 孙思邈、王焘、巢元方 | 大方 | 5-15 味 |
| 宋代 | 钱乙、刘完素、陈无择 | 和剂 | 6-18 味 |
| 金元 | 李东垣、张从正、朱丹溪 | 攻邪 | 4-12 味 |
| 明代 | 李时珍、张景岳、吴又可 | 温补 | 5-20 味 |
| 清代 | 叶天士、吴鞠通、王清任 | 温病 | 4-14 味 |

---

## API 文档

启动后访问 `http://localhost/docs` 查看完整 Swagger 文档。

### 核心端点

#### 方剂数据
- `GET /formulas/` — 方剂列表（支持全文搜索）
- `GET /formulas/{id}` — 方剂详情
- `GET /formulas/by-name/{name}` — 按名称查询
- `GET /formulas/search/by-disease` — 按病症反向查找

#### 配伍挖掘
- `GET /mining/frequent-itemsets` — 频繁项集
- `GET /mining/association-rules` — 关联规则
- `GET /mining/top-herb-pairs` — 高频药对
- `GET /mining/top-herb-triplets` — 角药组合
- `GET /mining/communities` — 药物社区发现
- `GET /mining/by-disease/{name}` — 指定病症挖掘

#### 新药发现
- `GET /discovery/link-prediction` — 链路预测
- `GET /discovery/new-pairs` — 新药对发现
- `GET /discovery/pair-detail` — 药对深度分析
- `GET /discovery/target-based` — 靶点筛选药物
- `GET /discovery/all-targets` — 全部靶点列表

#### 图数据
- `GET /graph/network` — 完整网络图数据
- `GET /graph/disease-formulas/{name}` — 病症相关子图
- `GET /graph/herb-formulas/{name}` — 药物相关子图
- `GET /graph/formula-detail/{name}` — 方剂细节子图

### 算法参数配置

配置文件：`backend/algorithm_config.json`

```json
{
  "fp_growth": {
    "min_support": 0.05,
    "min_confidence": 0.3,
    "max_itemset_length": 3
  },
  "louvain": {
    "partition_size": 100,
    "resolution": 1.0
  },
  "graph": {
    "aggregation_threshold": 150,
    "worker_node_threshold": 50
  }
}
```

---

## 开发指南

### 项目结构

```
.
├── backend/
│   ├── shared/              # 公共模块
│   │   ├── config.py        # 配置 + 算法参数
│   │   ├── database.py      # MongoDB/Neo4j 连接
│   │   ├── redis_client.py  # Redis 封装
│   │   └── models.py        # Pydantic 模型
│   ├── formula_loader/      # 方剂数据服务
│   ├── pattern_miner/       # 关联规则 + 社区发现
│   ├── drug_discoverer/     # 链路预测 + 靶点
│   ├── graph_api/           # 图查询服务
│   ├── data/
│   │   ├── tcm_data.py      # 基础数据（中药/病症）
│   │   └── simulator.py     # 数据模拟器
│   ├── gateway.py           # API 网关
│   └── regression_test.py   # 回归测试
├── frontend/
│   ├── js/
│   │   ├── herb_network.js  # 网络图组件
│   │   ├── formula_detail.js# 详情面板组件
│   │   ├── force-worker.js  # 力导向 Worker
│   │   └── main.js          # 主逻辑
│   └── css/style.css
├── deploy/
│   ├── mongodb/             # MongoDB 副本集配置
│   ├── neo4j/               # Neo4j 集群配置
│   ├── nginx/               # Nginx + Gzip 配置
│   └── gunicorn_conf.py     # Gunicorn 配置
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动数据库（Docker）
docker compose up -d mongodb-primary redis

# 设置环境变量
export MONGODB_URL=mongodb://admin:password@localhost:27017/tcm_formulas?authSource=admin
export REDIS_URL=redis://localhost:6379/0

# 运行网关
cd backend
uvicorn gateway:app --reload --port 8000

# 运行回归测试
python regression_test.py
```

### 扩展新服务

1. 在 `backend/` 下新建服务目录
2. 继承 `shared/` 中的公共模块
3. 在 `gateway.py` 的 `SERVICE_MAP` 中添加路由
4. 在 `docker-compose.yml` 中添加服务定义

---

## 性能优化记录

| 版本 | 问题 | 优化方案 |
|------|------|---------|
| v1.0 | Apriori 组合爆炸 | FP-Growth + max_itemset_length |
| v1.0 | Louvain 大图内存高 | 图分区 + 增量计算 |
| v1.0 | 前端力导向布局慢 | WebWorker + 节点聚合 |
| v1.0 | 文本搜索慢 | MongoDB 全文索引 |
| v2.0 | 单体架构难扩展 | 微服务拆分 + Redis 通信 |
| v2.0 | 单点故障风险 | MongoDB 副本集 + Neo4j 因果集群 |
| v2.0 | 前端加载慢 | Nginx Gzip 压缩 + 浏览器缓存 |
| v2.0 | 并发能力不足 | Gunicorn 多 Uvicorn Worker |

---

## License

MIT License
