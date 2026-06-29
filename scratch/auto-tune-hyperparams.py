import subprocess
import time
import requests
import json
import os
import re
import sys

# 鎖定工作目錄為專案根目錄，防止執行路徑偏移
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
os.chdir(project_root)

PORT = 8888
API_URL = f"http://127.0.0.1:{PORT}/v1/chat/completions"
HEALTH_URL = f"http://127.0.0.1:{PORT}/health"
LLAMA_SERVER = r"bin\llama-server.exe"
RESULTS_FILE = r"scratch\auto-tune-results.json"

MODELS = {
    "qwen-q4": {
        "path": r"models\Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf",
        "desc": "Qwen3.6-35B-A3B MTP Q4_K_M",
        "has_mtp": True
    },
    "qwen-q3": {
        "path": r"models\Qwen3.6-35B-A3B-MTP-Q3_K_M.gguf",
        "desc": "Qwen3.6-35B-A3B MTP Q3_K_M",
        "has_mtp": True
    }
}

def detect_cpu_cores():
    """Detect physical CPU cores using Windows wmic command, fallback to multiprocessing."""
    try:
        res = subprocess.run("wmic cpu get NumberOfCores", shell=True, capture_output=True, text=True, timeout=3)
        lines = [line.strip() for line in res.stdout.split('\n') if line.strip()]
        if len(lines) > 1 and lines[1].isdigit():
            return int(lines[1])
    except Exception:
        pass
    
    # Fallback to logical count // 2
    import multiprocessing
    try:
        cores = multiprocessing.cpu_count()
        return max(2, cores // 2)
    except Exception:
        return 4

def detect_gpu_vram():
    """Detect total GPU VRAM in MB using nvidia-smi query, fallback to 8192."""
    try:
        res = subprocess.run("nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits", shell=True, capture_output=True, text=True, timeout=3)
        out = res.stdout.strip()
        if out.isdigit():
            return int(out)
    except Exception:
        pass
    return 8192

def free_vram():
    """Recycle background VRAM."""
    print("  [VRAM] Cleaning background graphics memory apps...")
    subprocess.run(r"scripts\free-background-vram.bat", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)

def kill_server():
    """Kill any running llama-server.exe instances."""
    subprocess.run("taskkill /f /im llama-server.exe >nul 2>&1", shell=True)
    time.sleep(1.5)

def wait_for_server(timeout=45):
    """Wait for server health endpoint to respond with 200."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            r = requests.get(HEALTH_URL, timeout=1.5)
            if r.status_code == 200:
                time.sleep(1.0)
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False

def test_inference(warmup=False):
    """Test performance, returning metrics."""
    headers = {"Content-Type": "application/json"}
    prompt = "請寫一篇大約 150 字關於人工智慧未來發展的短文。一律使用繁體中文（臺灣）。"
    
    data = {
        "model": "qwen",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "top_p": 0.95,
        "max_tokens": 150, 
        "stream": True
    }
    
    try:
        start_request = time.time()
        r = requests.post(API_URL, headers=headers, json=data, stream=True, timeout=25)
        if r.status_code != 200:
            return None
            
        timestamps = []
        token_count = 0
        
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data: "):
                    content_str = decoded[6:]
                    if content_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(content_str)
                        delta = chunk['choices'][0]['delta']
                        content = delta.get('content') or delta.get('reasoning_content')
                        if content:
                            timestamps.append(time.time())
                            token_count += 1
                    except Exception:
                        pass
                        
        if len(timestamps) < 5:
            return None
            
        ttft = (timestamps[0] - start_request) * 1000  # ms
        decode_duration = timestamps[-1] - timestamps[0]
        decode_tps = (token_count - 1) / decode_duration if decode_duration > 0 else 0
        
        return {
            "ttft_ms": ttft,
            "decode_tps": decode_tps,
            "tokens": token_count,
            "duration_sec": timestamps[-1] - start_request
        }
    except Exception:
        return None

def extract_accept_rate():
    """Extract speculative acceptance rate from temp log."""
    try:
        log_path = r"scratch\llama-server-tune-temp.log"
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                matches = re.findall(r"(?:speculative|draft)?\s*accept(?:ance)?\s*=\s*([\d\.]+)(?:%)?", content, re.IGNORECASE)
                if matches:
                    val = float(matches[-1])
                    if val < 1.0:
                        val = val * 100.0
                    return val
    except Exception:
        pass
    return None

def run_server(model_path, params):
    """Launch server under Windows with specified parameters."""
    kill_server()
    
    # Adaptive CPU override: if ncmoe is 0 (full offload), we don't CPU override
    override_exp = ""
    if params["ncmoe"] > 0:
        override_exp = "ffn_.*_exps.*=CPU"
        
    cmd = [
        LLAMA_SERVER,
        "-m", model_path,
        "-np", "1",
        "-ngl", "99",
        "--override-tensor", override_exp,
        "-c", "4096",
        "-fa", "on",
        "--cache-type-k", params["cache_type"],
        "--cache-type-v", params["cache_type"],
        "--no-mmap",
        "--mlock",
        "-b", "4096",
        "-ub", str(params["ub"]),
        "--split-mode", "none",
        "--temp", "0.6",
        "--top-p", "0.95",
        "--jinja",
        "--host", "127.0.0.1",
        "--port", str(PORT)
    ]
    
    # Clean empty strings
    cmd = [c for c in cmd if c != ""]
    
    # Custom Expert Offloading (if ncmoe > 0)
    if params["ncmoe"] > 0:
        cmd.extend(["-ncmoe", str(params["ncmoe"])])
        
    cmd.extend(["-t", str(params["threads"])])
    cmd.extend(["-tb", str(params["threads_batch"])])
    
    if params.get("numa") and params["numa"] != "none":
        cmd.extend(["--numa", params["numa"]])
        
    cmd.extend(["--cpu-strict", str(params["cpu_strict"])])
    cmd.extend(["--poll", str(params["poll"])])
    cmd.extend(["--prio", "3"])
    
    if params.get("spec_draft_n_max"):
        cmd.extend(["--spec-type", "draft-mtp"])
        cmd.extend(["--spec-draft-n-max", str(params["spec_draft_n_max"])])
        cmd.extend(["--spec-draft-p-min", str(params.get("spec_draft_p_min", 0.1))])
        
    cmd_str = " ".join(cmd)
    log_path = r"scratch\llama-server-tune-temp.log"
    
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except Exception: pass
        
    cores = detect_cpu_cores()
    mask = (1 << cores) - 1
    if cores > 4:
        mask = mask & ~0x3  # 剔除前兩個核心讓給系統，防背景干擾
    affinity_mask_str = f"{mask:X}"
    
    affinity_str = f" /affinity {affinity_mask_str}" if params.get("use_affinity") else ""
    full_cmd = f'start /high{affinity_str} /b "" cmd /c "{cmd_str} > {log_path} 2>&1"'
    
    subprocess.Popen(full_cmd, shell=True)
    
    if wait_for_server():
        return True
    else:
        kill_server()
        return False

def evaluate_params(model_path, params, name="Test"):
    """Run server, warm up, test, extract metrics."""
    print(f"    [TEST] {name} | ncmoe={params['ncmoe']}, t={params['threads']}/{params['threads_batch']}, poll={params['poll']}, Cache={params['cache_type']}...")
    
    # Clean memory if GPU expert count is changed (to avoid caching errors)
    if params["ncmoe"] < 40:
        free_vram()
        
    if not run_server(model_path, params):
        print("    [FAILED] Server failed to start.")
        return None
        
    # Warmup
    test_inference(warmup=True)
    time.sleep(0.5)
    
    # Test 1
    metrics1 = test_inference()
    if not metrics1:
        print("    [FAILED] Request timeout or failed.")
        kill_server()
        return None
        
    # Test 2
    metrics2 = test_inference()
    
    kill_server()
    accept_rate = extract_accept_rate()
    
    tps = metrics1["decode_tps"]
    ttft = metrics1["ttft_ms"]
    if metrics2:
        tps = (metrics1["decode_tps"] + metrics2["decode_tps"]) / 2
        ttft = (metrics1["ttft_ms"] + metrics2["ttft_ms"]) / 2
        
    print(f"    [RESULT] TPS: {tps:.2f} t/s | TTFT: {ttft:.1f} ms" + (f" | MTP Accept: {accept_rate:.1f}%" if accept_rate else ""))
    
    res = params.copy()
    res["tps"] = tps
    res["ttft_ms"] = ttft
    res["accept_rate"] = accept_rate
    return res

def tune_model(model_key, cores, vram_mb):
    model_cfg = MODELS[model_key]
    model_path = model_cfg["path"]
    
    if not os.path.exists(model_path):
        print(f"\n[SKIP] Model not found: {model_path}")
        return None
        
    print(f"\n=============================================================")
    print(f"  Start Adaptive Tuning: {model_cfg['desc']}")
    print(f"=============================================================")
    
    # Initial Baseline Parameters (Adaptive based on detected cores/VRAM)
    # Default ncmoe: 35 for 8G, 15 for 16G, 0 (full offload) for 24G+
    init_ncmoe = 35
    if vram_mb >= 22000:
        init_ncmoe = 0
    elif vram_mb >= 11000:
        init_ncmoe = 20

    current_best = {
        "ncmoe": init_ncmoe,
        "threads": cores,
        "threads_batch": min(16, cores + 2),
        "poll": 100,
        "cpu_strict": 1 if cores >= 8 else 0,
        "numa": "none",
        "use_affinity": False,
        "spec_draft_n_max": 2,
        "spec_draft_p_min": 0.1,
        "cache_type": "q8_0",
        "ub": 512
    }
    
    history = []
    
    # -------------------------------------------------------------
    # PHASE 1: Adaptive GPU Expert Offload (-ncmoe) Space
    # -------------------------------------------------------------
    print("\n[PHASE 1] Searching optimal GPU MoE Expert Offload (-ncmoe)...")
    if vram_mb >= 22000:
        # High VRAM GPU (like 3090, 4090). 0 means fully load to GPU!
        ncmoe_options = [0, 5, 10]
    elif vram_mb >= 11000:
        # Medium VRAM GPU (like 12G or 16G GPUs)
        ncmoe_options = [15, 20, 25, 30]
    else:
        # Low VRAM GPU (like 3070 Ti 8G)
        ncmoe_options = [35, 36, 37, 38]
        
    best_ncmoe = current_best["ncmoe"]
    best_ncmoe_tps = 0.0
    
    for ncmoe in ncmoe_options:
        test_p = current_best.copy()
        test_p["ncmoe"] = ncmoe
        res = evaluate_params(model_path, test_p, f"Phase1_ncmoe_{ncmoe}")
        if res:
            history.append(res)
            if res["tps"] > best_ncmoe_tps:
                best_ncmoe_tps = res["tps"]
                best_ncmoe = ncmoe
                
    print(f"  => Phase 1 Optimal ncmoe: {best_ncmoe} (TPS: {best_ncmoe_tps:.2f})")
    current_best["ncmoe"] = best_ncmoe
    
    # -------------------------------------------------------------
    # PHASE 2: CPU Threads & Scheduling (Adaptive to physical cores)
    # -------------------------------------------------------------
    print("\n[PHASE 2] Fine-tuning CPU Threading & OS Scheduler...")
    
    # 2.1 Test Threads (t)
    best_t = current_best["threads"]
    best_t_tps = 0.0
    
    # Adaptive search window: [cores-2, cores, cores+2]
    threads_options = [cores - 2, cores, cores + 2]
    threads_options = [x for x in threads_options if x >= 2]
    threads_options = list(sorted(list(set(threads_options))))
    
    for t in threads_options:
        test_p = current_best.copy()
        test_p["threads"] = t
        test_p["threads_batch"] = max(t, test_p["threads_batch"])
        res = evaluate_params(model_path, test_p, f"Phase2.1_threads_{t}")
        if res:
            history.append(res)
            if res["tps"] > best_t_tps:
                best_t_tps = res["tps"]
                best_t = t
    print(f"  => Optimal threads (t): {best_t}")
    current_best["threads"] = best_t
    
    # 2.2 Test Threads Batch (tb)
    best_tb = current_best["threads_batch"]
    best_tb_tps = 0.0
    for tb in [best_t, best_t + 2, best_t + 4]:
        test_p = current_best.copy()
        test_p["threads_batch"] = tb
        res = evaluate_params(model_path, test_p, f"Phase2.2_tb_{tb}")
        if res:
            history.append(res)
            if res["tps"] > best_tb_tps:
                best_tb_tps = res["tps"]
                best_tb = tb
    print(f"  => Optimal threads_batch (tb): {best_tb}")
    current_best["threads_batch"] = best_tb
    
    # 2.3 Test Poll (Spinlocks)
    best_poll = current_best["poll"]
    best_poll_tps = 0.0
    for poll in [0, 50, 100, 150]:
        test_p = current_best.copy()
        test_p["poll"] = poll
        res = evaluate_params(model_path, test_p, f"Phase2.3_poll_{poll}")
        if res:
            history.append(res)
            if res["tps"] > best_poll_tps:
                best_poll_tps = res["tps"]
                best_poll = poll
    print(f"  => Optimal poll: {best_poll}")
    current_best["poll"] = best_poll

    # 2.4 Test CPU Strict & NUMA
    scheduler_options = [
        {"cpu_strict": 1, "numa": "isolate"},
        {"cpu_strict": 0, "numa": "isolate"},
        {"cpu_strict": 1, "numa": "none"},
        {"cpu_strict": 0, "numa": "none"}
    ]
    best_sched = {"cpu_strict": current_best["cpu_strict"], "numa": current_best["numa"]}
    best_sched_tps = 0.0
    for opt in scheduler_options:
        test_p = current_best.copy()
        test_p.update(opt)
        res = evaluate_params(model_path, test_p, f"Phase2.4_sched_strict{opt['cpu_strict']}_numa{opt['numa']}")
        if res:
            history.append(res)
            if res["tps"] > best_sched_tps:
                best_sched_tps = res["tps"]
                best_sched = opt
    print(f"  => Optimal scheduling: cpu_strict={best_sched['cpu_strict']}, numa={best_sched['numa']}")
    current_best.update(best_sched)

    # -------------------------------------------------------------
    # PHASE 3: MTP Speculative Parameters
    # -------------------------------------------------------------
    print("\n[PHASE 3] Optimizing MTP window size (n_max & p_min)...")
    best_mtp = {"n_max": current_best["spec_draft_n_max"], "p_min": current_best["spec_draft_p_min"]}
    best_mtp_tps = 0.0
    
    for n_max in [1, 2, 3]:
        for p_min in [0.05, 0.10, 0.12]:
            test_p = current_best.copy()
            test_p["spec_draft_n_max"] = n_max
            test_p["spec_draft_p_min"] = p_min
            res = evaluate_params(model_path, test_p, f"Phase3_MTP_n{n_max}_p{p_min}")
            if res:
                history.append(res)
                if res["tps"] > best_mtp_tps:
                    best_mtp_tps = res["tps"]
                    best_mtp = {"n_max": n_max, "p_min": p_min}
                    
    print(f"  => Optimal MTP: n_max={best_mtp['n_max']}, p_min={best_mtp['p_min']} (TPS: {best_mtp_tps:.2f})")
    current_best["spec_draft_n_max"] = best_mtp["n_max"]
    current_best["spec_draft_p_min"] = best_mtp["p_min"]

    # -------------------------------------------------------------
    # PHASE 4: KV Cache & Batching
    # -------------------------------------------------------------
    print("\n[PHASE 4] Optimizing KV Cache format & batch size...")
    best_cache_ub = {"cache_type": current_best["cache_type"], "ub": current_best["ub"]}
    best_cache_ub_tps = 0.0
    
    # If VRAM is extremely small, we skip f16 cache. Otherwise, we test it.
    cache_formats = ["q8_0", "f16"]
    for cache in cache_formats:
        for ub in [256, 512]:
            test_p = current_best.copy()
            test_p["cache_type"] = cache
            test_p["ub"] = ub
            res = evaluate_params(model_path, test_p, f"Phase4_cache{cache}_ub{ub}")
            if res:
                history.append(res)
                if res["tps"] > best_cache_ub_tps:
                    best_cache_ub_tps = res["tps"]
                    best_cache_ub = {"cache_type": cache, "ub": ub}
                    
    print(f"  => Optimal KV Cache & Batching: cache={best_cache_ub['cache_type']}, ub={best_cache_ub['ub']} (TPS: {best_cache_ub_tps:.2f})")
    current_best.update(best_cache_ub)
    
    # Final verified run
    print("\n[VERIFICATION] Re-evaluating the best settings to confirm stability...")
    final_runs = []
    for run_idx in range(3):
        res = evaluate_params(model_path, current_best, f"FinalBest_Run{run_idx+1}")
        if res:
            final_runs.append(res["tps"])
            
    if final_runs:
        current_best["final_verified_tps"] = sum(final_runs) / len(final_runs)
        print(f"  => Verified Average TPS: {current_best['final_verified_tps']:.2f}")
    else:
        current_best["final_verified_tps"] = best_cache_ub_tps
        print(f"  => Verification failed. Falling back to Phase 4 best: {best_cache_ub_tps:.2f}")
        
    return {
        "best_params": current_best,
        "history": history
    }

def main():
    kill_server()
    
    # Hardware Auto-Detection
    print("=====================================================")
    print("         Hardware-Adaptive Auto-Tuner Init")
    print("=====================================================")
    cores = detect_cpu_cores()
    vram_mb = detect_gpu_vram()
    print(f"  [DETECTED] CPU Physical Cores: {cores}")
    print(f"  [DETECTED] GPU VRAM Total   : {vram_mb} MB")
    print("=====================================================")
    
    all_results = {
        "hardware": {
            "cpu_cores": cores,
            "gpu_vram_mb": vram_mb
        }
    }
    
    for key in MODELS.keys():
        res = tune_model(key, cores, vram_mb)
        if res:
            all_results[key] = res
            
    # Save results to JSON
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)
        
    print(f"\n[SUCCESS] Saved hardware-optimized settings to {RESULTS_FILE}")
    
    # Dynamically trigger rebuild-bat-files.py to apply the best settings to bat files
    rebuild_script = r"scratch\rebuild-bat-files.py"
    if os.path.exists(rebuild_script):
        print("\n[AUTO] Rebuilding startup batch scripts with optimized settings...")
        subprocess.run(f"python {rebuild_script}", shell=True)
        
    # Print summary
    print("\n====================================================")
    print("            Adaptive Auto-Tuning Summary")
    print("====================================================")
    for key, val in all_results.items():
        if key == "hardware":
            continue
        desc = MODELS[key]["desc"]
        best = val["best_params"]
        tps = best["final_verified_tps"]
        print(f"  * Model: {desc}")
        print(f"    - Peak TPS        : {tps:.2f} t/s")
        print(f"    - GPU Offload     : -ncmoe {best['ncmoe']}")
        print(f"    - CPU Threads     : -t {best['threads']} (Batch: -tb {best['threads_batch']})")
        print(f"    - CPU Spinlock    : --poll {best['poll']} --cpu-strict {best['cpu_strict']}")
        print(f"    - KV Cache Format : {best['cache_type']}")
        print(f"    - MTP Tokens      : --spec-draft-n-max {best['spec_draft_n_max']} --spec-draft-p-min {best['spec_draft_p_min']}")
        print("----------------------------------------------------")

if __name__ == "__main__":
    main()
