#!/usr/bin/env python3
import os
import sys
import subprocess

# Changer vers le répertoire backend
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Démarrer uvicorn directement
try:
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "main:app", 
        "--host", "127.0.0.1", 
        "--port", "8000", 
        "--reload"
    ], check=True)
except Exception as e:
    print(f"Erreur lors du démarrage du serveur: {e}")
    input("Appuyez sur Entrée pour continuer...") 