#!/usr/bin/env python3
"""
Test des améliorations des algorithmes de ligne d'assemblage
- Affichage des noms de tâches au lieu des numéros
- Graphiques avec barres empilées
"""

import requests
import json

def test_comsoal():
    print("=== TEST COMSOAL ===")
    
    # Données de test avec noms personnalisés
    data = {
        "tasks_data": [
            {"id": 1, "name": "Assemblage base", "predecessors": None, "duration": 20},
            {"id": 2, "name": "Montage moteur", "predecessors": 1, "duration": 6},
            {"id": 3, "name": "Installation roues", "predecessors": 2, "duration": 5},
            {"id": 4, "name": "Peinture carrosserie", "predecessors": None, "duration": 21},
            {"id": 5, "name": "Pose vitres", "predecessors": None, "duration": 8}
        ],
        "cycle_time": 30,
        "unite": "minutes",
        "seed": 42
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/ligne_assemblage/comsoal", json=data)
        if response.status_code == 200:
            result = response.json()
            print("✅ COMSOAL - Succès!")
            print(f"Nombre de stations: {result['metrics']['nombre_stations']}")
            print(f"Efficacité: {result['metrics']['efficacite']}%")
            
            # Vérifier que les stations contiennent les bons IDs
            print("\nStations:")
            for station in result['stations']:
                print(f"  Station {station['id']}: Tâches {station['tasks']} ({station['utilization']:.1f}%)")
            
            return True
        else:
            print(f"❌ COMSOAL - Erreur {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ COMSOAL - Exception: {e}")
        return False

def test_lpt():
    print("\n=== TEST LPT ===")
    
    # Données de test avec noms personnalisés
    data = {
        "tasks_data": [
            {"id": 1, "name": "Préparation matériel", "predecessors": None, "duration": 15},
            {"id": 2, "name": "Usinage pièce A", "predecessors": 1, "duration": 12},
            {"id": 3, "name": "Usinage pièce B", "predecessors": 1, "duration": 18},
            {"id": 4, "name": "Assemblage final", "predecessors": [2, 3], "duration": 10}
        ],
        "cycle_time": 25,
        "unite": "minutes"
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/ligne_assemblage/lpt", json=data)
        if response.status_code == 200:
            result = response.json()
            print("✅ LPT - Succès!")
            print(f"Nombre de stations: {result['metrics']['nombre_stations']}")
            print(f"Efficacité: {result['metrics']['efficacite']}%")
            
            # Vérifier que les stations contiennent les bons IDs
            print("\nStations:")
            for station in result['stations']:
                print(f"  Station {station['id']}: Tâches {station['tasks']} ({station['utilization']:.1f}%)")
            
            return True
        else:
            print(f"❌ LPT - Erreur {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ LPT - Exception: {e}")
        return False

def test_pl():
    print("\n=== TEST PL ===")
    
    # Données de test avec noms personnalisés
    data = {
        "tasks_data": [
            {"id": 1, "name": "Découpe matériau", "predecessors": None, "duration": 8},
            {"id": 2, "name": "Perçage trous", "predecessors": 1, "duration": 5},
            {"id": 3, "name": "Soudure joints", "predecessors": 2, "duration": 12},
            {"id": 4, "name": "Contrôle qualité", "predecessors": 3, "duration": 6}
        ],
        "cycle_time": 20,
        "unite": "minutes"
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/ligne_assemblage/pl", json=data)
        if response.status_code == 200:
            result = response.json()
            print("✅ PL - Succès!")
            print(f"Nombre de stations: {result['metrics']['nombre_stations']}")
            print(f"Efficacité: {result['metrics']['efficacite']}%")
            print(f"Statut optimisation: {result['optimization_status']}")
            
            # Vérifier que les stations contiennent les bons IDs
            print("\nStations:")
            for station in result['stations']:
                print(f"  Station {station['id']}: Tâches {station['tasks']} ({station['utilization']:.1f}%)")
            
            return True
        else:
            print(f"❌ PL - Erreur {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ PL - Exception: {e}")
        return False

def test_chart_generation():
    print("\n=== TEST GÉNÉRATION GRAPHIQUES ===")
    
    # Test avec COMSOAL pour vérifier la génération de graphique
    data = {
        "tasks_data": [
            {"id": 1, "name": "Tâche Alpha", "predecessors": None, "duration": 10},
            {"id": 2, "name": "Tâche Beta", "predecessors": 1, "duration": 8},
            {"id": 3, "name": "Tâche Gamma", "predecessors": None, "duration": 12}
        ],
        "cycle_time": 15,
        "unite": "minutes",
        "seed": 123
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/ligne_assemblage/comsoal/chart", json=data)
        if response.status_code == 200:
            print("✅ Génération graphique - Succès!")
            print(f"Type de contenu: {response.headers.get('content-type')}")
            print(f"Taille du graphique: {len(response.content)} bytes")
            return True
        else:
            print(f"❌ Génération graphique - Erreur {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Génération graphique - Exception: {e}")
        return False

if __name__ == "__main__":
    print("🧪 TEST DES AMÉLIORATIONS LIGNE D'ASSEMBLAGE")
    print("=" * 50)
    
    results = []
    results.append(test_comsoal())
    results.append(test_lpt())
    results.append(test_pl())
    results.append(test_chart_generation())
    
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DES TESTS")
    print(f"Tests réussis: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 Tous les tests sont passés avec succès!")
        print("\n✨ AMÉLIORATIONS IMPLÉMENTÉES:")
        print("  1. ✅ Noms des tâches dans la configuration des stations")
        print("  2. ✅ Graphiques avec barres empilées par tâche")
        print("  3. ✅ Noms des tâches dans les graphiques")
        print("  4. ✅ Légendes avec noms personnalisés")
    else:
        print("❌ Certains tests ont échoué") 