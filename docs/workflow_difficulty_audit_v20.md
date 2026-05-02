# Workflow Difficulty Audit

- batch_root: `/Users/masteryth/Documents/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20`
- blueprints_file: `/Users/masteryth/Documents/webagent/tasks/workflow_generation_blueprints.json`
- blueprint_count: 504
- goal_count: 5040

## Blueprint-Level Stats
- difficulty_counts: {2: 1, 3: 76, 4: 159, 5: 268}
- mean_path_count_per_blueprint: 1.8552
- mean_step_length_per_blueprint_path: 3.1572

## Global Goal-Level Stats
- shortest_path_len.mean: 3.1766
- shortest_path_len.median: 3.0
- num_success_paths.mean: 1.8552
- target_state_size.mean: 2.8135
- visible_constraint_count.mean: 3.6964
- counterfactual_axis_count.mean: 4.0238
- max_steps.mean: 44.2024
- max_module_invocations.mean: 3.6647
- step_budget_ratio_vs_shortest_path.mean: 14.1015
- module_budget_slack.mean: 0.4881

## Saturation-Risk Indicators
- share_shortest_path_le_2: 0.316
- share_target_size_le_2: 0.546
- share_success_paths_le_2: 0.996
- share_step_budget_ratio_ge_15: 0.559
- share_module_budget_slack_le_1: 0.917
- saturation_risk_score_counts: {2: 330, 3: 3100, 4: 1210, 5: 400}

## Split Stats
### dev
- goals: 140
- difficulty_counts: {3: 30, 4: 30, 5: 80}
- shortest_path_len.mean: 3.5714
- num_success_paths.mean: 1.7143
- target_state_size.mean: 2.8571
- max_steps.mean: 46.6429
- step_budget_ratio_vs_shortest_path.mean: 13.4643
- share_shortest_path_le_2: 0.214
- share_target_size_le_2: 0.571
- share_step_budget_ratio_ge_15: 0.500

### test
- goals: 140
- difficulty_counts: {3: 10, 4: 20, 5: 110}
- shortest_path_len.mean: 3.5714
- num_success_paths.mean: 1.8571
- target_state_size.mean: 2.7143
- max_steps.mean: 45.5
- step_budget_ratio_vs_shortest_path.mean: 13.4226
- share_shortest_path_le_2: 0.214
- share_target_size_le_2: 0.571
- share_step_budget_ratio_ge_15: 0.500

### train
- goals: 4760
- difficulty_counts: {2: 10, 3: 720, 4: 1540, 5: 2490}
- shortest_path_len.mean: 3.1534
- num_success_paths.mean: 1.8592
- target_state_size.mean: 2.8151
- max_steps.mean: 44.0924
- step_budget_ratio_vs_shortest_path.mean: 14.1402
- share_shortest_path_le_2: 0.321
- share_target_size_le_2: 0.544
- share_step_budget_ratio_ge_15: 0.563

## Highest Saturation-Risk Candidates
- `WFG-EDUCATION-0011` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0012` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0013` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0014` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0015` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0016` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0017` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0018` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0019` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-EDUCATION-0020` (train/education): difficulty=3, paths=2, shortest_path=1, target=1, step_ratio=25.0, risk=5
- `WFG-CRISIS-0061` (train/crisis): difficulty=4, paths=2, shortest_path=1, target=2, step_ratio=20.0, risk=5
- `WFG-CRISIS-0062` (train/crisis): difficulty=4, paths=2, shortest_path=1, target=2, step_ratio=20.0, risk=5
- `WFG-CRISIS-0063` (train/crisis): difficulty=4, paths=2, shortest_path=1, target=2, step_ratio=20.0, risk=5
- `WFG-CRISIS-0064` (train/crisis): difficulty=4, paths=2, shortest_path=1, target=2, step_ratio=20.0, risk=5
- `WFG-CRISIS-0065` (train/crisis): difficulty=4, paths=2, shortest_path=1, target=2, step_ratio=20.0, risk=5

## Highest Structural-Complexity Candidates
- `WFG-GOV-0001` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0002` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0003` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0004` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0005` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0006` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0007` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0008` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0009` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0010` (dev/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0211` (train/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0212` (train/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0213` (train/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0214` (train/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4
- `WFG-GOV-0215` (train/government): difficulty=5, paths=1, shortest_path=6, target=2, constraints=3, counterfactual_axes=4

## Theme-Level Means
- `support`: goals=360, shortest_path.mean=2.4722, target.mean=2.4722, paths.mean=2.0278, step_ratio.mean=16.1458, share_short_path=0.778
- `composite`: goals=360, shortest_path.mean=2.7222, target.mean=2.25, paths.mean=1.9167, step_ratio.mean=15.2407, share_short_path=0.639
- `home`: goals=360, shortest_path.mean=2.5833, target.mean=2.2222, paths.mean=2, step_ratio.mean=12.4537, share_short_path=0.583
- `finance`: goals=360, shortest_path.mean=2.8056, target.mean=2.3611, paths.mean=1.9722, step_ratio.mean=13.5278, share_short_path=0.556
- `education`: goals=360, shortest_path.mean=2.7222, target.mean=1.9722, paths.mean=1.8333, step_ratio.mean=12.4028, share_short_path=0.417
- `crisis`: goals=360, shortest_path.mean=2.8333, target.mean=2.7778, paths.mean=1.8889, step_ratio.mean=16.6065, share_short_path=0.417
- `travel`: goals=360, shortest_path.mean=2.9167, target.mean=3.3056, paths.mean=1.9722, step_ratio.mean=14.4352, share_short_path=0.417
- `security`: goals=360, shortest_path.mean=2.8056, target.mean=2.5, paths.mean=1.4167, step_ratio.mean=11.4375, share_short_path=0.361
- `daily`: goals=360, shortest_path.mean=3.2778, target.mean=3, paths.mean=1.8333, step_ratio.mean=14.1782, share_short_path=0.139
- `newcomer`: goals=360, shortest_path.mean=4, target.mean=2.6389, paths.mean=1.9167, step_ratio.mean=11.9903, share_short_path=0.083
- `career`: goals=360, shortest_path.mean=3.9167, target.mean=3.75, paths.mean=1.9722, step_ratio.mean=15.9722, share_short_path=0.028
- `government`: goals=360, shortest_path.mean=4.2778, target.mean=2, paths.mean=1.2222, step_ratio.mean=9.3963, share_short_path=0.000
- `health`: goals=360, shortest_path.mean=4, target.mean=4, paths.mean=2, step_ratio.mean=17.0139, share_short_path=0.000
- `social`: goals=360, shortest_path.mean=3.1389, target.mean=4.1389, paths.mean=2, step_ratio.mean=16.6204, share_short_path=0.000
