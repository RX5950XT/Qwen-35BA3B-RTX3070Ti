import os
import sys

# 鎖定工作目錄為專案根目錄，防止執行路徑偏移
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
os.chdir(project_root)

# Model mapping database
MODEL_DB = {
    "qwen-q4": {
        "repo": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF",
        "file": "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
        "target": "Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf",
        "size": "21.7 GB"
    },
    "qwen-q3": {
        "repo": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF",
        "file": "Qwen3.6-35B-A3B-UD-Q3_K_M.gguf",
        "target": "Qwen3.6-35B-A3B-MTP-Q3_K_M.gguf",
        "size": "14.0 GB"
    },
    "ornith-q4": {
        "repo": "bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF",
        "file": "deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf",
        "target": "Ornith-1.0-35B-Q4_K_M.gguf",
        "size": "21.7 GB"
    },
    "ornith-q3": {
        "repo": "bartowski/deepreinforce-ai_Ornith-1.0-35B-GGUF",
        "file": "deepreinforce-ai_Ornith-1.0-35B-IQ3_M.gguf",
        "target": "Ornith-1.0-35B-IQ3_M.gguf",
        "size": "14.0 GB"
    }
}

def main():
    if len(sys.argv) < 2:
        print("[ERROR] Missing model key argument.")
        sys.exit(1)
        
    model_key = sys.argv[1].lower()
    if model_key not in MODEL_DB:
        print(f"[ERROR] Invalid model key: {model_key}")
        sys.exit(1)
        
    cfg = MODEL_DB[model_key]
    models_dir = "models"
    os.makedirs(models_dir, exist_ok=True)
    
    target_path = os.path.join(models_dir, cfg["target"])
    
    if os.path.exists(target_path):
        print(f"[INFO] Model {cfg['target']} is already downloaded.")
        sys.exit(0)
        
    print("=====================================================")
    print(f"      Auto-Downloading Model: {cfg['target']}")
    print(f"      Repository: {cfg['repo']}")
    print(f"      Est. Size : {cfg['size']}")
    print("=====================================================")
    print("[INFO] Setting up huggingface_hub library...")
    
    # Ensure huggingface_hub is installed
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[INFO] Installing huggingface_hub via pip...")
        import subprocess
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "huggingface_hub"], check=True)
            from huggingface_hub import hf_hub_download
        except Exception as e:
            print(f"[ERROR] Failed to install huggingface_hub: {e}")
            print("[ERROR] Please install dependency manually: pip install huggingface_hub")
            sys.exit(1)
            
    print("\n[INFO] Starting download. This may take a while depending on your bandwidth...")
    print("[INFO] Resumable download is active. (Close console to pause, run again to resume)")
    
    try:
        # Download file using huggingface_hub native API with beautiful progress bar
        downloaded_path = hf_hub_download(
            repo_id=cfg["repo"],
            filename=cfg["file"],
            local_dir=models_dir,
            local_dir_use_symlinks=False
        )
        
        # Rename file to target name if it downloaded as the original name
        orig_download_path = os.path.join(models_dir, cfg["file"])
        if os.path.exists(orig_download_path) and orig_download_path != target_path:
            try:
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.rename(orig_download_path, target_path)
            except PermissionError as perm_err:
                print(f"\n[WARNING] PermissionError: {perm_err}")
                print(f"[WARNING] Could not rename {orig_download_path} to {target_path} because the file is locked by a running process.")
                print("[WARNING] Please close any running llama-server.exe processes and rename the file manually.")
                sys.exit(0)
            
        print("\n=====================================================")
        print(f"  [SUCCESS] Model downloaded and configured successfully!")
        print(f"  [PATH] {target_path}")
        print("=====================================================")
        
    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")
        print("[ERROR] Please try running the download command manually using hf CLI.")
        sys.exit(1)

if __name__ == "__main__":
    main()
