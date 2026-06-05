# 传神智谱 · 本体管理模块验证脚本

基于《验证数据集》六关闯关验证体系，为「本体管理模块」编写的独立验证脚本。

## 验证目标

验证本体管理模块（关系型数据库 + Neo4j 图数据库）是否完整承载了验证数据集的语义资产，API 是否按预期工作。

| 脚本 | 验证内容 | 对应关卡 |
|------|---------|---------|
| `check_env.py` | 后端/Neo4j/PostgreSQL 连通性 | 环境基线 |
| `check_api.py` | 全部 REST API 端点 | 接口基线 |
| `check_ontology.py` | 本体数据完整性（对象/关系/行为/规则/属性） | 关1 本体边界 |
| `check_graph.py` | Neo4j 图结构验证（节点/边/穿透） | 关2 图穿透 |
| `check_levels.py` | 六关闯关主控（综合断言） | 关1~关6 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 编辑配置（如有必要）
# vim config.py

# 3. 环境检查
python check_env.py

# 4. 跑全部验证
python check_levels.py

# 或单独跑某一关
python check_levels.py 1   # 关1：本体边界
python check_levels.py 2   # 关2：图穿透
python check_levels.py 3   # 关3：规则引擎
```

## 前置条件

1. 后端服务已启动（默认 http://localhost:8001）
2. Neo4j 已启动（默认 bolt://localhost:7687）
3. PostgreSQL 已启动（默认 localhost:5432）
4. 已通过「初始化验证本体」按钮或 API 导入了合同审核模板

## 验证断言清单

### 关1 · 本体边界
- [ ] 本体空间存在（single_contract_ontology）
- [ ] 20+ 对象已导入
- [ ] 23 条关系已导入
- [ ] 8 条硬规则 + 7 条软规则已导入
- [ ] 8 种行为已导入
- [ ] 属性（Property）与对象正确关联

### 关2 · 图穿透
- [ ] Neo4j 中存在 Contract/Clause/CounterParty 等节点
- [ ] 关系边 HAS_CLAUSE/SIGNED_BY_COUNTERPARTY 等存在
- [ ] 从 S-301 出发可达海岳控股 → 王某 → S-900
- [ ] local-graph API 返回正确的节点和边

### 关3 · 规则引擎
- [ ] 规则 MissingMandatoryClauseVeto 存在
- [ ] 规则 BlacklistVeto 存在
- [ ] 行为 Veto/RaiseRiskFinding 等存在
- [ ] 规则与行为之间有 REFERENCES_ACTION 边

### 关4~关6 · Agent 相关
- [ ] 后续阶段，当前验证框架预留接口
