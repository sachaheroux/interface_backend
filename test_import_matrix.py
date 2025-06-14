#!/usr/bin/env python3

import requests
import os

def test_import_matrix():
    """Test l'import du template exemple"""
    
    # Chemin vers le template exemple
    template_path = "../frontend/public/Template-Flowshop_Exemple.xlsx"
    
    if not os.path.exists(template_path):
        print("❌ Template exemple non trouvé")
        return
    
    print("🧪 Test import template exemple...")
    
    try:
        # Lire le fichier
        with open(template_path, 'rb') as f:
            files = {'file': ('Template-Flowshop_Exemple.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            # Tester l'import SPT
            response = requests.post('http://127.0.0.1:8001/spt/import-excel', files=files)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Import réussi!")
                print(f"   Jobs: {data['imported_data']['job_names']}")
                print(f"   Machines: {data['imported_data']['machine_names']}")
                print(f"   Unité: {data['imported_data']['unite']}")
                print(f"   Makespan: {data['results']['makespan']}")
            else:
                print(f"❌ Erreur {response.status_code}: {response.text}")
                
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    test_import_matrix() 