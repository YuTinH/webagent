# WebAgent Dynamic Suite v2 (Skinned UI)
生成：2025-11-16T06:44:54.745548

更真实的页面皮肤（暗色、卡片、面包屑、模态、Toast、网格、徽章等），DOM 稳定且为自动化标注了 data-*。

## 运行
```bash
unzip webagent_dynamic_suite_v2_skin.zip
cd webagent_dynamic_suite_v2_skin
python3 server.py 8000
# 打开：
# http://localhost:8000/shop.local/index.html
# http://localhost:8000/pay.local/wallet/cards.html
# http://localhost:8000/trip.local/manage/PNR9ZZ.html
# http://localhost:8000/permit.local/RP-2024-77.html
# http://localhost:8000/energy.local/plan.html
# http://localhost:8000/card.local/block.html
```

## 校验（verify）
```bash
python3 verify_check.py D4-0017
```

## 扩展
- 新增页面：复制一份 HTML，用 `btn pri`/`badge`/`kv` 等类快速搭 UI
- 动作：按钮 `onclick="send('<TASK>','<ACTION>', {...})"`；在 `server.py -> mutate_env` 加分支
- 状态：在 `env/` 加 `*_initial.json` 与 `*_expected.json`
