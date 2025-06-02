from pulp import *
from math import gcd
from functools import reduce
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

def variation_goulot_algorithm(models_demand: List[int], task_times: List[List[float]], s1: float = 0.5, s2: float = 0.5, unite: str = "minutes") -> Dict:
    """
    Implémente l'algorithme de minimisation de la variation du goulot pour ligne d'assemblage mixte
    
    Args:
        models_demand: Demande par modèle par période/temps de cycle [4, 6]
        task_times: Temps de traitement des tâches au poste goulot [[3,3], [2,3]]
        s1: Paramètre de lissage pour les contraintes de modèles
        s2: Paramètre de lissage pour les contraintes de capacité
        unite: Unité de temps
    
    Returns:
        Dict avec les résultats de l'optimisation
    """
    
    models = tuple(models_demand)
    t_ij = task_times
    
    # Calculer le PGCD des modèles
    gcd_models = reduce(gcd, models)
    
    # Calculer N_j et N
    N_j = [model // gcd_models for model in models]
    N = sum(N_j)
    
    # Calculer C_k (temps de cycle moyen du goulot)
    C_k = sum(sum(t_ij[i][j] * N_j[j] for j in range(len(models))) for i in range(len(t_ij))) / N
    
    # Variables de décision
    x = [[LpVariable(f'x_{j}_{n}', cat='Binary') for n in range(N)] for j in range(len(models))]
    delta = LpVariable('delta', lowBound=0)
    
    # Créer le problème d'optimisation
    prob = LpProblem("BottleneckVariationMinimization", LpMinimize)
    
    # Fonction objectif : minimiser la variation
    prob += delta
    
    # Contraintes de variation
    for n in range(1, N+1):
        prob += delta >= lpSum([t_ij[i][j]*x[j][h] for h in range(n) for j in range(len(models)) for i in range(len(t_ij))]) - n*C_k 
        prob += delta >= n*C_k - lpSum([t_ij[i][j]*x[j][h] for h in range(n) for j in range(len(models)) for i in range(len(t_ij))])
    
    # Contraintes de production : nombre exact de chaque modèle
    for j in range(len(models)):
        prob += lpSum([x[j][n] for n in range(N)]) == N_j[j]
    
    # Contraintes de lissage des modèles
    for n in range(1, N+1):
        for j in range(len(models)):
            prob += (n*N_j[j])/N - s1 <= lpSum([x[j][b] for b in range(n)]) <= (n*N_j[j])/N + s1
    
    # Contraintes de capacité du goulot
    for n in range(1, N+1):
        prob += lpSum([t_ij[i][j]*x[j][h] for h in range(n) for j in range(len(models)) for i in range(len(t_ij))]) <= (n + s2)*C_k
    
    # Résolution du problème
    prob.solve(PULP_CBC_CMD(msg=0))
    
    # Vérification du statut
    status = LpStatus[prob.status]
    if status not in ["Optimal", "Feasible"]:
        raise Exception(f"Erreur d'optimisation: {status}")
    
    # Extraction de la séquence optimale
    sequence = []
    for n in range(N):
        for j in range(len(models)):
            if value(x[j][n]) and value(x[j][n]) >= 0.99:
                sequence.append(j+1)  # Modèle j+1
    
    # Calcul des métriques
    metrics = calculate_goulot_metrics(sequence, models, t_ij, C_k, delta.varValue, N_j, N, s1, s2, status, unite)
    
    # Génération de la visualisation
    chart_base64 = generate_goulot_chart(sequence, models, t_ij, C_k, unite, status)
    
    return {
        "sequence": sequence,
        "metrics": metrics,
        "graphique": chart_base64,
        "models_demand": models,
        "cycle_time_goulot": round(C_k, 3),
        "unite": unite,
        "optimization_status": status,
        "parameters": {"s1": s1, "s2": s2}
    }

def calculate_goulot_metrics(sequence: List[int], models: tuple, t_ij: List[List[float]], C_k: float, delta_value: float, N_j: List[int], N: int, s1: float, s2: float, status: str, unite: str) -> Dict:
    """Calcule les métriques de performance pour la variation du goulot"""
    try:
        # Analyse de la séquence
        model_counts = {i+1: sequence.count(i+1) for i in range(len(models))}
        
        # Calcul des temps cumulés au goulot
        cumulative_times = []
        cumulative_time = 0
        
        for pos, model in enumerate(sequence):
            model_idx = model - 1
            task_time = sum(t_ij[i][model_idx] for i in range(len(t_ij)))
            cumulative_time += task_time
            cumulative_times.append(cumulative_time)
        
        # Variation maximale observée
        max_variation = delta_value if delta_value else 0
        
        # Efficacité du lissage
        theoretical_ideal = [C_k * (i+1) for i in range(N)]
        actual_deviations = [abs(cumulative_times[i] - theoretical_ideal[i]) for i in range(N)]
        average_deviation = sum(actual_deviations) / len(actual_deviations)
        
        # Régularité de la séquence
        model_positions = {i+1: [pos for pos, m in enumerate(sequence) if m == i+1] for i in range(len(models))}
        
        return {
            "nombre_total_unites": N,
            "repartition_modeles": N_j,
            "demandes_modeles": list(models),
            "sequence_longueur": len(sequence),
            "variation_maximale": round(max_variation, 3),
            "temps_cycle_goulot": round(C_k, 3),
            "deviation_moyenne": round(average_deviation, 3),
            "comptage_modeles": model_counts,
            "parametres_lissage": {"s1": s1, "s2": s2},
            "statut_optimisation": status,
            "efficacite_lissage": round((1 - average_deviation/C_k) * 100, 2) if C_k > 0 else 0
        }
    except Exception as e:
        return {
            "nombre_total_unites": N,
            "repartition_modeles": N_j,
            "demandes_modeles": list(models),
            "sequence_longueur": len(sequence) if sequence else 0,
            "variation_maximale": 0,
            "temps_cycle_goulot": round(C_k, 3),
            "deviation_moyenne": 0,
            "comptage_modeles": {},
            "parametres_lissage": {"s1": s1, "s2": s2},
            "statut_optimisation": status,
            "efficacite_lissage": 0
        }

def generate_goulot_chart(sequence: List[int], models: tuple, t_ij: List[List[float]], C_k: float, unite: str, status: str) -> str:
    """Génère un graphique d'analyse de la variation du goulot"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Graphique 1: Séquence de production
    positions = list(range(1, len(sequence) + 1))
    colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6']
    model_colors = [colors[model-1] for model in sequence]
    
    bars = ax1.bar(positions, [1]*len(sequence), color=model_colors, alpha=0.8, width=0.8)
    ax1.set_ylabel('Modèle produit')
    ax1.set_xlabel('Position dans la séquence')
    ax1.set_title(f'Séquence optimale de production mixte - Status: {status}')
    ax1.set_ylim(0, max(models) + 0.5)
    
    # Ajouter les numéros de modèles sur les barres
    for bar, model in zip(bars, sequence):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height/2,
                f'M{model}', ha='center', va='center', fontweight='bold', color='white')
    
    # Légende pour les modèles
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=colors[i], label=f'Modèle {i+1}') for i in range(len(models))]
    ax1.legend(handles=legend_elements, loc='upper right')
    
    # Graphique 2: Variation du temps cumulé au goulot
    cumulative_times = []
    cumulative_time = 0
    
    for model in sequence:
        model_idx = model - 1
        task_time = sum(t_ij[i][model_idx] for i in range(len(t_ij)))
        cumulative_time += task_time
        cumulative_times.append(cumulative_time)
    
    # Temps théorique idéal
    N = len(sequence)
    theoretical_ideal = [C_k * (i+1) for i in range(N)]
    
    ax2.plot(positions, cumulative_times, 'o-', color='#ef4444', linewidth=2, markersize=4, label='Temps réel cumulé')
    ax2.plot(positions, theoretical_ideal, '--', color='#10b981', linewidth=2, label='Temps théorique idéal')
    
    # Zone de variation
    variations = [abs(cumulative_times[i] - theoretical_ideal[i]) for i in range(N)]
    max_variation = max(variations) if variations else 0
    
    ax2.fill_between(positions, 
                     [t - max_variation for t in theoretical_ideal],
                     [t + max_variation for t in theoretical_ideal],
                     alpha=0.2, color='orange', label=f'Zone de variation (±{max_variation:.2f})')
    
    ax2.set_ylabel(f'Temps cumulé ({unite})')
    ax2.set_xlabel('Position dans la séquence')
    ax2.set_title('Variation du temps cumulé au poste goulot')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Convertir en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64 