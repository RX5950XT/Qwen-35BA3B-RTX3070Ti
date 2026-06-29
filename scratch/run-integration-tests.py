import subprocess
import time
import requests
import os
import sys
import functools

# 強制實時刷新 stdout 輸出，防止背景任務緩衝造成看不到日誌
print = functools.partial(print, flush=True)

# 鎖定工作目錄為專案根目錄
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
os.chdir(project_root)

PORT = 8888
HEALTH_URL = f"http://127.0.0.1:{PORT}/health"
COMPLETIONS_URL = f"http://127.0.0.1:{PORT}/v1/chat/completions"

def kill_all_servers():
    """Ensure no llama-server is running before or after tests."""
    print("[TEST] Running stop-all-servers.bat cleanup...")
    subprocess.run([r"scripts\stop-all-servers.bat"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

def check_server_ready(timeout_sec=45):
    """Poll health endpoint until it returns ok."""
    print("  [POLL] Waiting for server health ready...")
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            res = requests.get(HEALTH_URL, timeout=2)
            if res.status_code == 200:
                print(f"  [READY] Server health check OK (took {time.time() - start_time:.1f}s)")
                return True
        except requests.RequestException:
            pass
        time.sleep(1.5)
    print("  [TIMEOUT] Health check timeout.")
    return False

def test_inference_completion():
    """Send a simple completion request to verify inference capability."""
    print("  [API] Sending completion request...")
    payload = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "你好，請用繁體中文（臺灣）說『功能測試成功』。"}],
        "max_tokens": 16,
        "temperature": 0.2
    }
    try:
        res = requests.post(COMPLETIONS_URL, json=payload, timeout=8)
        if res.status_code == 200:
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            print(f"  [API-SUCCESS] Response: {content.strip()}")
            return True
        else:
            print(f"  [API-ERROR] Status: {res.status_code}, Response: {res.text}")
    except Exception as e:
        print(f"  [API-EXCEPTION] Failed to query endpoint: {e}")
    return False

def run_bat_test(script_path, name):
    """Run specified bat file in background and verify it starts and serves completions."""
    print(f"\n=====================================================")
    print(f" [START TEST] Model: {name}")
    print(f" Script: {script_path}")
    print(f"=====================================================")
    
    kill_all_servers()
    
    # Launch bat script asynchronously with stdin redirect to DEVNULL, bypassing 'pause' blocks
    print(f"  [LAUNCH] Launching {script_path} in background...")
    proc = subprocess.Popen([script_path], shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Check health and verify completion
    ready = check_server_ready()
    success = False
    if ready:
        success = test_inference_completion()
        
    # Clean up process handles
    try:
        proc.terminate()
        proc.kill()
    except Exception:
        pass
        
    kill_all_servers()
    return ready and success

def test_ram_bandwidth():
    """Verify that multi-process RAM bandwidth benchmark runs successfully without deadlock."""
    print(f"\n=====================================================")
    print(f" [START TEST] RAM Bandwidth Benchmark")
    print(f"=====================================================")
    try:
        # Run with fewer processes for integration test speed (e.g. 4 processes)
        print("  [RUN] Executing benchmark-ram-bandwidth-mp.py...")
        cmd = f'"{sys.executable}" scratch\\benchmark-ram-bandwidth-mp.py --quick'
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
        if res.returncode == 0:
            print("  [SUCCESS] Bandwidth benchmark ran successfully.")
            # Print last few lines of output
            lines = [l.strip() for l in res.stdout.split('\n') if l.strip()]
            for line in lines[-4:]:
                print(f"    > {line}")
            return True
        else:
            print(f"  [ERROR] Exit code {res.returncode}. Output: {res.stderr}")
    except Exception as e:
        print(f"  [EXCEPTION] RAM test failed: {e}")
    return False

def main():
    print("=====================================================")
    print("       Qwen/Ornith Deployment Integration Tests      ")
    print("=====================================================")
    
    # 1. Setup check
    print("\n[1/6] Running environment diagnostic check...")
    try:
        cmd = f'"{sys.executable}" scratch\\setup-environment.py'
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=20)
        if res.returncode == 0:
            print("  [SUCCESS] Diagnostics completed.")
        else:
            print(f"  [ERROR] Diagnostics failed: {res.stderr}")
            sys.exit(1)
    except Exception as e:
        print(f"  [EXCEPTION] Diagnostic check failed: {e}")
        sys.exit(1)

    results = {}
    
    # 2. Test Qwen Q4 Standard (Option 1)
    results["qwen_q4_standard"] = run_bat_test(r"scripts\start-qwen-35b-q4-standard.bat", "Qwen3.6-35B Q4 Standard")
    
    # 3. Test Qwen Q3 Speed (Option 3)
    results["qwen_q3_speed"] = run_bat_test(r"scripts\start-qwen-35b-q3-speed.bat", "Qwen3.6-35B Q3 Speed")
    
    # 4. Test Ornith Q4 Standard (Option 4)
    results["ornith_q4_standard"] = run_bat_test(r"scripts\start-ornith-35b-q4-standard.bat", "Ornith-1.0-35B Q4 Standard")
    
    # 5. Test RAM Bandwidth Benchmark (Option 7)
    results["ram_bandwidth"] = test_ram_bandwidth()
    
    # Summary
    print("\n=====================================================")
    print("               INTEGRATION TESTS SUMMARY             ")
    print("=====================================================")
    all_passed = True
    for test_name, passed in results.items():
        print(f"  * {test_name:<25}: {'[PASSED] SUCCESS' if passed else '[FAILED] ERROR'}")
        if not passed:
            all_passed = False
            
    print("=====================================================")
    if all_passed:
        print("  [SUCCESS] All core deployment workflows verified successfully!")
        sys.exit(0)
    else:
        print("  [FAILURE] Some integration test cases failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
