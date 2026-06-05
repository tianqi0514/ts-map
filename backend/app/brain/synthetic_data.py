"""
合成数据生成引擎
根据本体对象定义和连接器字段映射，自动生成 Mock 数据。
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.brain.models import ApiConnector, DataMapping
from app.models import OntologyElement


class SyntheticDataGenerator:
    """基于本体定义生成合成数据"""

    # 数据类型 → 生成函数映射
    TYPE_GENERATORS: dict[str, callable] = {}

    def __init__(self, db: Session):
        self.db = db
        self._seed = 42
        random.seed(self._seed)

    def generate_for_connector(self, connector_id: str, count: int = 3) -> list[dict[str, Any]]:
        """为指定连接器生成合成数据"""
        connector = self.db.get(ApiConnector, connector_id)
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        mappings = (
            self.db.query(DataMapping)
            .filter(DataMapping.connector_id == connector_id)
            .all()
        )

        # 按 target_code 分组（一个对象对应多个字段映射）
        by_object: dict[str, list[DataMapping]] = {}
        for m in mappings:
            by_object.setdefault(m.target_code, []).append(m)

        records = []
        for i in range(count):
            record = self._generate_single_record(by_object, i)
            records.append(record)

        return records

    def _generate_single_record(
        self, by_object: dict[str, list[DataMapping]], index: int
    ) -> dict[str, Any]:
        """生成单条记录"""
        record: dict[str, Any] = {}

        for obj_code, mappings in by_object.items():
            obj_data: dict[str, Any] = {}

            for mapping in mappings:
                field_name = mapping.source_field.split(".")[-1]
                value = self._generate_value(mapping.transform, field_name, index)
                obj_data[field_name] = value

            # 用点号路径构建嵌套结构
            self._set_nested(record, obj_code, obj_data)

        return record

    def _generate_value(self, transform: str, field_name: str, index: int) -> Any:
        """根据字段类型生成值"""
        t = transform.lower()

        if t == "string":
            return self._gen_string(field_name, index)
        if t == "int" or t == "integer":
            return self._gen_int(field_name, index)
        if t == "float":
            return self._gen_float(field_name, index)
        if t == "money" or t == "decimal":
            return self._gen_money(field_name, index)
        if t == "date":
            return self._gen_date(field_name, index)
        if t == "datetime":
            return self._gen_datetime(field_name, index)
        if t == "bool" or t == "boolean":
            return self._gen_bool(field_name, index)
        if t.startswith("enum"):
            return self._gen_enum(t, field_name, index)
        if t == "ref" or t == "reference":
            return self._gen_ref(field_name, index)

        # 根据字段名启发式推断
        return self._infer_by_name(field_name, index)

    def _gen_string(self, field_name: str, index: int) -> str:
        if "name" in field_name or "title" in field_name:
            names = ["张三", "李四", "王五", "赵六", "陈七", "刘八", "周九", "吴十"]
            return f"{random.choice(names)}-{index + 1}"
        if "code" in field_name or "no" in field_name or "id" in field_name:
            prefix = field_name[:3].upper()
            return f"{prefix}-{datetime.now().year}-{index + 1001:04d}"
        if "type" in field_name:
            types = ["A类", "B类", "C类", "标准型", "定制型"]
            return random.choice(types)
        if "status" in field_name:
            statuses = ["草稿", "审批中", "已生效", "已归档", "已终止"]
            return random.choice(statuses)
        if "address" in field_name:
            cities = ["北京", "上海", "广州", "深圳", "杭州", "成都"]
            return f"{random.choice(cities)}市{random.randint(1, 20)}区{random.randint(1, 999)}号"
        if "email" in field_name:
            domains = ["example.com", "corp.cn", "group.com"]
            return f"user{index}@{random.choice(domains)}"
        if "phone" in field_name:
            return f"1{random.choice([3,5,7,8,9])}{random.randint(100000000, 999999999)}"
        return f"sample-{field_name}-{index}"

    def _gen_int(self, field_name: str, index: int) -> int:
        if "score" in field_name or "rating" in field_name:
            return random.randint(60, 100)
        if "age" in field_name:
            return random.randint(22, 60)
        if "count" in field_name or "qty" in field_name or "quantity" in field_name:
            return random.randint(1, 1000)
        if "year" in field_name:
            return datetime.now().year
        if "day" in field_name or "days" in field_name:
            return random.randint(1, 90)
        return random.randint(1000, 999999)

    def _gen_float(self, field_name: str, index: int) -> float:
        if "ratio" in field_name or "rate" in field_name:
            return round(random.uniform(0.01, 0.99), 4)
        return round(random.uniform(1.0, 1000.0), 2)

    def _gen_money(self, field_name: str, index: int) -> float:
        return round(random.uniform(10000, 10000000), 2)

    def _gen_date(self, field_name: str, index: int) -> str:
        days = random.randint(-365, 365)
        d = datetime.now() + timedelta(days=days)
        return d.strftime("%Y-%m-%d")

    def _gen_datetime(self, field_name: str, index: int) -> str:
        days = random.randint(-365, 365)
        hours = random.randint(0, 23)
        d = datetime.now() + timedelta(days=days, hours=hours)
        return d.strftime("%Y-%m-%d %H:%M:%S")

    def _gen_bool(self, field_name: str, index: int) -> bool:
        # 某些字段偏向 true
        if "is" in field_name.lower():
            return random.random() > 0.3
        return random.choice([True, False])

    def _gen_enum(self, transform: str, field_name: str, index: int) -> str:
        # enum[val1,val2,val3]
        try:
            inner = transform[5:-1]  # 去掉 enum[ 和 ]
            values = [v.strip() for v in inner.split(",")]
            return random.choice(values) if values else "unknown"
        except Exception:
            return "unknown"

    def _gen_ref(self, field_name: str, index: int) -> str:
        prefix = field_name[:3].upper()
        return f"{prefix}-{random.randint(1000, 9999)}"

    def _infer_by_name(self, field_name: str, index: int) -> Any:
        """根据字段名推断类型"""
        fn = field_name.lower()
        if any(k in fn for k in ["amount", "price", "cost", "fee", "sum", "total"]):
            return self._gen_money(field_name, index)
        if any(k in fn for k in ["date", "time", "at"]):
            return self._gen_date(field_name, index)
        if any(k in fn for k in ["count", "num", "qty", "quantity", "score", "age", "year"]):
            return self._gen_int(field_name, index)
        if any(k in fn for k in ["ratio", "rate", "percent"]):
            return self._gen_float(field_name, index)
        if any(k in fn for k in ["is", "has", "flag", "enable"]):
            return self._gen_bool(field_name, index)
        return self._gen_string(field_name, index)

    @staticmethod
    def _set_nested(record: dict, path: str, value: Any) -> None:
        """按点号路径设置嵌套字典值"""
        keys = path.split(".")
        current = record
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


def generate_preview(
    db: Session, connector_id: str, count: int = 3
) -> dict[str, Any]:
    """生成合成数据预览"""
    generator = SyntheticDataGenerator(db)
    connector = db.get(ApiConnector, connector_id)
    if not connector:
        raise ValueError(f"Connector {connector_id} not found")

    records = generator.generate_for_connector(connector_id, count)

    # 统计映射信息
    mappings = (
        db.query(DataMapping)
        .filter(DataMapping.connector_id == connector_id)
        .all()
    )

    mapping_summary = {
        "total_fields": len(mappings),
        "by_type": {},
        "by_object": {},
    }
    for m in mappings:
        mapping_summary["by_type"].setdefault(m.transform, 0)
        mapping_summary["by_type"][m.transform] += 1
        mapping_summary["by_object"].setdefault(m.target_code, 0)
        mapping_summary["by_object"][m.target_code] += 1

    return {
        "connector_id": connector_id,
        "connector_name": connector.name,
        "records": records,
        "mapping_summary": mapping_summary,
    }
