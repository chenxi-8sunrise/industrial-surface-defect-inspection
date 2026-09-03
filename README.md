# 工业表面缺陷检测与定位系统

本项目面向 MVTec AD 的 bottle、tile、transistor 三类工业图像，统一实现并比较四种异常检测模型：

- CAE：卷积自编码器重建误差；
- PaDiM：预训练特征分布建模；
- PatchCore：特征记忆库与最近邻检索；
- STFPM：教师-学生特征金字塔匹配。

系统采用 FastAPI、Vue 3 和 SQLite，支持图片检测、模型切换、异常热力图、历史记录和统计分析。

## 目录

- `backend/`：API、数据库和推理服务；
- `frontend/`：Vue 用户界面；
- `ml/`：数据、训练、评估和四模型实现；
- `configs/`：项目与模型配置；
- `tests/`：自动化测试；
- `docs/`：运行说明、实验记录和交付材料；
- `scripts/`：环境、数据和启动脚本。

## 当前数据范围

主数据集为 MVTec AD，类别固定为 `bottle`、`tile`、`transistor`。数据保留官方的 `train/test/ground_truth` 结构，路径由 `configs/project.yaml` 统一管理。

## 环境与数据

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe scripts\download_mvtec_subset.py
.venv\Scripts\python.exe scripts\inspect_dataset.py
```

数据完整性检查只有在三类训练图像、测试图像与像素掩膜数量全部符合 MVTec AD 统计时才会通过。

## 训练与评测

```powershell
.venv\Scripts\python.exe scripts\train_model.py patchcore bottle
.venv\Scripts\python.exe scripts\evaluate_model.py patchcore bottle
```

将命令中的模型替换为 `cae`、`padim`、`patchcore` 或 `stfpm`，类别替换为 `bottle`、`tile` 或 `transistor`。训练参数位于 `configs/models/`，模型文件保存到 `artifacts/models/`，评测结果保存到 `artifacts/results/`。

## 系统运行

前端生产构建完成后，双击 `启动系统.bat`。系统地址为 `http://127.0.0.1:8000`，接口文档地址为 `http://127.0.0.1:8000/docs`。

开发模式命令：

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
cd frontend
npm install
npm run dev
```

## 验证

```powershell
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

评测指标包括图像级 AUROC、像素级 AUROC、Precision、Recall、F1 和单张平均推理耗时。
