#!/usr/bin/env python3
"""
Test de l'export Excel pour identifier le problème des temps de traitement
"""

from excel_import import export_manual_data_to_excel
import json

# Données de test simples pour reproduire le problème
jobs_data = [
    [10.0, 20.0, 15.0],  # Job 1: 10h sur M1, 20h sur M2, 15h sur M3
    [5.0, 25.0, 10.0],   # Job 2: 5h sur M1, 25h sur M2, 10h sur M3
    [8.0, 12.0, 18.0]    # Job 3: 8h sur M1, 12h sur M2, 18h sur M3
]

due_dates = [50.0, 60.0, 55.0]  # Dates d'échéance
job_names = ["Job1", "Job2", "Job3"]
machine_names = ["Machine1", "Machine2", "Machine3"]

print("=== TEST EXPORT EXCEL ===")
print(f"jobs_data: {jobs_data}")
print(f"due_dates: {due_dates}")
print(f"job_names: {job_names}")
print(f"machine_names: {machine_names}")
print()

try:
    # Appeler la fonction d'export avec debug
    result = export_manual_data_to_excel(
        jobs_data=jobs_data,
        due_dates=due_dates,
        job_names=job_names,
        machine_names=machine_names,
        unite="heures"
    )
    
    # Sauvegarder le fichier pour inspection
    with open("test_export.xlsx", "wb") as f:
        f.write(result)
    
    print(f"✅ Export réussi ! Fichier sauvegardé : test_export.xlsx")
    print(f"Taille du fichier : {len(result)} bytes")
    
except Exception as e:
    print(f"❌ Erreur lors de l'export : {e}")
    import traceback
    traceback.print_exc() 