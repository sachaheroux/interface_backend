#!/usr/bin/env python3
"""
Test de débogage pour l'algorithme hybride
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from contraintes import flowshop_contraintes

def test_simple_hybride():
    """Test simple avec 2 jobs, 3 étapes, étape 2 avec 2 machines"""
    print("=== TEST DEBUG HYBRIDE SIMPLE ===")
    
    # Configuration simple
    jobs_data = [
        [(0, 10), (1, 5), (2, 8)],   # Job 0: 10s, 5s, 8s
        [(0, 6), (1, 9), (2, 4)]     # Job 1: 6s, 9s, 4s  
    ]
    due_dates = [30, 25]
    job_names = ["Job A", "Job B"]
    machine_names = ["Découpe", "Usinage", "Montage"]
    machines_per_stage = [1, 2, 1]  # Étape Usinage avec 2 machines
    
    print(f"Jobs data: {jobs_data}")
    print(f"Machines per stage: {machines_per_stage}")
    
    try:
        result = flowshop_contraintes(jobs_data, due_dates, job_names, machine_names, machines_per_stage)
        
        print(f"\n✅ RÉSULTATS:")
        print(f"Makespan: {result['makespan']}")
        print(f"Flowtime: {result['flowtime']}")
        print(f"Retard cumulé: {result['retard_cumule']}")
        
        print(f"\n📊 PLANIFICATION (par étapes):")
        for etape, tasks in result['machines'].items():
            print(f"  {machine_names[etape]}: {tasks}")
        
        if 'raw_machines' in result:
            print(f"\n🔧 MACHINES PHYSIQUES (pour Gantt):")
            for machine_id, tasks in result['raw_machines'].items():
                print(f"  Machine {machine_id}: {tasks}")
        
        print(f"\n⏱️  TEMPS DE COMPLÉTION:")
        for job, time in result['completion_times'].items():
            print(f"  {job}: {time}")
            
        return result
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_simple_hybride() 