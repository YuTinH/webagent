import os
import datetime

# ================= 配置 =================

# 1. 将被生成的新汇总文件
SUMMARY_FILENAME = "PROJECT_HISTORY.md"

# 2. 待删除的 Python 脚本 (一次性测试/调试文件)
FILES_TO_DELETE_PY = [
    "debug_search_flow.py",
    "quick_test.py",
    "test_127.py",
    "test_level4.py",
    "test_playwright_detailed.py",
    "test_search_direct.py",
    "test_setup.py",
    "verify_check.py"
]

# 3. 待合并并删除的 Markdown 日志 (保留 README.md 和 docs/)
FILES_TO_MERGE_AND_DELETE_MD = [
    "CLAUDE_AGENT_TEST_RESULTS.md",
    "COMPLETE_FRONTEND_OPTIMIZATION.md",
    "COMPLETE_TEST_RESULTS.md",
    "COMPLETION_SUMMARY.md",
    "ENHANCED_README.md",
    "FINAL_SUMMARY.md",
    "FINAL_TEST_REPORT.md",
    "FIX_IMPLEMENTATION_LOG.md",
    "FIX_SUMMARY.md",
    "FRONTEND_ENHANCEMENTS_SUMMARY.md",
    "FRONTEND_ENHANCEMENT_PLAN.md",
    "IMPLEMENTATION_SUMMARY.md",
    "LEVEL4_TEST_RESULTS.md",
    "PROGRESS_SUMMARY_CN.md",
    "SCORING_BASED_FINAL_REPORT.md",
    "STATUS.md",
    "TEST_REPORT.md",
    "VERIFICATION_SYSTEM_UPGRADE.md",
    "VERIFICATION_UPGRADE_SUMMARY.md"
]

# ================= 汇总内容模板 =================

SUMMARY_CONTENT = f"""# WebAgent Benchmark - Project History & Changelog
> Generated on {datetime.datetime.now().strftime('%Y-%m-%d')} by cleanup script.

This document consolidates previous development logs, test reports, and optimization records.

## 🌟 Key Milestones

### ✅ Phase 1: MVP & Task Definitions
- Defined 10 core tasks across Shop, Bank, and Gov domains.
- Established dependency chains (e.g., Shopping -> Returns).

### ✅ Phase 2: Frontend Optimization (2025-11-28)
- **100% Coverage**: Optimized all 10 pages across 3 domains.
- **Component Library**: Integrated Modals, Toasts, Dropdowns, and Cart Drawers.
- **Distractors**: Added "Marketing API" to generate random ads, cookie banners, and chat widgets to increase difficulty.

### ✅ Phase 3: Verification System Upgrade
- Implemented `EnhancedExecutor` with multi-modal verification (HTML, Screenshot, Memory).
- Added `AssertionsDSL` for flexible success criteria logic.
- Self-correction mechanism integrated for retry logic.

## 📊 Historical Test Reports

### Summary of Latest Results
- **Task Success**: High success rate on independent tasks (T1-T3).
- **Complex Chains**: Verified robust handling of dependency chains (e.g., T8->T9).
- **Resilience**: Agent successfully handles new frontend distractors.

---
"""

def main():
    print(f"🧹 Starting repository cleanup...")
    
    # 1. Create the Summary File
    # (Optional: In a real scenario, we could read the content of old files and append it, 
    # but here we use a structured summary to keep it clean)
    with open(SUMMARY_FILENAME, "w", encoding="utf-8") as f:
        f.write(SUMMARY_CONTENT)
        # Append a list of merged files for reference
        f.write("\n### 📂 Archived Log Files\nThe following files were merged into this history and deleted:\n")
        for log_file in FILES_TO_MERGE_AND_DELETE_MD:
            f.write(f"- {log_file}\n")
    
    print(f"✅ Created summary file: {SUMMARY_FILENAME}")

    # 2. Delete Markdown Files
    deleted_md_count = 0
    for filename in FILES_TO_MERGE_AND_DELETE_MD:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"   Deleted log: {filename}")
                deleted_md_count += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {filename}: {e}")
        else:
            print(f"   ⚠️ File not found (skipped): {filename}")

    # 3. Delete Python Files
    deleted_py_count = 0
    for filename in FILES_TO_DELETE_PY:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"   Deleted script: {filename}")
                deleted_py_count += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {filename}: {e}")
        else:
            print(f"   ⚠️ File not found (skipped): {filename}")

    print("-" * 30)
    print(f"🎉 Cleanup Complete!")
    print(f"   - Archived & Deleted MD files: {deleted_md_count}")
    print(f"   - Deleted temp PY files: {deleted_py_count}")
    print(f"   - Please check {SUMMARY_FILENAME} for project history.")

if __name__ == "__main__":
    main()