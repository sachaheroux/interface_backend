from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import io
import base64

def lpt_algorithm(task_tuples: List[tuple], cycle_time: float, unite: str = "minutes", task_names: Optional[Dict[int, str]] = None) -> Dict:
    """
    Implémente l'algorithme LPT (Longest Processing Time) pour l'équilibrage de ligne d'assemblage
    
    Args:
        task_tuples: Liste de tuples (tâche, prédécesseurs, durée)
        cycle_time: Temps de cycle de la ligne
        unite: Unité de temps
    
    Returns:
        Dict avec les résultats de l'équilibrage
    """
    # Préparation des données
    tasks = {task[0]: {"pred": task[1], "time": task[2], "assigned": False} for task in task_tuples}
    stations = []
    utilization_rates = []
    
    # Algorithme LPT
    while any(not task["assigned"] for task in tasks.values()):
        # Initialisation de la nouvelle station
        station = []
        remaining_time = cycle_time

        while True:
            # Identification des tâches éligibles
            eligible_tasks = [task_id for task_id, task in tasks.items() 
                              if not task["assigned"]
                              and is_precedence_satisfied(task_id, task, tasks)
                              and task["time"] <= remaining_time]
            
            # Si aucune tâche éligible, on arrête pour cette station
            if not eligible_tasks:
                break

            # Sélection de la tâche avec le temps de traitement le plus long
            task_to_assign = max(eligible_tasks, key=lambda t: tasks[t]["time"])

            station.append(task_to_assign)
            tasks[task_to_assign]["assigned"] = True
            remaining_time -= tasks[task_to_assign]["time"]
            
        stations.append(station)

        # Calcul du taux d'utilisation de la station
        utilization_rate = (cycle_time - remaining_time) / cycle_time * 100
        utilization_rates.append(utilization_rate)

    # Calcul des métriques globales
    metrics = calculate_metrics(stations, utilization_rates, tasks, cycle_time, unite)
    
    # Génération de la visualisation
    chart_base64 = generate_station_chart(stations, utilization_rates, tasks, unite, task_names)
    
    return {
        "stations": [{"id": i+1, "tasks": station, "utilization": rate} for i, (station, rate) in enumerate(zip(stations, utilization_rates))],
        "metrics": metrics,
        "graphique": chart_base64,
        "cycle_time": cycle_time,
        "unite": unite
    }

def is_precedence_satisfied(task_id: int, task: Dict, tasks: Dict) -> bool:
    """Vérifie si les contraintes de précédence sont satisfaites pour une tâche"""
    if task["pred"] is None:
        return True
    
    if isinstance(task["pred"], list):
        return all(tasks[pred]["assigned"] for pred in task["pred"])
    else:
        return tasks[task["pred"]]["assigned"]

def calculate_metrics(stations: List[List], utilization_rates: List[float], tasks: Dict, cycle_time: float, unite: str) -> Dict:
    """Calcule les métriques de performance de l'équilibrage"""
    try:
        num_stations = len(stations)
        total_task_time = sum(task["time"] for task in tasks.values())
        theoretical_min_stations = total_task_time / cycle_time
        
        # Efficacité de l'équilibrage
        efficiency = (total_task_time / (num_stations * cycle_time)) * 100
        
        # Temps de cycle théorique minimum
        max_task_time = max(task["time"] for task in tasks.values())
        min_theoretical_cycle_time = max_task_time
        
        # Utilisation moyenne
        average_utilization = sum(utilization_rates) / len(utilization_rates)
        
        # Temps total de la ligne
        total_line_time = num_stations * cycle_time
        
        return {
            "nombre_stations": num_stations,
            "stations_theoriques_min": round(theoretical_min_stations, 2),
            "efficacite": round(efficiency, 2),
            "utilisation_moyenne": round(average_utilization, 2),
            "temps_total_taches": total_task_time,
            "temps_cycle_theorique_min": min_theoretical_cycle_time,
            "temps_total_ligne": total_line_time,
            "taux_equilibrage": round((theoretical_min_stations / num_stations) * 100, 2)
        }
    except Exception as e:
        return {
            "nombre_stations": len(stations),
            "stations_theoriques_min": 0,
            "efficacite": 0,
            "utilisation_moyenne": 0,
            "temps_total_taches": 0,
            "temps_cycle_theorique_min": 0,
            "temps_total_ligne": 0,
            "taux_equilibrage": 0
        }

def generate_station_chart(stations: List[List], utilization_rates: List[float], tasks: Dict, unite: str, task_names: Optional[Dict[int, str]] = None) -> str:
    """Génère un graphique des stations et de leur utilisation"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Graphique 1: Taux d'utilisation par station
    station_numbers = [f"Station {i+1}" for i in range(len(stations))]
    colors = ['#3b82f6' if rate >= 80 else '#f59e0b' if rate >= 60 else '#ef4444' for rate in utilization_rates]
    
    bars = ax1.bar(station_numbers, utilization_rates, color=colors, alpha=0.7)
    ax1.set_ylabel(f'Taux d\'utilisation (%)')
    ax1.set_title('Taux d\'utilisation par station - Algorithme LPT')
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
    task_colors = plt.cm.Set3(range(len(tasks)))
    all_task_ids = list(tasks.keys())
    
    # Préparer les données pour les barres empilées
    station_data = {}
    for i, station in enumerate(stations):
        station_data[i] = {task_id: 0 for task_id in all_task_ids}
        for task_id in station:
            station_data[i][task_id] = tasks[task_id]["time"]
    
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
    ax2.set_title('Charge de travail par station - Stratégie LPT (Plus longue tâche d\'abord)')
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    
    # Convertir en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64 