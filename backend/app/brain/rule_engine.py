"""
规则引擎执行器
给定业务数据（JSON），按照本体中定义的硬规则/软规则进行匹配和推理。

规则条件语法（简化版）：
- 比较：field > 100, field == "xxx", field != null
- 逻辑：AND, OR, NOT
- 函数：in([a,b,c]), contains("xxx"), between(1, 100)
- 字段引用：支持点号路径如 data.contract.amount
"""

from __future__ import annotations

import operator
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models import ElementStatus, OntologyElement


class RuleConditionEvaluator:
    """规则条件求值器"""

    COMPARISON_OPS = {
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.reasoning: list[dict[str, Any]] = []

    def evaluate(self, condition: str) -> tuple[bool, list[dict[str, Any]]]:
        """
        评估条件表达式，返回 (是否命中, 推理步骤)
        """
        self.reasoning = []
        try:
            result = self._eval_expr(condition.strip())
            return result, self.reasoning
        except Exception as e:
            self.reasoning.append({
                "step": "evaluate",
                "condition": condition,
                "error": str(e),
                "result": False,
            })
            return False, self.reasoning

    def _eval_expr(self, expr: str) -> bool:
        """评估表达式（支持 AND/OR/NOT）"""
        expr = expr.strip()

        # 处理括号
        if expr.startswith("(") and expr.endswith(")"):
            inner = expr[1:-1].strip()
            # 确保不是嵌套括号的中间部分
            if inner.count("(") == inner.count(")"):
                return self._eval_expr(inner)

        # NOT
        if expr.upper().startswith("NOT "):
            inner = expr[4:].strip()
            result = not self._eval_expr(inner)
            self.reasoning.append({
                "step": "not",
                "expression": expr,
                "result": result,
            })
            return result

        # OR (优先级最低，最后处理)
        or_parts = self._split_by_logical(expr, " OR ")
        if len(or_parts) > 1:
            results = [self._eval_expr(p) for p in or_parts]
            result = any(results)
            self.reasoning.append({
                "step": "or",
                "parts": or_parts,
                "results": results,
                "result": result,
            })
            return result

        # AND
        and_parts = self._split_by_logical(expr, " AND ")
        if len(and_parts) > 1:
            results = [self._eval_expr(p) for p in and_parts]
            result = all(results)
            self.reasoning.append({
                "step": "and",
                "parts": and_parts,
                "results": results,
                "result": result,
            })
            return result

        # 函数调用：in(), contains(), between()
        if "(" in expr and expr.endswith(")"):
            return self._eval_function(expr)

        # 简单比较
        return self._eval_comparison(expr)

    def _split_by_logical(self, expr: str, op: str) -> list[str]:
        """按逻辑运算符切分，考虑括号嵌套"""
        parts = []
        current = ""
        depth = 0
        i = 0
        op_len = len(op)
        expr_upper = expr.upper()

        while i < len(expr):
            if expr[i] == "(":
                depth += 1
                current += expr[i]
            elif expr[i] == ")":
                depth -= 1
                current += expr[i]
            elif depth == 0 and expr_upper[i:i + op_len] == op.upper():
                parts.append(current.strip())
                current = ""
                i += op_len
                continue
            else:
                current += expr[i]
            i += 1

        if current.strip():
            parts.append(current.strip())

        return parts if len(parts) > 1 else [expr]

    def _eval_function(self, expr: str) -> bool:
        """评估函数调用"""
        match = re.match(r"(\w+)\s*\((.*)\)", expr.strip())
        if not match:
            return self._eval_comparison(expr)

        func_name = match.group(1).lower()
        args_str = match.group(2).strip()
        args = self._parse_args(args_str)

        if func_name == "in":
            field_val = self._get_value(args[0])
            options = [self._parse_literal(a) for a in args[1:]]
            result = field_val in options
            self.reasoning.append({
                "step": "in",
                "field": args[0],
                "value": field_val,
                "options": options,
                "result": result,
            })
            return result

        if func_name == "contains":
            field_val = str(self._get_value(args[0]))
            keyword = str(self._parse_literal(args[1]))
            result = keyword in field_val
            self.reasoning.append({
                "step": "contains",
                "field": args[0],
                "value": field_val,
                "keyword": keyword,
                "result": result,
            })
            return result

        if func_name == "between":
            field_val = self._to_number(self._get_value(args[0]))
            low = self._to_number(self._parse_literal(args[1]))
            high = self._to_number(self._parse_literal(args[2]))
            result = low <= field_val <= high
            self.reasoning.append({
                "step": "between",
                "field": args[0],
                "value": field_val,
                "range": [low, high],
                "result": result,
            })
            return result

        if func_name == "empty":
            field_val = self._get_value(args[0])
            result = field_val is None or field_val == "" or field_val == []
            self.reasoning.append({
                "step": "empty",
                "field": args[0],
                "value": field_val,
                "result": result,
            })
            return result

        if func_name == "has":
            field_val = self._get_value(args[0])
            result = field_val is not None and field_val != "" and field_val != []
            self.reasoning.append({
                "step": "has",
                "field": args[0],
                "value": field_val,
                "result": result,
            })
            return result

        self.reasoning.append({
            "step": "unknown_function",
            "function": func_name,
            "result": False,
        })
        return False

    def _parse_args(self, args_str: str) -> list[str]:
        """解析函数参数，处理引号内逗号"""
        args = []
        current = ""
        in_quote = False
        quote_char = None

        for char in args_str:
            if char in ('"', "'") and not in_quote:
                in_quote = True
                quote_char = char
                current += char
            elif char == quote_char and in_quote:
                in_quote = False
                quote_char = None
                current += char
            elif char == "," and not in_quote:
                args.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            args.append(current.strip())

        return args

    def _eval_comparison(self, expr: str) -> bool:
        """评估简单比较表达式"""
        # 匹配 field op value 或 value op field
        for op_str, op_func in sorted(self.COMPARISON_OPS.items(), key=lambda x: -len(x[0])):
            if op_str in expr:
                parts = expr.split(op_str, 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    left_val = self._get_value(left)
                    right_val = self._parse_literal(right)

                    # 处理 null/None
                    if right_val is None or str(right_val).lower() in ("null", "none"):
                        if op_str == "==":
                            result = left_val is None
                        elif op_str == "!=":
                            result = left_val is not None
                        else:
                            result = False
                    else:
                        # 类型转换
                        left_converted = self._convert_for_compare(left_val, right_val)
                        try:
                            result = op_func(left_converted, right_val)
                        except TypeError:
                            result = False

                    self.reasoning.append({
                        "step": "compare",
                        "field": left,
                        "operator": op_str,
                        "expected": right_val,
                        "actual": left_val,
                        "result": result,
                    })
                    return result

        # 无法解析，当成 truthy 判断
        val = self._get_value(expr)
        result = bool(val)
        self.reasoning.append({
            "step": "truthy",
            "expression": expr,
            "value": val,
            "result": result,
        })
        return result

    def _get_value(self, field_ref: str) -> Any:
        """从数据中获取字段值，支持点号路径"""
        field_ref = field_ref.strip().strip('"').strip("'")

        # 直接字面量
        if field_ref.lower() in ("true", "false", "null", "none"):
            return {"true": True, "false": False, "null": None, "none": None}[field_ref.lower()]
        if field_ref.startswith(("'", '"')) and field_ref.endswith(("'", '"')):
            return field_ref[1:-1]
        try:
            if "." not in field_ref and field_ref.isdigit():
                return int(field_ref)
            if "." not in field_ref:
                float(field_ref)  # 验证是数字
                return float(field_ref)
        except ValueError:
            pass

        # 点号路径取值
        keys = field_ref.split(".")
        current = self.data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            if current is None:
                return None
        return current

    def _parse_literal(self, value_str: str) -> Any:
        """解析字面量"""
        value_str = value_str.strip()
        lower = value_str.lower()

        if lower in ("true",):
            return True
        if lower in ("false",):
            return False
        if lower in ("null", "none"):
            return None
        if value_str.startswith(("'", '"')) and value_str.endswith(("'", '"')):
            return value_str[1:-1]
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str

    def _to_number(self, val: Any) -> float:
        """转换为数字"""
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def _convert_for_compare(self, left: Any, right: Any) -> Any:
        """为比较做类型转换"""
        if left is None:
            return None
        if isinstance(right, (int, float)) and not isinstance(left, (int, float)):
            try:
                return float(left)
            except (ValueError, TypeError):
                pass
        if isinstance(right, str) and not isinstance(left, str):
            return str(left)
        return left


class RuleEngine:
    """规则引擎"""

    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        space_id: str,
        data: dict[str, Any],
        rule_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        执行规则引擎

        Returns:
            {
                "space_id": str,
                "input_data": dict,
                "total_rules": int,
                "hit_count": int,
                "block_count": int,
                "hits": list[RuleHitResult],
                "execution_time_ms": float,
            }
        """
        start_time = time.time()

        # 加载规则
        query = self.db.query(OntologyElement).filter(
            OntologyElement.space_id == space_id,
            OntologyElement.resource_type == "rule",
            OntologyElement.status == ElementStatus.active,
        )
        if rule_ids:
            query = query.filter(OntologyElement.id.in_(rule_ids))

        rules = query.order_by(
            OntologyElement.payload["priority"].desc().nullslast()
        ).all()

        evaluator = RuleConditionEvaluator(data)
        hits = []
        misses = []
        block_count = 0
        all_rules = []

        for rule in rules:
            payload = rule.payload or {}
            condition = payload.get("condition", "") or payload.get("when", "")
            result_text = payload.get("result", "") or payload.get("then", "")
            rule_type = payload.get("rule_type", "硬规则")
            priority = payload.get("priority", 0)

            # 记录所有规则（用于上下文）
            all_rules.append({
                "rule_id": rule.id,
                "rule_code": rule.code,
                "rule_name": rule.name,
                "rule_type": rule_type,
                "priority": priority,
                "condition": condition,
                "result": result_text,
            })

            if not condition:
                continue

            matched, reasoning = evaluator.evaluate(condition)

            if matched:
                severity = "block" if rule_type == "硬规则" else "suggest"
                if severity == "block":
                    block_count += 1

                hits.append({
                    "rule_id": rule.id,
                    "rule_code": rule.code,
                    "rule_name": rule.name,
                    "rule_type": rule_type,
                    "priority": priority,
                    "condition": condition,
                    "matched": True,
                    "result": result_text,
                    "severity": severity,
                    "reasoning": reasoning,
                })
            else:
                misses.append({
                    "rule_id": rule.id,
                    "rule_code": rule.code,
                    "rule_name": rule.name,
                    "rule_type": rule_type,
                    "priority": priority,
                    "condition": condition,
                    "matched": False,
                    "result": result_text,
                    "severity": "block" if rule_type == "硬规则" else "suggest",
                    "reasoning": reasoning,
                })

        execution_time = (time.time() - start_time) * 1000

        return {
            "space_id": space_id,
            "input_data": data,
            "total_rules": len(rules),
            "hit_count": len(hits),
            "block_count": block_count,
            "miss_count": len(misses),
            "hits": hits,
            "misses": misses,
            "all_rules": all_rules,
            "execution_time_ms": round(execution_time, 2),
        }
