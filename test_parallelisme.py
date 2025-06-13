#!/usr/bin/env python3
"""
Test spécifique pour vérifier l'exploitation du parallélisme
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from contraintes import flowshop_contraintes

def test_parallelisme_evident():
    """
    Test avec une configuration où le parallélisme est évident et nécessaire
    3 jobs, 3 étapes, étape 2 avec 3 machines
    Si l'algo fonctionne, les 3 jobs devraient pouvoir passer en parallèle à l'étape 2
    """
    print("=== TEST PARALLÉLISME ÉVIDENT ===")
    print("Configuration: 3 jobs, étape 2 avec 3 machines en parallèle")
    
    # 3 jobs identiques pour forcer le parallélisme 
    jobs_data = [
        [(0, 10), (1, 20), (2, 10)],  # Job 0: 10s, 20s, 10s
        [(0, 10), (1, 20), (2, 10)],  # Job 1: 10s, 20s, 10s  
        [(0, 10), (1, 20), (2, 10)]   # Job 2: 10s, 20s, 10s
    ]
    
    due_dates = [50, 50, 50]
    job_names = ["Job A", "Job B", "Job C"]
    machine_names = ["Préparation", "Traitement", "Finition"]
    machines_per_stage = [1, 3, 1]  # Étape Traitement avec 3 machines
    
    print(f"Jobs: {len(jobs_data)} jobs identiques")
    print(f"Machines par étape: {machines_per_stage}")
    print(f"Théoriquement:")
    print(f"  - Sans parallélisme: makespan = 10 + 20*3 + 10 = 80")
    print(f"  - Avec parallélisme: makespan = 10 + 20 + 10 = 40 (les 3 jobs en parallèle à l'étape 2)")
    
    try:
        result = flowshop_contraintes(jobs_data, due_dates, job_names, machine_names, machines_per_stage)
        
        print(f"\n🎯 RÉSULTATS:")
        print(f"Makespan obtenu: {result['makespan']}")
        
        if result['makespan'] <= 45:  # Proche de 40 avec marge
            print(f"✅ PARALLÉLISME EXPLOITÉ! (makespan proche de 40)")
        else:
            print(f"❌ PARALLÉLISME PAS EXPLOITÉ (makespan proche de 80)")
        
        print(f"\n📊 DÉTAIL DES ÉTAPES:")
        for etape, tasks in result['machines'].items():
            print(f"  {machine_names[etape]}: {len(tasks)} tâches")
        
        if 'raw_machines' in result:
            print(f"\n🔧 UTILISATION DES MACHINES:")
            for machine_id, tasks in result['raw_machines'].items():
                if tasks:
                    print(f"  Machine {machine_id}: {len(tasks)} tâches - {tasks}")
                else:
                    print(f"  Machine {machine_id}: VIDE")
        
        return result
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_parallelisme_evident() 