# 传神智谱

企业经营决策分析平台的本体管理 MVP。当前版本只做"智谱"模块下的本体资产增删改查，不做合同创建、合同录入或合同审核流转。

## 技术栈

- 前端: React + TypeScript + Vite
- 后端: Python + FastAPI + SQLAlchemy
- 关系数据库: PostgreSQL
- 图数据库: Neo4j

## 端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 9000 | FastAPI 服务 |
| 前端 Vite | 9001 | 开发服务器 |
| PostgreSQL | 9002 | 关系数据库 |
| Neo4j Browser | 9003 | 图数据库浏览器 |
| Neo4j Bolt | 9004 | 图数据库连接端口 |

## 本地启动

### 1. 启动数据库

```bash
cd /Users/tianqi/Documents/CLAUDE-MAP/ts-map
docker compose up -d
```

### 2. 启动后端

```bash
cd /Users/tianqi/Documents/CLAUDE-MAP/ts-map/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9000
```

### 3. 启动前端

```bash
cd /Users/tianqi/Documents/CLAUDE-MAP/ts-map/frontend
npm run dev
```

### 默认地址

- 前端: http://127.0.0.1:9001
- 后端: http://localhost:9000
- API 文档: http://localhost:9000/docs
- Neo4j Browser: http://localhost:9003

## 已实现的系统功能

### 本体资产管理

- ✅ **本体空间管理** — 创建、列表查看、级联删除
- ✅ **对象管理** — 增删改查对象定义及字段
- ✅ **属性字典** — 对象字段的独立管理
- ✅ **关系管理** — 对象间关系的定义与维护
- ✅ **行为管理** — 规则触发后的动作模板
- ✅ **场景管理** — 业务场景的配置
- ✅ **规则管理** — 硬规则/软规则的增删改查
- ✅ **版本记录** — 所有变更的版本化留存

### 高级功能

- ✅ **级联删除** — 删除空间时自动级联删除元素、引用边、版本记录、审计日志、图同步任务及 Neo4j 节点
- ✅ **YAML 批量导入** — 支持从 YAML 文件一次性导入完整本体（含对象、属性、关系、行为、规则），自动创建引用边并同步 Neo4j
- ✅ **图遍历查询** — 从任意节点出发，支持双向/出边/入边遍历，可配置深度、节点类型过滤、关系类型过滤、结果限制
- ✅ **本体图谱可视化** — 可拖拽交互的节点关系图
- ✅ **影响分析** — 查看单个元素被引用和引用他人的完整范围

### 验证与测试

- ✅ **六级验证套件** — 本体边界验证、图遍历验证、规则引擎验证、智能体自治验证、反幻觉验证、融合判断验证
- ✅ **三个验证场景** —
  - 合同审核（21对象/163属性/24关系/10行为/25规则）
  - 保理风控（10对象/99属性/13关系/10行为/24规则）
  - 锂电池排程（13对象/141属性/16关系/10行为/21规则）

## 待实现功能（后续阶段）

- ⏳ **规则引擎执行** — 规则不只是静态配置，支持给定业务数据后按优先级匹配执行
- ⏳ **推理轨迹记录** — 记录规则执行的完整推理链，用于审计和调试
- ⏳ **自然语言图查询** — 接入 LLM，支持用自然语言提问来查询图关系
- ⏳ **评测面板** — 基于遍历结果做覆盖率分析，识别孤立节点和未命中规则
- ⏳ **语义包管理** — 语义资产的打包与发布
- ⏳ **调用信息** — 外部系统调用本体的日志与监控

