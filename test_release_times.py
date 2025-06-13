#!/usr/bin/env python3

import requests
import json

# Configuration du test
API_URL = "http://127.0.0.1:8001"

def test_jobshop_with_release_times():
    """Test de l'algorithme jobshop contraintes avec temps d'arrivée"""
    
    # Données de test
    test_data = {
        "jobs_data": [
            [[0, 4], [1, 2]],  # Job 1: Machine 0 (4h), Machine 1 (2h)
            [[1, 3], [0, 2]]   # Job 2: Machine 1 (3h), Machine 0 (2h)
        ],
        "due_dates": [12, 15],
        "job_names": ["Job A", "Job B"],
        "machine_names": ["Machine 1", "Machine 2"],
        "unite": "heures",
        "setup_times": None,
        "release_times": {
            0: 0,  # Job A arrive à t=0
            1: 5   # Job B arrive à t=5
        }
    }
    
    print("=== Test Jobshop Contraintes avec Temps d'Arrivée ===")
    print(f"Données envoyées: {json.dumps(test_data, indent=2)}")
    
    try:
        # Test de l'endpoint principal
        response = requests.post(f"{API_URL}/jobshop/contraintes", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Succès! Résultats:")
            print(f"Makespan: {result.get('makespan', 'N/A')}")
            print(f"Flowtime: {result.get('flowtime', 'N/A')}")
            print(f"Retard cumulé: {result.get('retard_cumule', 'N/A')}")
            
            if 'completion_times' in result:
                print("\nTemps de complétion:")
                for job, time in result['completion_times'].items():
                    print(f"  {job}: {time} heures")
            
            if 'release_times' in result:
                print("\nTemps d'arrivée:")
                for job, time in result['release_times'].items():
                    print(f"  {job}: {time} heures")
            
            if 'schedule' in result:
                print("\nPlanification:")
                for task in result['schedule']:
                    print(f"  {task['job']} sur {task['machine']}: {task['start']} → {task['end']}")
            
            return True
        else:
            print(f"❌ Erreur HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_without_release_times():
    """Test sans temps d'arrivée pour comparaison"""
    
    test_data = {
        "jobs_data": [
            [[0, 4], [1, 2]],  # Job 1: Machine 0 (4h), Machine 1 (2h)
            [[1, 3], [0, 2]]   # Job 2: Machine 1 (3h), Machine 0 (2h)
        ],
        "due_dates": [12, 15],
        "job_names": ["Job A", "Job B"],
        "machine_names": ["Machine 1", "Machine 2"],
        "unite": "heures",
        "setup_times": None,
        "release_times": None  # Pas de temps d'arrivée
    }
    
    print("\n=== Test Jobshop Contraintes SANS Temps d'Arrivée ===")
    
    try:
        response = requests.post(f"{API_URL}/jobshop/contraintes", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Succès! Résultats:")
            print(f"Makespan: {result.get('makespan', 'N/A')}")
            
            if 'schedule' in result:
                print("\nPlanification:")
                for task in result['schedule']:
                    print(f"  {task['job']} sur {task['machine']}: {task['start']} → {task['end']}")
            
            return True
        else:
            print(f"❌ Erreur HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Démarrage des tests des temps d'arrivée...")
    
    # Test sans temps d'arrivée
    success1 = test_without_release_times()
    
    # Test avec temps d'arrivée
    success2 = test_jobshop_with_release_times()
    
    if success1 and success2:
        print("\n🎉 Tous les tests sont passés avec succès!")
    else:
        print("\n⚠️ Certains tests ont échoué.") 