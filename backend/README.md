# CPU/CAD — 家装CAD+效果图智能报价系统

## 项目结论（最后更新：2026-06-12）

**最终决策：拆分双接口独立运行方案**
FastAPI异步环境下，大体积DXF(104MB)+LLaVA图片识别并行执行必然超时崩溃。
拆分接口后两套能力单独运行均已验证可用，方案稳定。

---

## 两个接口，各管各的

### 接口1：纯DXF矢量解析+报价（主推，秒级响应）
- `POST /api/analyze_full`
- 入参：`cad_file=@xxx.dxf`
- 能力：解析106个空间，精准算量，自动报价（当前单价9374）
- 稳定、秒出结果
- 适用：CAD户型算量、基础装修报价核心场景

### 接口2：效果图单独视觉识别
- `POST /api/analyze`
- 入参：`image_file=@效果图.jpg`
- 能力：LLaVA正常识别材质/空间，单独调用无崩溃
- 适用：提取效果图材质、软装、风格信息

## 使用规则
1. **禁止合并DXF+图片在一个接口并发处理**，会崩溃；
2. 业务层分两步：先调接口1出工程量&报价，再调接口2补材质/风格，人工合并；
3. 现有代码、素材、运行环境均无需改动，直接按拆分接口上线。

## 运行环境
- 后端：FastAPI + uvicorn，端口 **8100**
- DXF解析：ezdxf（纯Python，无需ODA转换器）
- 视觉识别：Ollama + LLaVA 7B（localhost:11434）
- 环境：conda torchtest（Python 3.10）
- 项目路径：`/home/sd317/cad/backend/`

## 启动命令
```bash
cd /home/sd317/cad/backend
source ~/miniconda3_new/etc/profile.d/conda.sh
conda activate torchtest
nohup python main.py > /tmp/cad_backend.log 2>&1 &
```

## 后端服务状态
- 服务运行中 ✅ (pid: 202025, port 8100)
- Ollama运行中 ✅ (llava:7b)
- 素材目录：`uploads/` 下14份PDF、1份DWG、1份DXF、3张效果图
