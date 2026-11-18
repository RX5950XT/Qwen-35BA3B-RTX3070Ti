# Agent 開發指引 (AGENTS.md)

本文件為後續協作的 AI Agent 提供操作指引與硬體調優速查。

## 代理人工作流
1. **任務規劃**：非簡單任務（3 個步驟以上）務必先在 `tasks/todo.md` 中進行規劃。
2. **免確認執行 (YOLO 模式)**：專案已永久啟用 YOLO 模式，請大膽執行指令以加速開發。
3. **完成驗證**：在宣佈任務完成前，必須徹底驗證。
4. **交接紀錄**：任務結束後更新 `tasks/todo.md`（≤100 行）作為開發紀錄交接文件。

## 核心調優配置 (RTX 3070 Ti 8G + Ryzen 5700X + 64GB 雙通道)
- **模型**：Qwen3.6-35B-A3B MoE (總參數 35B / 每 token 啟用 3B / 256 Experts / 41 Layers / GQA 2-Heads)
- **CPU-GPU 異構混合推理與 MoE 專家分流**：
  - 固定 `--override-tensor "ffn_.*_exps.*=CPU"` + `-ngl 99`。
  - 將 5 層 MoE 專家卸載至 GPU VRAM，即在命令列配置 **`-ncmoe 35`**，以 GPU 抹平反量化延遲。
- **投機解碼 MTP**：
  - **Q4 模型**：`--spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-p-min 0.05 --numa none` (投機 3 token 甜蜜點，TPS 提升 25%)。
  - **Q3 模型**：`--spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-p-min 0.12 --numa none` (投機 2 token 甜蜜點)。
- **KV Cache 類型靈活調度**：
  - **標準上下文 (32K 內)**：使用 **`--cache-type-k f16 --cache-type-v f16`** 以免去量化解壓縮計算延遲，釋放極限 TPS。
  - **極限長上下文 (48K)**：強制回退至 **`--cache-type-k q8_0 --cache-type-v q8_0`**，防止 VRAM 溢出觸發 PCIe Fallback。
- **執行緒、自旋鎖與 CPU 綁定**：
  - **Q4 模型**：`-t 6 -tb 8`，搭配 `--cpu-strict 0`、`--poll 50`。
  - **Q3 模型**：`-t 8 -tb 8`，搭配 `--cpu-strict 1`、`--poll 150`。
  - 統一使用 `-np 1` 限制 KV 槽併發。

## 核心物理壓測數據 (頻寬 33.46 GB/s)
| 模型 (GGUF) | 最優背景 TPS | 最優前台 TPS | MTP 接受率 | KV Cache 格式 |
|------|---------|---------|-----------|-----------|
| **Qwen3.6 Q4_K_M** | 31.05 | **35.02** | 81.4% | `f16` (16-bit) |
| **Qwen3.6 Q3_K_M** | 25.09 | **30.65** | 88.8% | `q8_0` (8-bit) |
| **Ornith-1.0 Q4_K_M** | 22.79 | **27.43** | N/A | `f16` (16-bit) |
| **Ornith-1.0 IQ3_M** | — | **22.29** | N/A | `q4_0` (4-bit) |

## 下載工具 (hf CLI)
本機已配備 `hf` (huggingface_hub CLI)。下載模型時必須使用 `hf download` 直接下載至 `models/`，並在下載完成後重新命名為腳本支援的簡短檔名。

### 常用模型下載指令：

1. **Qwen3.6-35B Q4_K_M (帶 MTP)**:
   ```cmd
   hf download unsloth/Qwen3.6-35B-A3B-MTP-GGUF Qwen3.6-35B-A3B-UD-Q4_K_M.gguf --local-dir models
   :: 下載後需重命名為：models\Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf
   ```

2. **Qwen3.6-35B Q3_K_M (帶 MTP)**:
   ```cmd
   hf download unsloth/Qwen3.6-35B-A3B-MTP-GGUF Qwen3.6-35B-A3B-UD-Q3_K_M.gguf --local-dir models
   :: 下載後需重命名為：models\Qwen3.6-35B-A3B-MTP-Q3_K_M.gguf
   ```

3. **Ornith-1.0-35B Q4_K_M (無 MTP)**:
   ```cmd
   hf download bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf --local-dir models
   :: 下載後需重命名為：models\Ornith-1.0-35B-Q4_K_M.gguf
   ```

4. **Ornith-1.0-35B IQ3_M (無 MTP)**:
   ```cmd
   hf download bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF deepreinforce-ai_Ornith-1.0-35B-IQ3_M.gguf --local-dir models
   :: 下載後需重命名為：models\Ornith-1.0-35B-IQ3_M.gguf
   ```
