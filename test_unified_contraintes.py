#!/usr/bin/env python3
"""
Test rapide pour vérifier le système unifié des contraintes
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from contraintes import flowshop_contraintes

def test_flowshop_classique():
    """Test du flowshop classique (toutes les machines quantité = 1)"""
    print("=== TEST FLOWSHOP CLASSIQUE ===")
    
    # Données de test classiques
    jobs_data = [
        [(0, 8.0), (1, 6.0), (2, 4.0)],  # Job 1
        [(0, 5.0), (1, 9.0), (2, 3.0)]   # Job 2
    ]
    due_dates = [20, 25]
    job_names = ["Job A", "Job B"]
    machine_names = ["Machine 1", "Machine 2", "Machine 3"]
    machines_per_stage = [1, 1, 1]  # Une seule machine par étape
    
    result = flowshop_contraintes(jobs_data, due_dates, job_names, machine_names, machines_per_stage)
    
    print(f"Makespan: {result['makespan']}")
    print(f"Flowtime: {result['flowtime']}")
    print(f"Retard cumulé: {result['retard_cumule']}")
    print("✅ Flowshop classique réussi\n")
    
    return result

def test_flowshop_hybride():
    """Test du flowshop hybride (au moins une machine avec quantité > 1)"""
    print("=== TEST FLOWSHOP HYBRIDE ===")
    
    # Données de test hybrides
    jobs_data = [
        [(0, 8.0), (1, 6.0), (2, 4.0)],  # Job 1
        [(0, 5.0), (1, 9.0), (2, 3.0)]   # Job 2
    ]
    due_dates = [20, 25]
    job_names = ["Job A", "Job B"]
    machine_names = ["Étape 1", "Étape 2", "Étape 3"]
    machines_per_stage = [1, 3, 2]  # Étape 2 a 3 machines, Étape 3 a 2 machines
    
    result = flowshop_contraintes(jobs_data, due_dates, job_names, machine_names, machines_per_stage)
    
    print(f"Makespan: {result['makespan']}")
    print(f"Flowtime: {result['flowtime']}")
    print(f"Retard cumulé: {result['retard_cumule']}")
    print("✅ Flowshop hybride réussi\n")
    
    return result

if __name__ == "__main__":
    try:
        # Test des deux modes
        classic_result = test_flowshop_classique()
        hybrid_result = test_flowshop_hybride()
        
        print("🎉 TOUS LES TESTS RÉUSSIS!")
        print(f"Classique makespan: {classic_result['makespan']}")
        print(f"Hybride makespan: {hybrid_result['makespan']}")
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc() 