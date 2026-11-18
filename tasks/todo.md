# Qwen-35BA3B-RTX3070Ti todo
最後更新：2026-11-19

## 現況（交接）

在 RTX 3070 Ti（8GB）+ Ryzen 7 5700X（8C/16T）+ 64GB DDR4-3200 雙通道（實測唯讀 33.46 GB/s）上，用 llama.cpp（`llama-server.exe` tag b9437 prebuilt CUDA 12.4，Windows）部署 Qwen3.6-35B-A3B MoE（35B 總參數 / 3B 啟用 / 41 層 / GQA 2 KV 頭）。參數細節與下載指令見 `AGENTS.md`，使用方式見 README。

### 關鍵檔案

- `start.bat`：統一入口互動式控制台；`scripts/start-*.bat`：各模型啟動腳本（5 款）
- `scratch/auto-tune-hyperparams.py` → `scratch/auto-tune-results.json` → `scratch/rebuild-bat-files.py`：自動調參並重建批次檔
- `scratch/benchmark-ram-bandwidth-mp.py`（多進程頻寬壓測）、`download-model.py`、`setup-environment.py`（環境診斷與引擎下載）、`run-integration-tests.py`（整合測試）
- `docs/interactive-deployment-dashboard.html`（儀表板）、`docs/local-inference-optimization-and-tuning-report.md`（調優與單/雙通道比對報告）

### 核心決策

1. MoE 專家分流：`--override-tensor "ffn_.*_exps.*=CPU"` + `-ngl 99` + `-ncmoe 35`（5 層專家上 GPU 抹平反量化開銷，其餘 36 層留 RAM）。
2. MTP：Q4 用 `--spec-draft-n-max 3 --spec-draft-p-min 0.05`；Q3 用 `n-max 2 / p-min 0.12`。
3. KV cache：32K 內用 `f16`（TPS 最高）；48K 長上下文用 `q8_0`（防 WDDM fallback）。
4. Windows 排程：`start /high` 獨立視窗 + `--prio 3`；`--poll 50`（Q4）/ `--poll 150`（Q3）。
5. `-np 1` 防多 KV 槽擠爆顯存。

### 實測（64GB 雙通道）

| 模型 | 背景 TPS | 前台 TPS | MTP 接受率 | KV |
|---|---|---|---|---|
| Qwen3.6 Q4_K_M | 31.05 | **35.02** | 81.4% | `f16` |
| Qwen3.6 Q3_K_M | 25.09 | **30.65** | 88.8% | `q8_0` |
| Ornith-1.0 Q4_K_M | 22.79 | **27.43** | 無 MTP | `f16` |
| Ornith-1.0 IQ3_M | — | **22.29** | 無 MTP | `q4_0` |

- 雙通道升級：唯讀 6.03 → 33.46 GB/s、複製 18.48 → 43.20 GB/s；Qwen Q4 從 29.26 升到 35.02 TPS（純解碼執行緒測試最高 35.94）。
- 純 CPU 跑 3-bit 不升反降（CPU 反量化是瓶頸）；要靠 GPU 專家卸載。
- 結論：此硬體物理天花板約 35 TPS（PCIe x16 頻寬 + CPU 反量化）。若換 RTX 3080 20G，200K 上下文搭 `Q4_0` KV 僅需 3.91GB VRAM，可把 70% 以上專家搬上 GPU，預估 60~80+ TPS（未實測）。

### 踩雷

- 新版 llama.cpp 廢除 `--numa none` 會讓視窗閃退；批次檔生成器已處理。
- `start` 命令在 cmd.exe 下 `^` 續行會被誤解，啟動參數一律扁平成單行。
- 測試用 `localhost` 在 Windows 會受 IPv6 解析干擾，改用 `127.0.0.1`。
- 整合測試要把 stdin 導向 DEVNULL，否則 `pause` 會卡死。
- Python 腳本開頭 `os.chdir(project_root)` 防工作目錄偏移；`start.bat` 開頭 `cd /d "%~dp0"`；`choice` 輸入要去雙引號。
- `benchmark-ram-bandwidth-mp.py` 的 `barrier.wait()` 放 `finally`，避免 MemoryError 死鎖。
- 8.06 GiB 顯存需求必定觸發 WDDM fallback，設定要留餘裕。
- Web UI：啟動後用 curl 輪詢健康端點，就緒後才開 `http://127.0.0.1:8888`。

## 待辦

目前無未完成項目。換硬體後重跑 `auto-tune-hyperparams.py`，並更新本檔數據。
