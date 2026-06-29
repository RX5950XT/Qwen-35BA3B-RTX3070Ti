# Qwen-35B-A3B x RTX 3070 Ti 本地極致優化部署專案

本專案提供一個 **「零摩擦、一鍵到底」** 的全自動部署方案。利用 `llama.cpp` 異構混合推理技術，在具有記憶體限制與顯示晶片限制的本機環境下，自動完成引擎下載、硬體自適應優化與大模型部署，壓榨出 35B 級別大型 MoE (Mixture of Experts) 模型的物理極限推理速度。

---

## 1. 效能與實驗數據報告 

本專案的所有最優參數與測試數據，均基於以下硬體環境與實驗變因得出。詳細的物理學分析與診斷，請參閱本專案產出之文件：

* **視覺化儀表板**：[interactive-deployment-dashboard.html](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/docs/interactive-deployment-dashboard.html)
* **效能與調優綜合報告**：[local-inference-optimization-and-tuning-report.md](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/docs/local-inference-optimization-and-tuning-report.md)

### 📊 記憶體單/雙通道頻寬與推理速度對比

* **測試硬體**：AMD Ryzen 7 5700X (8C/16T) + RTX 3070 Ti (8GB VRAM) + 64GB RAM。
* **實測效能對照表** *(註：表中除標記為「理論極限」外，所有單雙通道之頻寬與 TPS 數據，均為在該實體硬體上實際運行壓測所得出的真實測量數據。其中 TPS 為經完整網格壓測調優後的「最優最快極限 TPS」，以呈現純頻寬升級帶來的極限效能對決)*：

| 模型名稱 (35B MoE)           | 量化格式         | 單通道 Flex Mode (18.48 GB/s 複製頻寬 / 6.03 GB/s 唯讀) | 雙通道 DDR4-3200 (43.20 GB/s 複製頻寬 / 33.46 GB/s 唯讀) | 性能增幅與調優特徵                                          |
| :--------------------------- | :--------------- | :------------------------------------------------------ | :------------------------------------------------------- | :---------------------------------------------------------- |
| **Qwen3.6-35B** (MTP)  | **Q4_K_M** | `29.26 t/s`                                           | **`35.02 t/s`**                                  | 🚀 提升 19.7%！啟用`f16` KV cache 並卸載 5 層專家至 GPU。 |
| **Qwen3.6-35B** (MTP)  | **Q3_K_M** | `29.09 t/s`                                           | **`30.65 t/s`**                                  | 🚀 提升 5.4%！啟用`q8_0` KV cache 並卸載 5 層專家。       |
| **Ornith-1.0** (無MTP) | **Q4_K_M** | `27.43 t/s`                                           | **`27.43 t/s`**                                  | 受限於 CPU 反量化算力牆，單/雙通道速度持平。                |
| **Ornith-1.0** (無MTP) | **IQ3_M**  | `22.29 t/s`                                           | **`22.29 t/s`**                                  | 受限於 imatrix CPU 計算開銷，高頻寬未能完全釋放。           |

> [!TIP]
> **💡 為什麼 Q4 配 `f16` KV 快取，Q3 卻配 `q8_0`？**
>
> * **Q4_K_M**：32K 內顯存充足，使用 **`f16`** 可以**完全免去** KV 快取在讀寫時的解壓反量化計算開銷，從而榨出最高的 **`35.02 TPS`** 物理極限。
> * **Q3_K_M**：因為 3-bit 權重在 CPU 端的反量化計算開銷（算力牆）顯著大於 4-bit，此時推論速度完全被 CPU 計算鎖死。經壓測，在此狀態下使用 `f16` 與 `q8_0` 的 TPS 完全相同，故調優策略選擇 **`q8_0`**，在不犧牲速度的前提下，為主機省下近一半 of 顯存空間。

---

## 2. 🚀 部署與運行指引 (全自動一鍵啟動)

本專案已實現 **「零摩擦開箱即用」** 的自動化環境配置與模型按需下載。您只需要滿足以下極簡的前置準備：

### 2.1 啟動步驟

