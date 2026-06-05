"""公共工具函数"""

import json
import sys
from typing import Any

import requests

from config import API_BASE


def api_get(path: str, params: dict | None = None) -> dict[str, Any]:
    """GET 请求，返回 JSON data 字段"""
    url = f"{API_BASE}{path}"
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"API error: {body.get('error')}")
    return body.get("data", {})


def api_post(path: str, payload: dict | None = None) -> dict[str, Any]:
    """POST 请求"""
    url = f"{API_BASE}{path}"
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"API error: {body.get('error')}")
    return body.get("data", {})


def pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


class CheckResult:
    """单个检查结果"""
    def __init__(self, name: str, passed: bool, message: str = "", detail: Any = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        mark = "✅ PASS" if self.passed else "❌ FAIL"
        return f"  {mark}  {self.name}{': ' + self.message if self.message else ''}"


class LevelReport:
    """一关的验证报告"""
    def __init__(self, level: int, title: str):
        self.level = level
        self.title = title
        self.checks: list[CheckResult] = []

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def print(self) -> None:
        border = "━" * 60
        status = "✅ 通过" if self.passed() else "❌ 未通过"
        print(f"\n{border}")
        print(f"【关 {self.level}】{self.title}  →  {status}")
        print(f"{border}")
        for c in self.checks:
            print(str(c))
            if c.detail and not c.passed:
                print(f"      详情: {pretty(c.detail)[:300]}")
        if self.passed():
            print(f"  🎉 恭喜，关 {self.level} 闯关成功！")
        else:
            failed = [c.name for c in self.checks if not c.passed]
            print(f"  ⚠️  未通过项: {', '.join(failed)}")


def load_yaml(path: str) -> dict[str, Any]:
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # 回退到项目目录查找
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(project_root, "验证数据集", "本体验证文件包", "ontology.yaml")
        if os.path.exists(full_path):
            import yaml
            with open(full_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        raise


RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_banner() -> None:
    print(f"""
{GREEN}╔══════════════════════════════════════════════════════════════╗
║     传神智谱 · 本体管理模块 · 验证脚本套件 v0.1              ║
║     基于验证数据集六关闯关体系                                ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")