## API 接口清单

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/spaces` | GET | 列出所有空间 |
| `/api/spaces` | POST | 创建空间 |
| `/api/spaces/{id}` | DELETE | 级联删除空间 |
| `/api/spaces/{id}/summary` | GET | 空间统计摘要 |
| `/api/spaces/{id}/versions` | GET | 空间版本记录 |
| `/api/ontology/{space_id}/{resource}` | GET | 列出元素 |
| `/api/ontology/{space_id}/{resource}` | POST | 创建元素 |
| `/api/ontology/{space_id}/{resource}/{id}` | GET | 获取元素 |
| `/api/ontology/{space_id}/{resource}/{id}` | PUT | 更新元素 |
| `/api/ontology/{space_id}/{resource}/{id}/deactivate` | POST | 停用元素 |
| `/api/ontology/{space_id}/{resource}/{id}/copy` | POST | 复制元素 |
| `/api/ontology/{space_id}/{resource}/{id}/impact` | GET | 影响分析 |
| `/api/ontology/{space_id}/{resource}/{id}/local-graph` | GET | 局部图视图 |
| `/api/graph/traverse` | POST | 图遍历查询 |
| `/api/graph-sync/run` | POST | 手动触发图同步 |
| `/api/admin/import-yaml` | POST | YAML 批量导入 |

## 测试脚本

### 测试图遍历

```bash
cd /Users/tianqi/Documents/CLAUDE-MAP/ts-map/scenarios

# 1. 导入测试数据
curl -s -X POST -F "file=@contract-review.yaml" http://localhost:9000/api/admin/import-yaml

# 2. 获取一个对象ID
OBJ_ID=$(curl -s 'http://localhost:9000/api/ontology/contract_review/objects?page_size=1' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['items'][0]['id'])")

# 3. 测试双向遍历
curl -s -X POST http://localhost:9000/api/graph/traverse \
  -H "Content-Type: application/json" \
  -d "{\"start_node_id\":\"$OBJ_ID\",\"direction\":\"both\",\"max_depth\":3,\"limit\":100}"

# 4. 测试出边遍历（从关系出发）
REL_ID=$(curl -s 'http://localhost:9000/api/ontology/contract_review/relations?page_size=1' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['items'][0]['id'])")
curl -s -X POST http://localhost:9000/api/graph/traverse \
  -H "Content-Type: application/json" \
  -d "{\"start_node_id\":\"$REL_ID\",\"direction\":\"outgoing\",\"max_depth\":2}"

# 5. 清理
curl -s http://localhost:9000/api/spaces \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(s['id']) for s in d['data'] if s['code']=='contract_review']" \
  | xargs -I {} curl -s -X DELETE "http://localhost:9000/api/spaces/{}"
```

### 测试级联删除

```bash
# 导入数据
curl -s -X POST -F "file=@contract-review.yaml" http://localhost:9000/api/admin/import-yaml

# 获取空间ID并删除
SPACE_ID=$(curl -s http://localhost:9000/api/spaces \
  | python3 -c "import sys,json; d=json.load(sys.stdin); spaces=[s for s in d['data'] if s['code']=='contract_review']; print(spaces[0]['id'] if spaces else '')")

curl -s -X DELETE "http://localhost:9000/api/spaces/$SPACE_ID"
```

### 测试YAML导入

```bash
# 合同审核场景
curl -s -X POST -F "file=@contract-review.yaml" http://localhost:9000/api/admin/import-yaml

# 保理风控场景
curl -s -X POST -F "file=@factoring-risk.yaml" http://localhost:9000/api/admin/import-yaml

# 锂电池排程场景
curl -s -X POST -F "file=@battery-scheduling.yaml" http://localhost:9000/api/admin/import-yaml
```

## 验证数据集覆盖情况

| 验证级别 | 说明 | 覆盖状态 |
|---------|------|---------|
| L1 本体边界 | 空间/元素/属性/关系的增删改查 | ✅ 已覆盖 |
| L2 图遍历 | 图查询执行与可视化 | ✅ 已覆盖 |
| L3 规则引擎 | 规则的触发-执行-结果链路 | ⏳ 待实现 |
| L4 智能体自治 | Agent执行规则、自主决策 | ⏳ 待实现 |
| L5 反幻觉 | LLM集成和事实校验 | ⏳ 待实现 |
| L6 融合判断 | 多源信息融合和冲突消解 | ⏳ 待实现 |