1. 下載並安裝本機 [Python 3.9+](https://www.python.org/downloads/) (安裝時請勾選 "Add Python to PATH")。
2. 雙擊執行專案根目錄下的 [start.bat](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/start.bat)。

### 2.2 主控制台 (start.bat) 核心功能介紹

[start.bat](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/start.bat) 是本專案的統一交互式控制台，它整合了整個專案的一鍵式運維、部署與診斷功能：

1. **一鍵環境自適應診斷與 llama.cpp 引擎自動安裝**：
   * 雙擊啟動時會自動呼叫 [setup-environment.py](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/scratch/setup-environment.py) 進行 Python 相依套件與硬體 CUDA 偵測。
   * 若本地無 `bin/` 引擎，將會自適應地從 GitHub 下載對應您電腦規格的最新 `llama.cpp` CPU 或 CUDA 版本，自動配置並在解壓完成後自動刪除臨時檔案，達到真正「零摩擦」部署。
2. **Qwen3.6-35B (含原生 MTP 投機解碼) 推理服務啟動**：
   * **選項 1**：Q4_K_M 標準滿血版 (32K Context，`f16` KV cache，實測極速 **35.02 TPS**)。
   * **選項 2**：Q4_K_M 超長上下文版 (48K Context，`q8_0` KV cache，極限 VRAM 擴展測試)。
   * **選項 3**：Q3_K_M 高速版 (32K Context，`q8_0` KV cache，實測速度 **30.65 TPS**)。
3. **Ornith-1.0-35B (Agentic 邏輯推理，無 MTP) 推理服務啟動**：
   * **選項 4**：Q4_K_M 標準推理版 (32K Context，`f16` KV cache，實測速度 **27.43 TPS**)。
   * **選項 5**：IQ3_M 進階推理版 (32K Context，`q8_0` KV cache，實測速度 **22.29 TPS**)。
4. **模型按需下載與命名自動對齊**：
   * 啟動上述任何模型時，若本地無對應的 GGUF 檔案，控制台會自動執行 [download-model.py](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/scratch/download-model.py)，調用官方 Hugging Face API 進行高速多線程、斷點續傳的下載，並自動將下載後的檔案重命名對齊啟動腳本。
5. **健康檢測與自動彈出對話 Web 網頁**：
   * 背景異步拉起伺服器後，主控制台會以 curl 持續輪詢健康檢測端點，在模型加載完畢並 Ready 的第一時間，**自動呼叫預設瀏覽器**彈出對話 Web UI 頁面 (`http://127.0.0.1:8888`)，使用者可直接打字對話。
6. **一鍵強制關閉伺服器與顯存清理 (選項 6)**：
   * 一鍵強制終止所有背景 `llama-server.exe` 推理進程，安全釋放系統記憶體與顯存。
7. **一鍵本機實體記憶體頻寬壓測 (選項 7)**：
   * 一鍵運行多進程 NumPy 記憶體頻寬測試腳本 [benchmark-ram-bandwidth-mp.py](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/scratch/benchmark-ram-bandwidth-mp.py)，測量您電腦在 1-12 進程下的 Read/Copy 真實頻寬，用以判定通道狀態與推算 TPS 理論極限。

### 2.3 自動化工作流說明

當您雙擊 `start.bat` 後，系統會在背景自動執行以下流程，您無須手動操作：

* **依賴庫檢查**：檢查並自動安裝 `numpy` 與 `requests`。
* **引擎自動下載**：若根目錄無 `bin/` 資料夾，自動偵測您的電腦是否具備 NVIDIA 顯卡與 CUDA：
  * *GPU 模式*：自動下載最新的官方 `llama.cpp` CUDA 12.4 x64 預編譯壓縮包。
  * *CPU 模式*：自動下載官方最新純 CPU 預編譯壓縮包。
  * 下載後自動解壓並配置至 `bin/`，並自動刪除臨時檔案。
* **按需下載模型**：當您在主選單中選擇啟動某個模型時，若本地 `models/` 下無該模型，系統會**自動在背景觸發多線程、支援斷點續傳的下載**，下載完成後自動命名並拉起模型推理，開箱即用。
* **自動對話網頁開啟**：伺服器載入就緒後，系統會**自動彈出瀏覽器**開啟對話介面 (`http://127.0.0.1:8888`)。

---

## 3. 🔧 一鍵硬體自適應全自動化調參 (Auto-Tuning)

當您首次在自己的電腦上運行本專案時，若想獲得最契合您設備硬體的最優生成速度（TPS），請在根目錄執行：

```cmd
python scratch/auto-tune-hyperparams.py
```

* **原理**：自動偵測您物理 CPU 的實體核心數與顯卡的可用 VRAM 總量，自適應調整搜尋空間，進行背景往復測速，尋求最優引數。完成後自動寫入 `auto-tune-results.json` 並自動執行 `rebuild-bat-files.py` 重新覆蓋生成適合您設備的最優啟動批次檔。

> [!IMPORTANT]
> **💡 AI 代理人協作與自訂硬體提示**：
> 本專案中的 [AGENTS.md](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/AGENTS.md)、[CLAUDE.md](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/CLAUDE.md)、[CONTEXT.md](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/CONTEXT.md) 以及 [tasks/](file:///D:/Workbench/AI_inference/Qwen-35BA3B-RTX3070Ti/tasks/) **本質上是為後續協作的 AI 代理人（AI Agent）準備的上下文與規範指南**。
> 當您在自己的電腦上執行完自適應調參並獲得自訂硬體的數據後，**請務必依您的真實配置更新這些文件**。這能讓接手的 AI 代理在讀取專案時，精確掌握您本地的實體核心數、顯存餘額與實測 TPS 限度，避免 AI 因載入過時上下文而做出錯誤的推理優化決策！


---


## 4. 🔧 離線備用方案與模型直接下載連結 (Manual Setup)

若您處於無網路環境或 API 限制，可手動下載並配置：

### 4.1 手動下載直接連結

請點擊以下直接連結下載所需資源，並放入對應目錄：

* **推理引擎**：[llama.cpp GitHub Releases 官方最新發行版](https://github.com/ggerganov/llama.cpp/releases/latest) (解壓後將所有 `.exe` 與 `.dll` 放入 `bin/` 資料夾)。
* **模型權重** (下載後放入 `models/` 並請**重新命名**為「標準檔名」)：
  1. [Qwen3.6-35B-A3B Q4_K_M 直接下載連結](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf) $\rightarrow$ 重新命名為：`Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf` (21.7 GB)
  2. [Qwen3.6-35B-A3B Q3_K_M 直接下載連結](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q3_K_M.gguf) $\rightarrow$ 重新命名為：`Qwen3.6-35B-A3B-MTP-Q3_K_M.gguf` (14.0 GB)
  3. [Ornith-1.0-35B Q4_K_M 直接下載連結](https://huggingface.co/bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF/resolve/main/deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf) $\rightarrow$ 重新命名為：`Ornith-1.0-35B-Q4_K_M.gguf` (21.7 GB)
  4. [Ornith-1.0-35B IQ3_M 直接下載連結](https://huggingface.co/bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF/resolve/main/deepreinforce-ai_Ornith-1.0-35B-IQ3_M.gguf) $\rightarrow$ 重新命名為：`Ornith-1.0-35B-IQ3_M.gguf` (14.0 GB)

---

## 5. 📂 專案檔案結構總覽

```text
./
├── .gitignore                     # Git 排除大檔案模型、DLL、EXE與日誌
├── start.bat                      # 統一互動式選單入口 (雙擊直接執行)
├── bin/                           # llama.cpp 核心推理引擎目錄
├── models/                        # 模型存放處
├── scripts/                       # 各模型啟動與維運腳本
│   ├── start-qwen-*.bat             # Qwen 35B 啟動腳本群
│   ├── start-ornith-*.bat           # Ornith 35B 啟動腳本群
│   ├── free-background-vram.bat     # 清理背景顯存佔用
│   └── stop-all-servers.bat         # 強制終止 llama-server
├── docs/                          # 效能分析、儀表板與優化指南
│   ├── interactive-deployment-dashboard.html           # 互動式純黑科技感儀表板
│   └── local-inference-optimization-and-tuning-report.md # 單雙通道對比與優化實驗報告 (綜合版)
├── scratch/                       # 自動化實驗與自適應調參腳本
│   ├── auto-tune-hyperparams.py     # 全自動自適應調參腳本 (一鍵執行)
│   ├── auto-tune-results.json       # 最優參數數據庫
│   ├── benchmark-ram-bandwidth-mp.py # 記憶體頻寬壓測工具
│   ├── download-model.py            # 按需下載模型工具
│   ├── rebuild-bat-files.py         # 讀取 JSON 並重建批次檔
│   └── setup-environment.py         # 環境自動診斷與引擎下載工具
└── tasks/                         # 進度與教訓記錄
    ├── todo.md                          # 進度清單
    └── lessons.md                       # 調優核心教訓總結
```
