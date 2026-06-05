# 传神智谱

企业经营决策分析平台的本体管理 MVP。当前版本只做“智谱”模块下的本体资产增删改查，不做合同创建、合同录入或合同审核流转。

## 技术栈

- 前端: React + TypeScript + Vite
- 后端: Python + FastAPI + SQLAlchemy
- 关系数据库: PostgreSQL
- 图数据库: Neo4j

## 本地启动

1. 启动数据库:

```bash
docker compose up -d postgres neo4j
```

2. 启动后端:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

3. 启动前端:

```bash
cd frontend
npm install
npm run dev
```

默认地址:

- 前端: http://127.0.0.1:5173
- 后端: http://localhost:8001
- API 文档: http://localhost:8001/docs
- Neo4j Browser: http://localhost:7474

当前机器上如果 `localhost:5173` 命中其他旧服务，请使用 `127.0.0.1:5173`。

## 当前一期范围

- 工作台
- 对象
- 关系
- 行为
- 属性字典
- 场景
- 规则
- 版本记录
- 设置

评测、推理轨迹、语义包、调用信息作为后续阶段预留。
