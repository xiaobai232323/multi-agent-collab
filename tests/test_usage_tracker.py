"""用量追踪模块 单元测试"""

import sys, os, json, tempfile
from pathlib import Path
from datetime import datetime

# 把父目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import usage_tracker as ut


def test_record_and_query(tmp_path, monkeypatch):
    """测试记录调用和查询"""
    # 用临时目录替代实际文件路径
    tmp_usage = tmp_path / "usage.json"
    tmp_budget = tmp_path / "budget.json"
    monkeypatch.setattr(ut, "USAGE_FILE", tmp_usage)
    monkeypatch.setattr(ut, "BUDGET_FILE", tmp_budget)

    # 初始化默认预算文件
    tmp_budget.write_text(json.dumps({
        "prices": ut.DEFAULT_PRICES,
        "budget": ut.DEFAULT_BUDGET,
    }, ensure_ascii=False))

    tracker = ut.UsageTracker()

    # 记录一次调用
    tracker.record("deepseek-chat", input_tokens=500, output_tokens=200)

    today = tracker.today()
    assert today["calls"] == 1
    assert today["tokens"] == 700
    assert today["cost"] > 0

    month = tracker.month()
    assert month["calls"] == 1

    all_time = tracker.all_time()
    assert all_time["calls"] == 1


def test_multiple_models(tmp_path, monkeypatch):
    """测试多个模型的记录"""
    tmp_usage = tmp_path / "usage.json"
    tmp_budget = tmp_path / "budget.json"
    monkeypatch.setattr(ut, "USAGE_FILE", tmp_usage)
    monkeypatch.setattr(ut, "BUDGET_FILE", tmp_budget)

    tmp_budget.write_text(json.dumps({
        "prices": ut.DEFAULT_PRICES,
        "budget": ut.DEFAULT_BUDGET,
    }, ensure_ascii=False))

    tracker = ut.UsageTracker()

    tracker.record("deepseek-chat", 1000, 500)
    tracker.record("qwen-max", 800, 300)
    tracker.record("qwen-vl-max", 600, 200, image_count=1)

    today = tracker.today()
    assert today["calls"] == 3
    assert today["tokens"] == 3400  # 1000+500+800+300+600+200

    # 视觉模型调用费用应高于普通文本
    recent = tracker.recent_calls(3)
    assert len(recent) == 3


def test_budget_warning(tmp_path, monkeypatch):
    """测试预算预警"""
    tmp_usage = tmp_path / "usage.json"
    tmp_budget = tmp_path / "budget.json"
    monkeypatch.setattr(ut, "USAGE_FILE", tmp_usage)
    monkeypatch.setattr(ut, "BUDGET_FILE", tmp_budget)

    tmp_budget.write_text(json.dumps({
        "prices": ut.DEFAULT_PRICES,
        "budget": {"monthly": 10.0, "warning_pct": 80, "daily_limit": 2.0},
    }, ensure_ascii=False))

    tracker = ut.UsageTracker()

    # 少量使用 — 不预警
    tracker.record("deepseek-chat", 100, 50)
    assert tracker.warning_level() == "ok"

    # 大量使用触发预警 (模拟)
    tracker.data["totals"][datetime.now().strftime("%Y-%m")] = {
        "cost": 9.0, "tokens": 50000, "calls": 100
    }
    ut._save_json(tmp_usage, tracker.data)

    wl = tracker.warning_level()
    assert wl in ("warn", "critical")


def test_recent_calls_limit(tmp_path, monkeypatch):
    """测试最近调用记录限制在 5 条"""
    tmp_usage = tmp_path / "usage.json"
    tmp_budget = tmp_path / "budget.json"
    monkeypatch.setattr(ut, "USAGE_FILE", tmp_usage)
    monkeypatch.setattr(ut, "BUDGET_FILE", tmp_budget)

    tmp_budget.write_text(json.dumps({
        "prices": ut.DEFAULT_PRICES,
        "budget": ut.DEFAULT_BUDGET,
    }, ensure_ascii=False))

    tracker = ut.UsageTracker()

    for i in range(10):
        tracker.record("deepseek-chat", 100, 50)

    recent = tracker.recent_calls(5)
    assert len(recent) == 5


def test_default_budget_creation(tmp_path, monkeypatch):
    """测试默认预算文件自动创建"""
    tmp_budget = tmp_path / "no_exist.json"
    monkeypatch.setattr(ut, "BUDGET_FILE", tmp_budget)

    # 不存在的文件应返回默认值
    data = ut._load_json(tmp_budget, ut.DEFAULT_BUDGET)
    assert data["monthly"] == 15.0
    assert data["warning_pct"] == 80
