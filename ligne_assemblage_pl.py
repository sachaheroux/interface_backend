from pulp import *
import numpy as np
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import io
import base64

def pl_algorithm(task_tuples: List[tuple], cycle_time: float, unite: str = "minutes", task_names: Optional[Dict[int, str]] = None) -> Dict:
    """
    Implémente l'algorithme PL (Programmation Linéaire) pour l'équilibrage optimal de ligne d'assemblage
    
    Args:
        task_tuples: Liste de tuples (tâche, prédécesseurs, durée)
        cycle_time: Temps de cycle de la ligne
        unite: Unité de temps
    
    Returns:
        Dict avec les résultats de l'optimisation
    """
    
    # Préparation des données
    tasks_data = task_tuples
    C = cycle_time
    
    # Calcul du nombre minimal théorique de stations
    T = sum([task[2] for task in tasks_data])
    K_min = T / C
    
    # Les stations (on prend quelques stations en plus pour être sûr)
    stations = list(range(1, int(K_min) + 3))
    
    tasks = [task[0] for task in tasks_data]
    predecessors = {task[0]: task[1] for task in tasks_data}
    processing_times = {task[0]: task[2] for task in tasks_data}
    
    # Définition du problème d'optimisation
    prob = LpProblem("AssemblyLineScheduling", LpMinimize)
    
    # Variables de décision
    y = LpVariable.dicts("Station", [(i,j) for i in tasks for j in stations], 0, 1, LpBinary)
    
    # Fonction objective : minimiser le nombre de stations utilisées
    prob += lpSum([(10**j)*y[(i,j)] for i in tasks for j in stations]), "Total Cost of Stations"
    
    # Contraintes
    # 1. Chaque tâche est assignée à exactement une station
    for i in tasks:
        prob += lpSum([y[(i,j)] for j in stations]) == 1, f"Each task is assigned exactly once_{i}"
    
    # 2. Contrainte de temps de cycle pour chaque station
    for j in stations:
        prob += lpSum([processing_times[i]*y[(i,j)] for i in tasks]) <= C, f"Cycle time constraint_{j}"
    
    # 3. Contraintes de précédence
    for i in tasks:
        if predecessors[i] is not None:
            if isinstance(predecessors[i], list):
                for p in predecessors[i]:
                    prob += lpSum([j*y[(i,j)] for j in stations]) >= lpSum([j*y[(p,j)] for j in stations]), f"Precedence constraint_{p}_{i}"
            else:
                p = predecessors[i]
                prob += lpSum([j*y[(i,j)] for j in stations]) >= lpSum([j*y[(p,j)] for j in stations]), f"Precedence constraint_{p}_{i}"
    
    # Résolution du problème
    prob.solve(PULP_CBC_CMD(msg=0))  # msg=0 pour désactiver les messages de debug
    
    # Vérification du statut de la solution
    status = LpStatus[prob.status]
    if status != "Optimal":
        raise Exception(f"Erreur d'optimisation: {status}")
    
    # Extraction des résultats
    assigned_tasks = {j: [] for j in stations}
    
    for i in tasks:
        for j in stations:
            if y[(i,j)].varValue and y[(i,j)].varValue > 0:
                assigned_tasks[j].append(i)
    
    # Filtrer les stations utilisées
    used_stations = []
    utilization_rates = []
    
    for j in stations:
        if assigned_tasks[j]:  # Si la station a des tâches assignées
            used_stations.append(j)
            # Calcul du taux d'utilisation
            station_time = sum([processing_times[i] for i in assigned_tasks[j]])
            utilization_rate = (station_time / C) * 100
            utilization_rates.append(utilization_rate)
    
    # Reformatage pour la cohérence avec les autres algorithmes
    stations_result = []
    for idx, station_num in enumerate(used_stations):
        stations_result.append({
            "id": idx + 1,  # Renommer pour cohérence (1, 2, 3...)
            "tasks": assigned_tasks[station_num],
            "utilization": utilization_rates[idx]
        })
    
    # Calcul des métriques
    metrics = calculate_metrics(stations_result, utilization_rates, processing_times, C, unite, K_min, status)
    
    # Génération de la visualisation
    chart_base64 = generate_pl_chart(stations_result, utilization_rates, processing_times, unite, status, task_names)
    
    return {
        "stations": stations_result,
        "metrics": metrics,
        "graphique": chart_base64,
        "cycle_time": C,
        "unite": unite,
        "optimization_status": status
    }

