# Qwen-35B-A3B 部署專案規範

## 常用指令

- **啟動本機控制台 (主入口)**：雙擊或執行根目錄下的 `start.bat`
- **強制關閉伺服器並釋放記憶體**：執行 `scripts\stop-all-servers.bat`
- **一鍵硬體自適應全自動調參**：執行 `python scratch\auto-tune-hyperparams.py`
- **獨立啟動伺服器**：

  - Qwen3.6 Q4: `scripts\start-qwen-35b-q4-standard.bat`
  - Qwen3.6 48K Context: `scripts\start-qwen-35b-q4-48k-context.bat`
  - Qwen3.6 3bit: `scripts\start-qwen-35b-q3-speed.bat`
  - Ornith Q4: `scripts\start-ornith-35b-q4-standard.bat`
  - Ornith 3bit: `scripts\start-ornith-35b-q3-speed.bat`
- **測量記憶體頻寬**：`python scratch\benchmark-ram-bandwidth-mp.py` (多進程精準版)
- **手動重建所有啟動批次檔**：`python scratch\rebuild-bat-files.py`
- **下載模型 (使用 hf CLI，下載後需重新命名對齊腳本)**：

  - Qwen3.6 Q4: `hf download unsloth/Qwen3.6-35B-A3B-MTP-GGUF Qwen3.6-35B-A3B-UD-Q4_K_M.gguf --local-dir models`
  - Qwen3.6 3bit: `hf download unsloth/Qwen3.6-35B-A3B-MTP-GGUF Qwen3.6-35B-A3B-UD-Q3_K_M.gguf --local-dir models`
  - Ornith Q4: `hf download bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf --local-dir models`
  - Ornith 3bit: `hf download bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF deepreinforce-ai_Ornith-1.0-35B-IQ3_M.gguf --local-dir models`
    *(下載後請依照順序重新命名為：`Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf`、`Qwen3.6-35B-A3B-MTP-Q3_K_M.gguf`、`Ornith-1.0-35B-Q4_K_M.gguf`、`Ornith-1.0-35B-IQ3_M.gguf`)*
- **測試 API 請求**：

  ```powershell
  $body = @{ model = "qwen"; messages = @( @{ role = "user"; content = "Hello" } ) } | ConvertTo-Json -Compress
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
  Invoke-RestMethod -Uri "http://127.0.0.1:8888/v1/chat/completions" -Method Post -Body $bytes -ContentType "application/json"
  ```

## 專案架構

- `bin/` — llama.cpp 核心與 CUDA 加速相關 DLL 依存項目
- `models/` — 模型存放處
- `scripts/` — 收納所有獨立啟動/關閉的批次檔 (.bat)
- `start.bat` — 統一入口的互動式控制台 (ASCII 選單)
- `docs/` — 優化報告與分析文件 (僅保留一個 HTML 與一個 MD)
  - `interactive-deployment-dashboard.html` — 互動式儀表板（4 Tab: 部署計畫 / 底層診斷 / 術語百科 / 實驗圖表）
  - `local-inference-optimization-and-tuning-report.md` — 效能調優與單/雙通道比對實驗報告 (綜合版)
- `scratch/` — 自動化實驗工具與原始數據 (僅保留必要檔案)
  - `auto-tune-hyperparams.py` — 全自動硬體自適應調參腳本
  - `auto-tune-results.json` — 調參結果數據庫
  - `benchmark-ram-bandwidth-mp.py` — 多進程記憶體頻寬壓測工具
  - `download-model.py` — 根據選單按需下載模型工具
  - `rebuild-bat-files.py` — 讀取 JSON 並重建批次檔工具
  - `setup-environment.py` — 開機自動環境診斷與引擎下載工具
- `tasks/` — 開發進度與計畫規劃
  - `todo.md` — 交接現況與待辦（≤100 行）
  - `lessons.md` — 調優教訓總結
- `AGENTS.md` — AI Agent 後續協作開發指引與硬體調優速查
- `README.md` — 本專案說明檔

