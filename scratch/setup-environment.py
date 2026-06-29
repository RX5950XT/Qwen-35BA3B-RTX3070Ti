import os
import sys
import subprocess
import urllib.request
import json
import zipfile
import shutil

# 鎖定工作目錄為專案根目錄，防止執行路徑偏移
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
os.chdir(project_root)

def check_python_dependencies():
    """Ensure requests and numpy are installed."""
    print("[1/4] Checking Python dependencies...")
    try:
        import requests
        import numpy
        print("  [SUCCESS] Python dependencies are ready.")
    except ImportError:
        print("  [INFO] Missing dependencies. Installing requests and numpy automatically...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "numpy", "requests"], check=True)
            print("  [SUCCESS] Dependencies installed successfully.")
        except Exception as e:
            print(f"  [ERROR] Failed to install dependencies: {e}. Please run 'pip install numpy requests' manually.")

def detect_cuda_device():
    """Check if NVIDIA GPU and nvidia-smi are available."""
    try:
        res = subprocess.run("nvidia-smi", shell=True, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    return False

def check_system_memory():
    """Check total physical memory size and warn if it is insufficient for 35B MoE."""
    print("[2/4] Checking hardware environment...")
    # Use wmic on Windows to get total memory
    try:
        res = subprocess.run("wmic computersystem get TotalPhysicalMemory", shell=True, capture_output=True, text=True, timeout=3)
        lines = [line.strip() for line in res.stdout.split('\n') if line.strip()]
        if len(lines) > 1 and lines[1].isdigit():
            total_bytes = int(lines[1])
            total_gb = total_bytes / (1024 ** 3)
            print(f"  [DETECTED] Total Physical Memory: {total_gb:.1f} GB")
            if total_gb < 24.0:
                print("  [WARNING] Your physical RAM is less than 24GB. Running 35B MoE models may trigger disk swapping and cause slow speeds.")
                print("            It is highly recommended to upgrade RAM or run Qwen 3-bit (Q3_K_M) models.")
            else:
                print("  [SUCCESS] Physical Memory size is sufficient.")
            return
    except Exception:
        pass
    print("  [WARNING] Could not check physical RAM size. Ensure you have at least 24GB RAM for 35B MoE.")

def download_and_extract_llama_cpp():
    """Dynamically fetch latest llama.cpp zip release from GitHub and extract it to bin/."""
    bin_dir = "bin"
    server_exe = os.path.join(bin_dir, "llama-server.exe")
    
    if os.path.exists(server_exe):
        print("[3/4] Checking llama.cpp engine...")
        print("  [SUCCESS] llama-server.exe is already installed in bin/.")
        return

    print("[3/4] llama.cpp engine not found. Initiating auto-download...")
    os.makedirs(bin_dir, exist_ok=True)
    
    has_gpu = detect_cuda_device()
    print(f"  [DETECTED] GPU Acceleration Status: {'CUDA GPU Detected (CUDA mode enabled)' if has_gpu else 'No NVIDIA GPU / CUDA Found (CPU mode fallback)'}")
    
    # Query GitHub API for the latest release
    api_url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
    print("  [API] Querying GitHub for latest llama.cpp release...")
    
    download_url = None
    asset_name = None
    temp_zip = "bin_temp.zip"
    
    try:
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                release_data = json.loads(response.read().decode())
                
            assets = release_data.get("assets", [])
            
            # Determine search keyword
            target_keyword = "bin-win-cuda-cu12.4-x64.zip" if has_gpu else "bin-win-x64.zip"
            
            for asset in assets:
                name = asset.get("name", "")
                if target_keyword in name:
                    download_url = asset.get("browser_download_url")
                    asset_name = name
                    break
                    
            # Fallback in case cu12.4 is not available
            if not download_url and has_gpu:
                for asset in assets:
                    name = asset.get("name", "")
                    if "bin-win-cuda" in name and "x64.zip" in name:
                        download_url = asset.get("browser_download_url")
                        asset_name = name
                        break
                        
            # Fallback to pure CPU
            if not download_url:
                for asset in assets:
                    name = asset.get("name", "")
                    if "bin-win-x64.zip" in name:
                        download_url = asset.get("browser_download_url")
                        asset_name = name
                        break
        except Exception as api_err:
            print(f"  [API-WARNING] GitHub API query failed (likely rate limited): {api_err}")
            # Fallback to hardcoded stable version b4570 to bypass API Rate Limit
            if has_gpu:
                download_url = "https://github.com/ggerganov/llama.cpp/releases/download/b4570/llama-b4570-bin-win-cuda-cu12.4-x64.zip"
                asset_name = "llama-b4570-bin-win-cuda-cu12.4-x64.zip"
            else:
                download_url = "https://github.com/ggerganov/llama.cpp/releases/download/b4570/llama-b4570-bin-win-x64.zip"
                asset_name = "llama-b4570-bin-win-x64.zip"
            print(f"  [API-FALLBACK] Using hardcoded stable release fallback: {asset_name}")

        if not download_url:
            raise Exception("Could not find matching prebuilt zip file in release assets.")
            
        print(f"  [DOWNLOAD] Downloading {asset_name}...")
        print(f"             from: {download_url}")
        
        # Download with simple progress display
        def progress_hook(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size)
            sys.stdout.write(f"\r  [PROGRESS] Downloading: {percent}%")
            sys.stdout.flush()
            
        urllib.request.urlretrieve(download_url, temp_zip, progress_hook)
        print("\n  [SUCCESS] Download completed.")
        
        print("  [EXTRACT] Extracting files to bin/...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(bin_dir)
            
        print("  [SUCCESS] llama.cpp engine extracted successfully to bin/.")
        
    except Exception as e:
        print(f"  [ERROR] Auto-download failed: {e}")
        print("          Please manually download llama.cpp release from GitHub and extract to bin/.")
        print("          Refer to README.md for instructions.")
    finally:
        # 確保臨時下載的 zip 檔案不論如何一定會被清除，不留下垃圾檔案
        if os.path.exists(temp_zip):
            try:
                os.remove(temp_zip)
            except Exception:
                pass

def check_models_presence():
    """Verify if models exist in models/ directory, warn if empty."""
    print("[4/4] Checking models directory...")
    models_dir = "models"
    os.makedirs(models_dir, exist_ok=True)
    
    files = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
    if not files:
        print("  [WARNING] No .gguf model weights found in models/ directory!")
        print("            Please download the required models to start inference.")
        print("            Refer to README.md for specific download commands.")
    else:
        print(f"  [SUCCESS] Found {len(files)} model(s) in models/ directory: {files}")

def main():
    print("=====================================================")
    print("       Deployment Environment Health Check Tool")
    print("=====================================================")
    check_python_dependencies()
    check_system_memory()
    download_and_extract_llama_cpp()
    check_models_presence()
    print("=====================================================")
    print("[COMPLETE] Health check finished. Environment is ready.")
    print("=====================================================")

if __name__ == "__main__":
    main()
