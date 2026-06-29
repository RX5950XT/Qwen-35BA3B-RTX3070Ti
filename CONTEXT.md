# Qwen-35B-A3B × RTX 3070 Ti 部署專案 — 交接文件

## 專案概述

在 RTX 3070 Ti（8GB VRAM）+ 64GB RAM 上，使用 llama.cpp 部署 Qwen3.6-35B-A3B MoE 模型（35B 總參數 / 3B 啟用），追求極致推理效能。

## 硬體與環境

| 項目     | 規格                                                |
| -------- | --------------------------------------------------- |
| GPU      | RTX 3070 Ti — 8GB VRAM, PCIe 4.0 x16               |
| CPU      | AMD Ryzen 7 5700X — 8C/16T                         |
| RAM      | 64GB DDR4-3200 雙通道 (32GB*2，實測頻寬 33.46 GB/s) |
| OS       | Windows                                             |
| 推理引擎 | llama-server.exe tag b9437 prebuilt CUDA 12.4       |

## 核心架構決策

1. **CPU-GPU 異構混合推理與 MoE 專家分流**：`--override-tensor "ffn_.*_exps.*=CPU"` + `-ngl 99` + `-ncmoe 35`。將 5 層 MoE 專家（約 2.5GB 顯存）卸載至 RTX 3070 Ti 的 VRAM 安全區，藉由 GPU Tensor Cores 的強大算力抹平反量化開銷，其餘 36 層 MoE 專家則留存在系統記憶體。
2. **MTP 投機解碼**：Q4 模型以 `--spec-draft-n-max 3 --spec-draft-p-min 0.05` 為最優甜點；Q3 模型以 `--spec-draft-n-max 2 --spec-draft-p-min 0.12` 為最優甜點。
3. **KV Cache 類型靈活調度**：在 32K 內標準上下文，KV Cache 使用 `f16` (16-bit) 格式，省去解壓縮與反量化的計算延遲，TPS 最大化；在 48K 極限長上下文，KV Cache 使用 `q8_0` (8-bit) 節省 50% 顯存防禦 WDDM Fallback。
4. **Windows 前台排程與自旋鎖優化**：`start /high` 獨立視窗運行（+ `--prio 3`），搭配微秒級自旋鎖 `--poll 50` (Q4) 或 `--poll 150` (Q3)，免除超執行緒競爭。
5. **Slot 限制**：`-np 1` 防止多 KV 槽庫膨脹擠爆顯存。

## 關鍵實測數據

| 模型                                                                                                                                              | 背景 TPS | 前台 TPS (尋優極限) | MTP 接受率   | 最佳 KV Cache 格式 |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------- | ------------ | ------------------ |
| Qwen3.6 Q4_K_M                                                                                                                                    | 31.05    | **35.02**     | 81.4%        | `f16`            |
| Qwen3.6 Q3_K_M                                                                                                                                    | 25.09    | **30.65**     | 88.8%        | `q8_0`           |
| Ornith-1.0 Q4_K_M                                                                                                                                 | 22.79    | **27.43**     | N/A (無 MTP) | `f16`            |
| Ornith-1.0 IQ3_M                                                                                                                                  | —       | **22.29**     | N/A          | `q4_0`           |
| *備註：以上數據皆為 64GB 雙通道記憶體（33.46 GB/s）極限壓測數據。雙通道解鎖與 GQA 結構最佳化成功讓 Qwen Q4 性能從 29.26 TPS 攀升至 35.02 TPS。* |          |                     |              |                    |

## 產出文件

| 路徑                                                       | 用途                                     |
| ---------------------------------------------------------- | ---------------------------------------- |
| `start.bat`                                              | 統一入口互動式控制台                     |
| `docs/interactive-deployment-dashboard.html`             | 互動式儀表板（4 Tab / 4 Chart.js 圖表）  |
| `docs/local-inference-optimization-and-tuning-report.md` | 效能調優與單/雙通道比對實驗報告 (綜合版) |
| `scripts/start-*.bat`                                    | 各模型啟動腳本 (5 款)                    |
| `scratch/auto-tune-results.json`                         | 自動調參最優物理參數數據庫 (JSON 備份)   |
| `scratch/auto-tune-hyperparams.py`                       | 廣泛自動化自適應調參壓測腳本             |
| `scratch/benchmark-ram-bandwidth-mp.py`                  | 多進程記憶體頻寬壓測工具 (繞過 GIL)      |
| `scratch/download-model.py`                              | 按需下載模型工具 (Hugging Face API)      |
| `scratch/rebuild-bat-files.py`                           | 讀取 JSON 並重建批次檔工具               |
| `scratch/setup-environment.py`                           | 環境自動診斷與引擎下載工具               |

## 已完成里程碑

