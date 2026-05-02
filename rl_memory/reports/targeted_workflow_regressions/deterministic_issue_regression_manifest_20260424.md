# Deterministic Issue Regression Manifest (2026-04-24)

- source_batch: `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20`

## track_orders_executor_compat

Goals that invoke BIND_B4_TRACK_ORDERS and should be revalidated after TRACK_ORDER/:has-text executor fixes.

- total_goals: `530`
- test: `10` goals
- goal_ids_file: `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/track_orders_executor_compat.test.goal_ids.txt`
- train: `520` goals
- goal_ids_file: `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/track_orders_executor_compat.train.goal_ids.txt`

## insurance_policy_param_drift

Goals whose BIND_G2_INSURANCE_POLICY invocation drifted away from the fixed Prime Shield task defaults.

- total_goals: `0`

## insurance_policy_param_drift_pre_repair

Pre-repair snapshot of train goals whose BIND_G2_INSURANCE_POLICY invocation parameters drifted away from the fixed Prime Shield defaults before the deterministic repair on 2026-04-24.

- total_goals: `30`
- train: `30` goals
- goal_ids_file: `/Users/masteryth/Documents/webagent/rl_memory/reports/targeted_workflow_regressions/insurance_policy_param_drift_pre_repair.train.goal_ids.txt`
