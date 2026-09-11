#!/usr/bin/env python3
"""
NetWatch Model Import Utility.
Extracts and registers model files from 'netwatch_trained_models.zip'
into the local directory structure.
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

def import_models(zip_path: str = "netwatch_trained_models.zip"):
    p = Path(zip_path)
    if not p.exists():
        # Check Downloads folder
        downloads_path = Path.home() / "Downloads" / "netwatch_trained_models.zip"
        if downloads_path.exists():
            p = downloads_path
            print(f"📦 Found model package in Downloads: {p}")
        else:
            print(f"❌ Error: Model zip file not found at '{zip_path}' or in '~/Downloads/netwatch_trained_models.zip'")
            print("👉 Please download 'netwatch_trained_models.zip' from Google Colab and place it in the project root or Downloads.")
            return False

    print(f"Extracting {p}...")
    extract_temp = Path("temp_models_extract")
    if extract_temp.exists():
        shutil.rmtree(extract_temp)
    extract_temp.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(p, 'r') as zip_ref:
        zip_ref.extractall(extract_temp)

    # Destination directories
    data_models_dir = Path("data/data/models")
    data_models_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = Path("models/checkpoints")
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for root, _, files in os.walk(extract_temp):
        for f in files:
            src_file = Path(root) / f
            if f.endswith(('.pt', '.pkl', '.json', '.npz')):
                # Copy to data/data/models
                dest_data = data_models_dir / f
                shutil.copy2(src_file, dest_data)
                
                # If checkpoint or registry, also copy to models/checkpoints
                if f in ("world_model_lstm.pt", "registry.json", "feature_scaler.pkl", "ensemble_baselines.pkl"):
                    shutil.copy2(src_file, checkpoints_dir / f)
                    
                print(f"  ✓ Installed: {f}")
                copied += 1

    shutil.rmtree(extract_temp)
    print(f"\n✅ Successfully imported {copied} model artifacts!")
    print("👉 All 8 detection models are now active and ready for offline inference.")
    return True

if __name__ == "__main__":
    zip_arg = sys.argv[1] if len(sys.argv) > 1 else "netwatch_trained_models.zip"
    import_models(zip_arg)