def calculate_metrics(stations: List[Dict], utilization_rates: List[float], processing_times: Dict, cycle_time: float, unite: str, theoretical_min: float, status: str) -> Dict:
    """Calcule les métriques de performance de l'équilibrage optimal"""
    try:
        num_stations = len(stations)
        total_task_time = sum(processing_times.values())
        
        # Efficacité de l'équilibrage
        efficiency = (total_task_time / (num_stations * cycle_time)) * 100
        
        # Temps de cycle théorique minimum
        max_task_time = max(processing_times.values())
        min_theoretical_cycle_time = max_task_time
        
        # Utilisation moyenne
        average_utilization = sum(utilization_rates) / len(utilization_rates) if utilization_rates else 0
        
        # Temps total de la ligne
        total_line_time = num_stations * cycle_time
        
        # Écart à l'optimal
        optimality_gap = ((num_stations - theoretical_min) / theoretical_min) * 100 if theoretical_min > 0 else 0
        
        return {
            "nombre_stations": num_stations,
            "stations_theoriques_min": round(theoretical_min, 2),
            "efficacite": round(efficiency, 2),
            "utilisation_moyenne": round(average_utilization, 2),
            "temps_total_taches": total_task_time,
            "temps_cycle_theorique_min": min_theoretical_cycle_time,
            "temps_total_ligne": total_line_time,
            "taux_equilibrage": round((theoretical_min / num_stations) * 100, 2),
            "ecart_optimal": round(optimality_gap, 2),
            "statut_optimisation": status
        }
    except Exception as e:
        return {
            "nombre_stations": len(stations),
            "stations_theoriques_min": round(theoretical_min, 2),
            "efficacite": 0,
            "utilisation_moyenne": 0,
            "temps_total_taches": 0,
            "temps_cycle_theorique_min": 0,
            "temps_total_ligne": 0,
            "taux_equilibrage": 0,
            "ecart_optimal": 0,
            "statut_optimisation": status
        }

def generate_pl_chart(stations: List[Dict], utilization_rates: List[float], processing_times: Dict, unite: str, status: str, task_names: Optional[Dict[int, str]] = None) -> str:
    """Génère un graphique des stations et de leur utilisation pour l'algorithme PL"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Graphique 1: Taux d'utilisation par station
    station_numbers = [f"Station {station['id']}" for station in stations]
    colors = ['#10b981' if rate >= 80 else '#f59e0b' if rate >= 60 else '#ef4444' for rate in utilization_rates]
    
    bars = ax1.bar(station_numbers, utilization_rates, color=colors, alpha=0.8)
    ax1.set_ylabel(f'Taux d\'utilisation (%)')
    ax1.set_title(f'Taux d\'utilisation par station - Algorithme PL (Optimal) - Status: {status}')
    ax1.set_ylim(0, 100)
    
    # Ajouter les valeurs sur les barres
    for bar, rate in zip(bars, utilization_rates):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    # Ligne de référence à 80%
    ax1.axhline(y=80, color='green', linestyle='--', alpha=0.7, label='Cible 80%')
    ax1.legend()
    
    # Graphique 2: Temps de traitement par station avec barres empilées
    # Palette de couleurs pour les tâches
    all_task_ids = list(processing_times.keys())
    task_colors = plt.cm.Set3(range(len(all_task_ids)))
    
    # Préparer les données pour les barres empilées
    station_data = {}
    for i, station in enumerate(stations):
        station_data[i] = {task_id: 0 for task_id in all_task_ids}
        for task_id in station['tasks']:
            station_data[i][task_id] = processing_times[task_id]
    
    # Créer les barres empilées
    bottom_values = [0] * len(stations)
    
    for task_idx, task_id in enumerate(all_task_ids):
        task_times = [station_data[i][task_id] for i in range(len(stations))]
        
        # Ne dessiner que si au moins une station a cette tâche
        if any(time > 0 for time in task_times):
            task_label = task_names.get(task_id, f'Tâche {task_id}') if task_names else f'Tâche {task_id}'
            bars = ax2.bar(station_numbers, task_times, bottom=bottom_values, 
                          color=task_colors[task_idx], alpha=0.8, 
                          label=task_label)
            
            # Ajouter le texte sur chaque segment de barre
            for i, (bar, time) in enumerate(zip(bars, task_times)):
                if time > 0:  # Seulement si la tâche est présente dans cette station
                    height = bar.get_height()
                    task_display_name = task_names.get(task_id, f'T{task_id}') if task_names else f'T{task_id}'
                    ax2.text(bar.get_x() + bar.get_width()/2., 
                            bottom_values[i] + height/2,
                            f'{task_display_name}\n{time} {unite}', 
                            ha='center', va='center', 
                            fontsize=8, fontweight='bold')
            
            # Mettre à jour les valeurs de base pour l'empilement
            bottom_values = [bottom + time for bottom, time in zip(bottom_values, task_times)]
    
    ax2.set_ylabel(f'Temps total ({unite})')
    ax2.set_title('Charge de travail par station - Solution Optimale PL')
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    
    # Convertir en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64 