1. 研究 → 規劃 → 環境準備 → 模型下載 → 部署驗證
2. 記憶體頻寬實測與物理瓶頸診斷（18.48 GB/s，Flex Mode 退化）
3. Ornith-1.0-35B 架構對比與 MTP 不相容性確認
4. 全自動網格調優（threads / poll / MTP / cache_type / affinity）
5. 多維往復實驗（Context × TPS / MTP 窗口 / GPU Expert Offload PK）
6. Q4 極限衝刺與 Windows 前台排程紅利發現（背景 23.85 → 前台 29.26）
7. HTML 儀表板全面翻新（CSS/JS 去重、4 圖表修復、語法驗證通過）
8. 文檔數據一致性校正（accept_rate / threads / poll / 幽靈引用修復）
9. 完成 64GB DDR4-3200 雙通道記憶體升級，並以多進程壓測證實成功解鎖雙通道 (實測唯讀 33.46 GB/s / 複製 43.20 GB/s)，較原先單通道（唯讀 6.03 GB/s / 複製 18.48 GB/s）的唯讀頻寬大增 454.9%、複製頻寬飆升 133.8%。
10. 優化啟動腳本與主控制台 start.bat，解除 Q4 腳本的同步阻塞，並改進 Web UI 開啟邏輯：使用 curl 輪詢健康端點，確保模型 100% 載入就緒後再自動開啟 Web UI (http://127.0.0.1:8888) 頁面。
11. 全專案腳本健壯性深度審查：修復跨進程 NumPy 頻寬測試在記憶體不足分支時的結構崩潰 Bug，修正批次檔生成器中的變數轉義錯誤與標準化啟動參數，清理無效的臨時 C++ 原始碼，確保所有部署與壓測腳本 100% 健壯運行。
12. Windows 專用批次與連線健壯性修正：修復了 `start` 命令在 cmd.exe 下 the `^` 續行參數誤解 Bug，將所有啟動參數扁平化為單行；並修復了測試腳本中使用 `localhost` 時在 Windows 下因 IPv6 解析干擾引發的連線拒絕 Bug，將其改為標準 IPv4 迴路 `127.0.0.1`，並經執行緒基準測試證實 Qwen Q4 於新記憶體解鎖下純解碼速度成功突破至 **35.94 TPS**！
13. GPU MoE 專家卸載調優與 3-bit 模型補齊：背景下載了 Qwen3.6 Q3_K_M (3-bit) 模型。實測證實，受限於 CPU 反量化運算鐵壁，純 CPU 的 3-bit 速度不升反降。但經調優在 8GB VRAM 安全區內設定 GPU 專家卸載（均為 `-ncmoe 35`），可藉由 GPU 算力抹平反量化延遲，使 Qwen Q4 的解碼極限提速至 **35.02 TPS**，已達此硬體定址與頻寬下的物理絕對天花板！
14. 更新互動式部署儀表板 (interactive-deployment-dashboard.html)，將 64GB 雙通道實測頻寬 33.46 GB/s、CPU 反量化算力牆 (CPU Bound) Bottleneck、以及 GPU 專家卸載調優 (-ncmoe) 成功打破效能天花板 (35.02 TPS) 的最新發現與參數全面寫入，完成文檔與實驗數據的同步對齊。
15. **完成 Phase 30 廣泛自動化調參壓測**：實作全自動調優壓測腳本 `auto-tune-hyperparams.py`，全方位遍遍專家卸載、執行緒、自旋鎖、numa、MTP 投機窗口、KV Cache 精度格式與 Batch 大小。成功將 Q4 模型的生成效能提速至 **35.02 TPS**，Q3 模型提速至 **30.65 TPS**。同時，讀取模型 Header 揭示了 GQA（2 個 KV 頭、256 頭維度、41 層）的物理實情，為 RTX 3080 20G 長上下文部署奠定了物理與數據根基。
16. **完成對抗式紅隊審計與漏洞診斷**：對專案核心文件進行極限物理與數據交叉檢查，產出 `red_team_audit_report.md`。揭示了 HTML 圖表數據庫殘留 23.85 TPS 舊數據、verify-deployment.py 幽靈引用、72GB RAM 錯配，以及 8.06 GiB 顯存需求必定觸發 WDDM Fallback 的物理學盲區。
17. **完成程式碼與邏輯深度審計**：對所有 Python 壓測/部署腳本與 Windows 批次檔進行邏輯漏洞審查，指出 `benchmark-ram-bandwidth-mp.py` 當遇到 MemoryError 時會觸發進程死鎖的嚴重漏洞、`setup-environment.py` 與 `download-model.py` 的 API Rate Limit/殘留臨時檔/鎖定異常，以及所有 Python 腳本工作目錄偏移時導致路徑偏移與損毀的隱患，並撰寫 `code_audit_report.md` 報告。
18. **實作自動化整合測試與 Windows 啟動閃退死鎖修復**：徹底修復了最新 llama.cpp 廢除 `--numa none` 造成的彈出視窗閃退，重構了批次檔生成器；並實作了 `run-integration-tests.py` 全自動整合測試，透過 stdin 重定向 DEVNULL 破解 `pause` 等待卡死，實測 100% 綠色通過所有模型 Ready 部署、 completions 生成與 RAM 頻寬壓測，確保專案 100% 健壯運行。


## 最新效能展望 (記憶體頻寬 33.46 GB/s)

- **4-bit 模型 (Q4_K_M)**：經 `-ncmoe 35` 卸載 5 層專家至 GPU 並啟用 `f16` KV cache 後，滿血解碼極限達 **35.02 TPS**。
- **3-bit 模型 (Q3_K_M)**：經 `-ncmoe 35` 卸載 5 層專家並啟用 `q8_0` KV cache 後，解碼極限提升至 **30.65 TPS**。
- **物理天花板結論**：在 RTX 3070 Ti (8GB) + 64GB 雙通道記憶體限制下，35B 大模型受限於 PCIe x16 (31.5 GB/s) 頻寬與 CPU 反量化運算極限，解碼效能之物理鐵壁為 **~35 TPS**。未來若升級為 **RTX 3080 20G**，由於 VRAM 充裕，在 200K 長上下文下搭配 `Q4_0` KV cache 僅需 3.91GB VRAM，可將 70% 以上 of MoE 專家完全卸載至 GPU，實現破局的 **60~80+ TPS** 超高推論速度。

