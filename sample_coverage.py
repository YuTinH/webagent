import json
import random

def coverage_aware_sample(input_file, target_count=100):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 1. 统计每个任务在哪些剧本中出现
    task_to_scenarios = {}
    all_scenarios = data
    
    for idx, s in enumerate(all_scenarios):
        for step in s['steps']:
            tid = step['task_id']
            if tid not in task_to_scenarios:
                task_to_scenarios[tid] = []
            task_to_scenarios[tid].append(idx)
            
    all_tasks = set(task_to_scenarios.keys())
    print(f"Total unique tasks found in dataset: {len(all_tasks)}")
    
    # 2. 贪婪覆盖采样
    selected_indices = set()
    covered_tasks = set()
    
    # 优先处理最稀有的任务
    sorted_tasks = sorted(list(all_tasks), key=lambda t: len(task_to_scenarios[t]))
    
    for task in sorted_tasks:
        if task not in covered_tasks:
            # 选一个包含该任务的剧本
            # 为了多样性，随机选一个
            possible_indices = task_to_scenarios[task]
            # 尽量选一个能覆盖更多其他未覆盖任务的
            best_idx = -1
            max_new_cover = -1
            
            # 抽样检查以防循环过久
            sample_size = min(len(possible_indices), 50)
            for idx in random.sample(possible_indices, sample_size):
                scenario_tasks = {step['task_id'] for step in all_scenarios[idx]['steps']}
                new_cover = len(scenario_tasks - covered_tasks)
                if new_cover > max_new_cover:
                    max_new_cover = new_cover
                    best_idx = idx
            
            selected_indices.add(best_idx)
            # 更新覆盖状态
            for step in all_scenarios[best_idx]['steps']:
                covered_tasks.add(step['task_id'])
                
    print(f"Selected {len(selected_indices)} scenarios to cover all tasks.")
    
    # 3. 补足到 100 条
    if len(selected_indices) < target_count:
        remaining_indices = list(set(range(len(all_scenarios))) - selected_indices)
        additional = random.sample(remaining_indices, target_count - len(selected_indices))
        selected_indices.update(additional)
        
    # 4. 输出结果
    sampled_data = [all_scenarios[i] for i in selected_indices]
    
    # 最后验证一次
    final_tasks = {step['task_id'] for s in sampled_data for step in s['steps']}
    print(f"Final sampled coverage: {len(final_tasks)}/{len(all_tasks)}")
    
    return sampled_data

if __name__ == "__main__":
    sampled = coverage_aware_sample("dynamic_scenarios_v3.json", 100)
    with open("sampled_100_v3.json", "w", encoding="utf-8") as f:
        json.dump(sampled, f, indent=2, ensure_ascii=False)
    print("✅ Sampled 100 scenarios saved to sampled_100_v3.json")
