#!/usr/bin/env python3
"""
WebAgent Benchmark 任务评分计算器

根据TASK_SCORING_SYSTEM.md中定义的评分标准,
自动计算Agent在各个任务上的得分。

Usage:
    python calculate_score.py
    python calculate_score.py --results output/
    python calculate_score.py --task B1-shopping --completed 15 --total 22
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


# 任务评分定义 (总分100分/任务)
TASK_SCORES = {
    "B1-shopping": {
        "total_steps": 22,
        "step_scores": [2, 2, 3, 3, 2, 4, 5, 4, 2, 5, 2, 7, 4, 5, 2, 8, 2, 5, 4, 8, 2, 7],
        "complexity": "极难",
        "weight": 3.0
    },
    "B5-track-orders": {
        "total_steps": 5,
        "step_scores": [15, 15, 30, 15, 25],
        "complexity": "简单",
        "weight": 1.5
    },
    "C2-return": {
        "total_steps": 3,
        "step_scores": [30, 30, 40],
        "complexity": "非常简单",
        "weight": 1.0
    },
    "D1-check-balance": {
        "total_steps": 11,
        "step_scores": [5, 5, 10, 10, 12, 8, 10, 15, 8, 12, 5],
        "complexity": "困难",
        "weight": 2.0
    },
    "D3-autopay": {
        "total_steps": 3,
        "step_scores": [30, 35, 35],
        "complexity": "非常简单",
        "weight": 1.0
    },
    "D4-card-replacement": {
        "total_steps": 3,
        "step_scores": [30, 35, 35],
        "complexity": "非常简单",
        "weight": 1.0
    },
    "H1-check-bill": {
        "total_steps": 3,
        "step_scores": [30, 35, 35],
        "complexity": "非常简单",
        "weight": 1.0
    },
    "H2-permit-app": {
        "total_steps": 8,
        "step_scores": [5, 5, 10, 10, 25, 25, 15, 5],
        "complexity": "极难",
        "weight": 3.0
    },
    "K2-aa-split": {
        "total_steps": 3,
        "step_scores": [30, 35, 35],
        "complexity": "非常简单",
        "weight": 1.0
    },
    "M1-lost-card-crisis": {
        "total_steps": 3,
        "step_scores": [30, 35, 35],
        "complexity": "非常简单",
        "weight": 1.0
    }
}


def calculate_task_score(task_id: str, completed_steps: int) -> Tuple[int, int]:
    """
    计算单个任务的得分

    Args:
        task_id: 任务ID
        completed_steps: 完成的步骤数

    Returns:
        (获得分数, 总分)
    """
    if task_id not in TASK_SCORES:
        raise ValueError(f"Unknown task: {task_id}")

    task_info = TASK_SCORES[task_id]
    step_scores = task_info["step_scores"]

    # 计算完成步骤的累计得分
    earned_score = sum(step_scores[:completed_steps])
    total_score = sum(step_scores)

    return earned_score, total_score


def calculate_overall_score(results: Dict[str, int]) -> Dict:
    """
    计算总体得分

    Args:
        results: {task_id: completed_steps}

    Returns:
        详细得分信息
    """
    total_earned = 0
    total_possible = 0
    weighted_earned = 0
    weighted_possible = 0

    task_details = []

    for task_id, completed_steps in results.items():
        earned, total = calculate_task_score(task_id, completed_steps)
        task_info = TASK_SCORES[task_id]
        weight = task_info["weight"]

        total_earned += earned
        total_possible += total
        weighted_earned += earned * weight
        weighted_possible += total * weight

        task_details.append({
            "task_id": task_id,
            "completed_steps": f"{completed_steps}/{task_info['total_steps']}",
            "score": earned,
            "total": total,
            "percentage": (earned / total * 100) if total > 0 else 0,
            "complexity": task_info["complexity"],
            "weight": weight
        })

    return {
        "total_score": total_earned,
        "total_possible": total_possible,
        "percentage": (total_earned / total_possible * 100) if total_possible > 0 else 0,
        "weighted_score": weighted_earned,
        "weighted_possible": weighted_possible,
        "weighted_percentage": (weighted_earned / weighted_possible * 100) if weighted_possible > 0 else 0,
        "tasks": task_details
    }


def print_score_report(scores: Dict):
    """打印得分报告"""
    print("=" * 80)
    print("🎯 WebAgent Benchmark 评分报告")
    print("=" * 80)
    print()

    # 任务详情
    print("📊 任务得分明细:")
    print()
    print(f"{'任务ID':<25} {'步骤':<12} {'得分':<12} {'完成率':<10} {'复杂度':<10}")
    print("-" * 80)

    for task in scores["tasks"]:
        percentage = f"{task['percentage']:.1f}%"
        score_str = f"{task['score']}/{task['total']}"
        print(f"{task['task_id']:<25} {task['completed_steps']:<12} {score_str:<12} {percentage:<10} {task['complexity']:<10}")

    print()
    print("=" * 80)
    print("📈 总体统计:")
    print("=" * 80)
    print()
    print(f"原始得分:   {scores['total_score']}/{scores['total_possible']} ({scores['percentage']:.1f}%)")
    print(f"加权得分:   {scores['weighted_score']:.1f}/{scores['weighted_possible']:.1f} ({scores['weighted_percentage']:.1f}%)")
    print()

    # 评级
    percentage = scores['weighted_percentage']
    if percentage >= 90:
        grade = "🏆 卓越 (A+)"
    elif percentage >= 80:
        grade = "⭐ 优秀 (A)"
    elif percentage >= 70:
        grade = "✅ 良好 (B)"
    elif percentage >= 60:
        grade = "📝 及格 (C)"
    else:
        grade = "❌ 不及格 (D)"

    print(f"综合评级:   {grade}")
    print()

    # 任务分类统计
    complexity_stats = {}
    for task in scores["tasks"]:
        comp = task["complexity"]
        if comp not in complexity_stats:
            complexity_stats[comp] = {"earned": 0, "total": 0, "count": 0}
        complexity_stats[comp]["earned"] += task["score"]
        complexity_stats[comp]["total"] += task["total"]
        complexity_stats[comp]["count"] += 1

    print("📊 按复杂度分类:")
    print()
    for comp, stats in sorted(complexity_stats.items(), key=lambda x: {"极难": 5, "困难": 4, "中等": 3, "简单": 2, "非常简单": 1}.get(x[0], 0), reverse=True):
        perc = (stats["earned"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {comp:8} ({stats['count']}个任务): {stats['earned']:4}/{stats['total']:4} ({perc:.1f}%)")

    print()
    print("=" * 80)


def load_results_from_output(output_dir: Path) -> Dict[str, int]:
    """从output目录加载测试结果"""
    results = {}

    for task_dir in output_dir.iterdir():
        if task_dir.is_dir():
            result_file = task_dir / "result.json"
            if result_file.exists():
                with open(result_file) as f:
                    data = json.load(f)
                    task_id = task_dir.name
                    completed_steps = data.get("steps_completed", 0)
                    results[task_id] = completed_steps

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Calculate WebAgent task scores')
    parser.add_argument('--results', type=str, help='Path to results directory')
    parser.add_argument('--task', type=str, help='Single task to score')
    parser.add_argument('--completed', type=int, help='Completed steps for single task')
    parser.add_argument('--total', type=int, help='Total steps for single task (for verification)')

    args = parser.parse_args()

    if args.task:
        # 单个任务评分
        if args.completed is None:
            parser.error("--completed is required when using --task")

        earned, total = calculate_task_score(args.task, args.completed)

        print()
        print(f"任务: {args.task}")
        print(f"完成步骤: {args.completed}/{TASK_SCORES[args.task]['total_steps']}")
        print(f"得分: {earned}/{total} ({earned/total*100:.1f}%)")
        print(f"复杂度: {TASK_SCORES[args.task]['complexity']}")
        print()

    elif args.results:
        # 从结果目录加载
        output_dir = Path(args.results)
        if not output_dir.exists():
            print(f"Error: Directory not found: {output_dir}")
            return

        results = load_results_from_output(output_dir)
        scores = calculate_overall_score(results)
        print_score_report(scores)

    else:
        # 使用Claude Sonnet 4.5的测试结果
        claude_results = {
            "B1-shopping": 15,
            "B5-track-orders": 5,
            "C2-return": 3,
            "D1-check-balance": 8,
            "D3-autopay": 1,
            "D4-card-replacement": 3,
            "H1-check-bill": 1,
            "H2-permit-app": 8,
            "K2-aa-split": 1,
            "M1-lost-card-crisis": 1
        }

        print()
        print("📊 使用Claude Sonnet 4.5的测试结果计算得分...")
        print()

        scores = calculate_overall_score(claude_results)
        print_score_report(scores)


if __name__ == "__main__":
    main()
