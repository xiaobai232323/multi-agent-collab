"""API 用量追踪 + 预算预警"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

BASE = Path(__file__).parent
USAGE_FILE = BASE / "usage.json"
BUDGET_FILE = BASE / "budget.json"

# 默认价格 (人民币/百万tokens)
DEFAULT_PRICES = {
    "deepseek-chat":     {"input": 1.0, "output": 2.0},
    "deepseek-reasoner": {"input": 4.0, "output": 16.0},
    "qwen-max":          {"input": 20.0, "output": 60.0},
    "qwen-vl-max":       {"input": 20.0, "output": 60.0, "per_image": 0.003},  # 视觉模型
}

# 默认预算 (元)
DEFAULT_BUDGET = {
    "monthly": 15.0,      # 月预算
    "warning_pct": 80,    # 80% 时预警
    "daily_limit": 2.0,   # 单日上限
}


def _load_json(path, default):
    if path.exists():
        return json.loads(path.read_text("utf-8"))
    return default


def _save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(path)  # 原子替换，防止并发写损坏


class UsageTracker:
    """用量追踪器 — 单例"""

    def __init__(self):
        self.data = _load_json(USAGE_FILE, {"calls": [], "totals": {}})
        self.prices = _load_json(BUDGET_FILE, {"prices": DEFAULT_PRICES, "budget": DEFAULT_BUDGET})
        # 确保默认价格存在
        for k, v in DEFAULT_PRICES.items():
            if k not in self.prices["prices"]:
                self.prices["prices"][k] = v

    # ── 记录 ──

    def record(self, model: str, input_tokens: int, output_tokens: int, image_count: int = 0):
        """记录一次 API 调用"""
        price = self.prices["prices"].get(model, {"input": 1.0, "output": 2.0})
        input_cost = (input_tokens / 1_000_000) * price["input"]
        output_cost = (output_tokens / 1_000_000) * price["output"]
        image_cost = image_count * price.get("per_image", 0)
        total_cost = input_cost + output_cost + image_cost

        call = {
            "time": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "image_count": image_count,
            "cost": round(total_cost, 6),
        }
        self.data["calls"].append(call)

        # 更新汇总
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        for key in [today, month, "all"]:
            if key not in self.data["totals"]:
                self.data["totals"][key] = {"cost": 0, "tokens": 0, "calls": 0}
            self.data["totals"][key]["cost"] += total_cost
            self.data["totals"][key]["tokens"] += input_tokens + output_tokens
            self.data["totals"][key]["calls"] += 1

        # 只保留最近 90 天详细记录
        cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        self.data["calls"] = [c for c in self.data["calls"] if c["time"] >= cutoff]

        _save_json(USAGE_FILE, self.data)

    # ── 查询 ──

    def today(self) -> dict:
        key = datetime.now().strftime("%Y-%m-%d")
        return self.data["totals"].get(key, {"cost": 0, "tokens": 0, "calls": 0})

    def month(self) -> dict:
        key = datetime.now().strftime("%Y-%m")
        return self.data["totals"].get(key, {"cost": 0, "tokens": 0, "calls": 0})

    def all_time(self) -> dict:
        return self.data["totals"].get("all", {"cost": 0, "tokens": 0, "calls": 0})

    def recent_calls(self, n=10) -> list:
        return self.data["calls"][-n:][::-1]

    # ── 预算 ──

    def budget(self) -> dict:
        return self.prices.get("budget", DEFAULT_BUDGET)

    def warning_level(self) -> str:
        """返回预警等级: ok/warn/critical"""
        b = self.budget()
        monthly_cost = self.month()["cost"]
        pct = (monthly_cost / b["monthly"]) * 100 if b["monthly"] > 0 else 0

        if b.get("daily_limit", 0) > 0 and self.today()["cost"] >= b["daily_limit"]:
            return "critical"
        if pct >= 95:
            return "critical"
        if pct >= b.get("warning_pct", 80):
            return "warn"
        return "ok"

    def budget_summary(self) -> str:
        """一句话预算摘要"""
        b = self.budget()
        mt = self.month()
        td = self.today()
        pct = (mt["cost"] / b["monthly"] * 100) if b["monthly"] > 0 else 0
        return (
            f"本月 ¥{mt['cost']:.2f} / ¥{b['monthly']:.0f} ({pct:.0f}%)  |  "
            f"今日 ¥{td['cost']:.3f}  |  "
            f"累计 {self.all_time()['calls']} 次调用"
        )


# 全局单例
tracker = UsageTracker()
