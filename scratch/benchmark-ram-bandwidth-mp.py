import numpy as np
import time
import multiprocessing as mp
import sys

# 每個進程分配的元素數量
# 64M float64 = 512 MB (8 bytes per float64)
# 每個進程 512MB，若 8 進程共 4GB，對系統記憶體壓力適中
ELEMENTS_PER_PROCESS = 67108864 
SIZE_GB = (ELEMENTS_PER_PROCESS * 8) / (1024**3) # 0.5 GB

def read_worker(proc_id, barrier, return_dict):
    A = None
    try:
        # 分配並初始化記憶體
        A = np.ones(ELEMENTS_PER_PROCESS, dtype=np.float64)
        # 暖身
        _ = A.sum()
    except MemoryError:
        return_dict[proc_id] = (0.0, 0.0)
    finally:
        # 確保不論是否分配成功，一定會呼叫 barrier.wait()，防死鎖
        barrier.wait()
        
    if A is None:
        return
    
    # 開始測試
    t0 = time.perf_counter()
    s = A.sum()
    t1 = time.perf_counter()
    
    elapsed = t1 - t0
    return_dict[proc_id] = (elapsed, s)

def copy_worker(proc_id, barrier, return_dict):
    A = None
    B = None
    try:
        A = np.ones(ELEMENTS_PER_PROCESS, dtype=np.float64)
        B = np.zeros(ELEMENTS_PER_PROCESS, dtype=np.float64)
        # 暖身
        np.copyto(B, A)
    except MemoryError:
        return_dict[proc_id] = (0.0, 0.0)
    finally:
        # 確保不論是否分配成功，一定會呼叫 barrier.wait()，防死鎖
        barrier.wait()
        
    if A is None or B is None:
        return
    
    t0 = time.perf_counter()
    np.copyto(B, A)
    t1 = time.perf_counter()
    
    elapsed = t1 - t0
    # 確保 B 的內容確實被寫入，防最佳化
    verify = B[0]
    return_dict[proc_id] = (elapsed, verify)

def run_benchmark(num_processes, mode='read'):
    barrier = mp.Barrier(num_processes)
    manager = mp.Manager()
    return_dict = manager.dict()
    
    processes = []
    for i in range(num_processes):
        if mode == 'read':
            p = mp.Process(target=read_worker, args=(i, barrier, return_dict))
        else:
            p = mp.Process(target=copy_worker, args=(i, barrier, return_dict))
        processes.append(p)
        p.start()
        
    for p in processes:
        p.join()
        
    # 計算並行時間與總數據量
    results = return_dict.values()
    if not results or any(r[0] == 0.0 for r in results):
        return 0.0
        
    elapseds = [r[0] for r in results]
    # 對於並行任務，總頻寬 = 總數據量 / 最大耗時 (即最晚完成的那個)
    max_elapsed = max(elapseds)
    
    if mode == 'read':
        total_data_gb = SIZE_GB * num_processes # 唯讀總量
    else:
        total_data_gb = SIZE_GB * 2 * num_processes # 讀+寫總量
        
    bw = total_data_gb / max_elapsed
    return bw

def main():
    print("====================================================")
    print(" Multiprocessing Memory Bandwidth Benchmark (RAM)  ")
    print("====================================================")
    
    # 支援 --quick 快速整合測試模式
    is_quick = "--quick" in sys.argv
    
    print(f"Each process allocates {SIZE_GB*1024:.0f} MB (A.sum() = 512MB, np.copyto = 1GB)")
    print("-" * 50)
    
    cores_to_test = [2] if is_quick else [1, 2, 4, 6, 8, 12]
    repeats = 1 if is_quick else 3
    # 取得系統 CPU 核心數
    cpu_count = mp.cpu_count()
    print(f"System logical CPU cores detected: {cpu_count}")
    print("------------------------------------------------------------")
    print(f"{'Processes':<12}{'Read BW (GB/s)':<18}{'Copy BW (GB/s)':<18}")
    print("------------------------------------------------------------")
    
    best_read_bw = 0.0
    best_copy_bw = 0.0
    
    for n in cores_to_test:
        if n > cpu_count:
            continue
            
        # 測試 Read
        read_bws = []
        for _ in range(repeats): 
            bw = run_benchmark(n, mode='read')
            read_bws.append(bw)
        avg_read = max(read_bws) # 取最優頻寬
        
        # 測試 Copy
        copy_bws = []
        for _ in range(repeats):
            bw = run_benchmark(n, mode='copy')
            copy_bws.append(bw)
        avg_copy = max(copy_bws)
        
        print(f"{n:<12}{avg_read:<18.2f}{avg_copy:<18.2f}")
        
        if avg_read > best_read_bw:
            best_read_bw = avg_read
        if avg_copy > best_copy_bw:
            best_copy_bw = avg_copy
            
    print("====================================================")
    print(f"Peak Read Bandwidth: {best_read_bw:.2f} GB/s")
    print(f"Peak Copy Bandwidth: {best_copy_bw:.2f} GB/s")
    print("------------------------------------------------------------")
    
    # 理論分析
    theoretical_single = 25.6 # DDR4-3200 單通道理論上限
    theoretical_dual = 51.2   # DDR4-3200 雙通道理論上限
    
    print(f"DDR4-3200 Single-Channel Theoretical Max: {theoretical_single:.2f} GB/s")
    print(f"DDR4-3200 Dual-Channel Theoretical Max: {theoretical_dual:.2f} GB/s")
    print("-" * 50)
    
    # 雙通道判斷邏輯
    # 單通道實測極限通常不超過 21-22 GB/s。
    # 如果 Peak Copy 或 Peak Read 突破 26 GB/s，說明必定已經啟用雙通道！
    achieved_bw = max(best_read_bw, best_copy_bw)
    
    if achieved_bw >= 26.0:
        print("[Analysis] SUCCESS: Dual-channel mode is CONFIRMED and ACTIVE!")
        print(f"Your memory bandwidth reached {achieved_bw:.2f} GB/s, which exceeds the physical limit of single-channel (25.6 GB/s).")
        efficiency = (achieved_bw / theoretical_dual) * 100
        print(f"Achieved Efficiency vs Dual-Channel Theoretical Max: {efficiency:.1f}%")
        print("\nThis unlocks full memory bandwidth and will significantly improve LLM CPU inference speed.")
    else:
        print("[Analysis] WARNING: Memory bandwidth suggests Single-Channel performance.")
        print(f"Peak bandwidth {achieved_bw:.2f} GB/s is below single-channel limit.")
        print("Please check if the memory modules are installed in correct slots for dual-channel (usually DIMM 2 and DIMM 4).")

if __name__ == "__main__":
    # Windows multiprocessing require spawn protection
    mp.freeze_support()
    main()
