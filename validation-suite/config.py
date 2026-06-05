"""验证脚本配置 —— 按需修改连接参数"""

import os

# ── 后端 API ──
API_BASE = os.environ.get("API_BASE", "http://localhost:9000")

# ── Neo4j ──
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:9004")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")

# ── PostgreSQL ──
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "9002"))
PG_DB = os.environ.get("PG_DB", "zhishen")
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "postgres")

# ── 验证阈值 ──
EXPECTED_OBJECT_COUNT = 20      # 期望对象数
EXPECTED_RELATION_COUNT = 23    # 期望关系数
EXPECTED_RULE_COUNT = 15        # 期望规则数 (8硬+7软)
EXPECTED_ACTION_COUNT = 8       # 期望行为数
EXPECTED_PROPERTY_COUNT = 50    # 期望属性数（对象字段总数）

# 验证数据集核心断言
EXPECTED_CONTRACTS = ["C-2024-001", "C-2024-005", "C-2024-006", "C-2024-007"]
EXPECTED_COUNTERPARTIES = ["S-301", "S-900"]  # S-301 干净但被穿透；S-900 黑名单
