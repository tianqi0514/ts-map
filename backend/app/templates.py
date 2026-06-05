from pathlib import Path
from typing import Any

import yaml

from app.models import ElementType, EdgeType


def load_contract_template() -> dict[str, Any]:
    dataset_path = (
        Path(__file__).resolve().parents[2]
        / "验证数据集"
        / "本体验证文件包"
        / "ontology.yaml"
    )
    if dataset_path.exists():
        with dataset_path.open("r", encoding="utf-8") as file:
            source = yaml.safe_load(file)["ontology"]
        return build_template_from_ontology(source)
    return fallback_template()


def build_template_from_ontology(source: dict[str, Any]) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    edges: list[tuple[str, EdgeType, str]] = []

    for code, spec in source.get("objects", {}).items():
        label = spec.get("label", code)
        fields = spec.get("fields", {})
        elements.append(
            {
                "resource_type": ElementType.object,
                "code": code,
                "name": label,
                "description": f"{label}对象，业务主键为 {spec.get('key', '-')}",
                "payload": {
                    "key": spec.get("key"),
                    "fields": fields,
                    "source": "验证数据集/ontology.yaml",
                },
            }
        )
        for field_name, field_type in fields.items():
            property_code = f"{code}.{field_name}"
            elements.append(
                {
                    "resource_type": ElementType.property,
                    "code": property_code,
                    "name": field_name,
                    "description": f"{label}.{field_name}",
                    "payload": {
                        "object_code": code,
                        "data_type": str(field_type),
                    },
                }
            )
            edges.append((code, EdgeType.has_property, property_code))

    for link in source.get("links", []):
        code = link["name"]
        from_code = link["from"]
        to_value = link["to"]
        to_codes = to_value if isinstance(to_value, list) else [to_value]
        elements.append(
            {
                "resource_type": ElementType.relation,
                "code": code,
                "name": link.get("label", code),
                "description": f"{link.get('label', code)}: {from_code} -> {', '.join(to_codes)}",
                "payload": {
                    "source_code": from_code,
                    "target_codes": to_codes,
                    "cardinality": link.get("card"),
                    "traversable": link.get("traversable", False),
                },
            }
        )
        edges.append((code, EdgeType.relates_from, from_code))
        for to_code in to_codes:
            edges.append((code, EdgeType.relates_to, to_code))

    behavior_codes = set()
    for behavior in source.get("behaviors", []):
        code = behavior["id"]
        behavior_codes.add(code)
        elements.append(
            {
                "resource_type": ElementType.action,
                "code": code,
                "name": behavior.get("label", code),
                "description": behavior.get("effect", ""),
                "payload": {
                    "hook": behavior.get("hook"),
                    "effect": behavior.get("effect"),
                    "rules": [],
                },
            }
        )

    for rule_type in ("hard", "soft"):
        for rule in source.get("rules", {}).get(rule_type, []):
            code = rule["id"]
            actions = extract_actions(rule.get("then"))
            elements.append(
                {
                    "resource_type": ElementType.rule,
                    "code": code,
                    "name": rule.get("label", code),
                    "description": f"{rule.get('when', '')} -> {rule.get('then', '')}",
                    "payload": {
                        "rule_type": "硬规则" if rule_type == "hard" else "软规则",
                        "priority": rule.get("priority"),
                        "condition": rule.get("when"),
                        "result": rule.get("then"),
                        "actions": actions,
                        "needs": rule.get("needs"),
                    },
                }
            )
            for action_code in actions:
                if action_code in behavior_codes:
                    edges.append((code, EdgeType.references_action, action_code))

    for constraint in source.get("constraints", []):
        code = f"Constraint.{constraint['id']}"
        elements.append(
            {
                "resource_type": ElementType.rule,
                "code": code,
                "name": constraint["id"],
                "description": constraint.get("expr", ""),
                "payload": {
                    "rule_type": "约束",
                    "condition": constraint.get("expr"),
                    "kind": constraint.get("kind"),
                    "weight": constraint.get("weight"),
                    "actions": [],
                },
            }
        )

    return {
        "space": {
            "code": "single_contract_ontology",
            "name": "单合同审核本体",
            "domain": source.get("domain", "单合同合同审核"),
            "template_code": "validation_single_contract",
            "description": "基于验证数据集 ontology.yaml 初始化的本体资产，包含对象、关系、行为、规则和约束。",
        },
        "elements": elements,
        "edges": edges,
    }


def extract_actions(value: Any) -> list[str]:
    text = str(value)
    actions = [
        "Veto",
        "RaiseRiskFinding",
        "RequireApproval",
        "RequireHumanReview",
        "ProposeAmendment",
        "BlockEffectiveness",
        "Notify",
        "RecordDecision",
    ]
    return [action for action in actions if action in text]


def fallback_template() -> dict[str, Any]:
    return {
        "space": {
            "code": "single_contract_ontology",
            "name": "单合同审核本体",
            "domain": "contract_review",
            "template_code": "fallback",
            "description": "合同审核本体模板。",
        },
        "elements": [],
        "edges": [],
    }


CONTRACT_TEMPLATE = load_contract_template()
