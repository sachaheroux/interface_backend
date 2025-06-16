#!/usr/bin/env python3
"""
Test de l'export Excel pour SPT avec le bon format de données
"""

import requests
import json

# URL du serveur (port 8003 d'après les logs)
API_URL = "http://127.0.0.1:8003"

# Données de test au format SPT (comme elles arrivent du frontend)
data = {
    "jobs_data": [
        [10.0, 20.0, 15.0],  # Job 1: 10h sur M1, 20h sur M2, 15h sur M3
        [5.0, 25.0, 10.0],   # Job 2: 5h sur M1, 25h sur M2, 10h sur M3
        [8.0, 12.0, 18.0]    # Job 3: 8h sur M1, 12h sur M2, 18h sur M3
    ],
    "due_dates": [50.0, 60.0, 55.0],
    "job_names": ["Job 1", "Job 2", "Job 3"],
    "machine_names": ["Machine 1", "Machine 2", "Machine 3"],
    "unite": "heures"
}

print("=== TEST EXPORT SPT ===")
print(f"Données à envoyer: {json.dumps(data, indent=2)}")
print()

try:
    # Envoyer la requête d'export
    response = requests.post(
        f"{API_URL}/spt/export-excel",
        json=data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        # Sauvegarder le fichier Excel
        with open("test_spt_export.xlsx", "wb") as f:
            f.write(response.content)
        
        print(f"✅ Export SPT réussi !")
        print(f"📁 Fichier sauvegardé : test_spt_export.xlsx")
        print(f"📊 Taille du fichier : {len(response.content)} bytes")
        print()
        print("🔍 Ouvrez le fichier Excel pour vérifier que :")
        print("   - Les noms des jobs sont dans la colonne C (lignes 6-8)")
        print("   - Les noms des machines sont dans la ligne 5 (colonnes D-F)")
        print("   - Les temps de traitement sont dans D6-F8 (NON ZÉRO !)")
        print("   - Les dates d'échéance sont dans la colonne N (lignes 6-8)")
        
    else:
        print(f"❌ Erreur HTTP {response.status_code}")
        try:
            error_data = response.json()
            print(f"Détail de l'erreur : {error_data}")
        except:
            print(f"Réponse brute : {response.text}")
            
except requests.exceptions.ConnectionError:
    print(f"❌ Impossible de se connecter au serveur sur {API_URL}")
    print("Vérifiez que le serveur FastAPI est démarré")
    
except Exception as e:
    print(f"❌ Erreur inattendue : {e}")
    import traceback
    traceback.print_exc() 