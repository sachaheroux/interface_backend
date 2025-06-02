import requests
import json

url = "http://localhost:8001/fms/sac_a_dos"

# Données simplifiées pour le test
data = {
    "vente_unite": [200, 155],
    "cout_mp_unite": [45, 35],
    "demande_periode": [100, 50],
    "temps_fabrication_unite": [1, 2],
    "cout_op": 50,
    "capacite_max": 250,
    "noms_produits": ["Produit 1", "Produit 2"],
    "unite": "heures"
}

try:
    print("Testing with simplified data...")
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("Success!")
        print(f"Profit maximal: {result.get('profit_maximal', 'N/A')}")
        print(f"Status: {result.get('status', 'N/A')}")
    else:
        print("Error Response:")
        print(response.text)
        
except Exception as e:
    print(f"Exception: {e}") 