from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from backend import spt  # Algorithme SPT
from backend.validation import validate_jobs_data  # Validation externe
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from ligne_assemblage_mixte_goulot import variation_goulot_algorithm

app = FastAPI()

# Configuration CORS pour permettre les requêtes depuis le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- Modèle d’entrée -----------

class SPTRequest(BaseModel):
    jobs_data: List[List[List[int]]]
    due_dates: List[int]

class GoulotVariationRequest(BaseModel):
    sequence: List[str]  # Séquence de produits (A, B, etc.)
    models_demand: List[int]  # Demande par modèle [3, 7]
    task_times: List[List[float]]  # Temps des tâches [[14, 10], [12, 8], [16, 12], [11, 9]]

# ----------- Route principale -----------

@app.post("/spt")
def run_spt(request: SPTRequest):
    jobs_data = request.jobs_data
    due_dates = request.due_dates

    # Validation avancée
    try:
        validate_jobs_data(jobs_data, due_dates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Traitement
    result = spt.schedule(jobs_data, due_dates)

    # Formatage du résultat
    planification = {
        f"Machine {machine}": tasks
        for machine, tasks in result["machines"].items()
    }

    # Construction de la réponse finale
    return {
        "makespan": result["makespan"],
        "flowtime": result["flowtime"],
        "retard_cumule": result["retard_cumule"],
        "completion_times": {f"Job {j}": t for j, t in result["completion_times"].items()},
        "planification": planification
    }

@app.post("/goulot-variation")
def run_goulot_variation(request: GoulotVariationRequest):
    sequence = request.sequence
    models_demand = request.models_demand
    task_times = request.task_times

    try:
        # Convertir la séquence de lettres (A, B) en indices (1, 2)
        sequence_indices = []
        for product in sequence:
            if product == 'A':
                sequence_indices.append(1)
            elif product == 'B':
                sequence_indices.append(2)
            else:
                raise ValueError(f"Produit inconnu: {product}")

        # Calculer les métriques pour la séquence donnée
        models = tuple(models_demand)
        t_ij = task_times
        
        # Calculer le PGCD des modèles
        from math import gcd
        from functools import reduce
        gcd_models = reduce(gcd, models)
        
        # Calculer N_j et N
        N_j = [model // gcd_models for model in models]
        N = sum(N_j)
        
        # Calculer C_k (temps de cycle moyen du goulot)
        C_k = sum(sum(t_ij[i][j] * N_j[j] for j in range(len(models))) for i in range(len(t_ij))) / N
        
        # Calculer les temps cumulés
        cumulative_times = []
        cumulative_time = 0
        for pos, model in enumerate(sequence_indices):
            model_idx = model - 1
            task_time = sum(t_ij[i][model_idx] for i in range(len(t_ij)))
            cumulative_time += task_time
            cumulative_times.append(cumulative_time)
        
        # Temps théorique idéal
        theoretical_ideal = [C_k * (i+1) for i in range(len(sequence_indices))]
        
        # Calculer les déviations
        actual_deviations = [abs(cumulative_times[i] - theoretical_ideal[i]) for i in range(len(sequence_indices))]
        average_deviation = sum(actual_deviations) / len(actual_deviations) if actual_deviations else 0
        max_variation = max(actual_deviations) if actual_deviations else 0
        
        # Compter les modèles
        model_counts = {i+1: sequence_indices.count(i+1) for i in range(len(models))}
        
        # Créer les métriques
        metrics = {
            "nombre_total_unites": N,
            "repartition_modeles": N_j,
            "demandes_modeles": list(models),
            "sequence_longueur": len(sequence_indices),
            "variation_maximale": round(max_variation, 3),
            "temps_cycle_goulot": round(C_k, 3),
            "deviation_moyenne": round(average_deviation, 3),
            "comptage_modeles": model_counts,
            "parametres_lissage": {"s1": 0.5, "s2": 0.5},
            "statut_optimisation": "Evaluation",
            "efficacite_lissage": round((1 - average_deviation/C_k) * 100, 2) if C_k > 0 else 0
        }

        # Adapter le résultat pour la simulation interactive
        return {
            "sequence": sequence,
            "metrics": metrics,
            "cumulative_times": cumulative_times,
            "theoretical_ideal": theoretical_ideal,
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


