from pulp import *
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import base64

def mixed_assembly_line_scheduling(models, tasks_data, cycle_time):
    """
    Algorithme d'équilibrage de ligne d'assemblage mixte
    Utilise la programmation linéaire pour minimiser le nombre de stations
    tout en respectant les contraintes de temps de cycle et de précédence
    """
    # Calcul du temps total pondéré par les modèles
    T = sum([sum(np.multiply(models, [task[i][1] for i in range(1, len(task))])) for task in tasks_data])
    K_min = T / cycle_time

    # Définition des stations (on prend une marge de sécurité)
    stations = list(range(1, int(np.ceil(K_min)) + 2))

    # Extraction des tâches et construction du dictionnaire des prédécesseurs
    tasks = [task[0] for task in tasks_data]
    
    # Construction du dictionnaire des prédécesseurs (union des prédécesseurs de tous les modèles)
    predecessors = {}
    for task in tasks_data:
        task_id = task[0]
        all_predecessors = []
        for i in range(1, len(task)):
            pred = task[i][0]
            if pred is not None:
                if isinstance(pred, list):
                    all_predecessors.extend(pred)
                else:
                    all_predecessors.append(pred)
        # Enlever les doublons et None
        predecessors[task_id] = list(set([p for p in all_predecessors if p is not None]))

    # Calcul des temps de traitement pondérés par la demande de chaque modèle
    weighted_processing_times = {}
    for task in tasks_data:
        task_id = task[0]
        weighted_time = sum(np.multiply(models, [task[i][1] for i in range(1, len(task))]))
        weighted_processing_times[task_id] = weighted_time

    # Création du problème de programmation linéaire
    prob = LpProblem("MixedAssemblyLineScheduling", LpMinimize)

    # Variables de décision
    y = LpVariable.dicts("Station", [(i,j) for i in tasks for j in stations], 0, 1, LpBinary)

    # Fonction objective : minimiser le nombre de stations utilisées
    # On utilise une pondération par puissance de 10 pour favoriser les stations avec index plus petit
    prob += lpSum([(10**j)*y[(i,j)] for i in tasks for j in stations]), "Total Cost of Stations"

    # Contraintes
    # 1. Chaque tâche doit être assignée à exactement une station
    for i in tasks:
        prob += lpSum([y[(i,j)] for j in stations]) == 1, f"Each_task_assigned_once_{i}"

    # 2. Contrainte de temps de cycle pour chaque station
    for j in stations:
        prob += lpSum([weighted_processing_times[i]*y[(i,j)] for i in tasks]) <= cycle_time, f"Cycle_time_constraint_{j}"

    # 3. Contraintes de précédence
    counter = 1
    for i in tasks:
        if predecessors[i]:  # Si la tâche a des prédécesseurs
            for p in predecessors[i]:
                # Une tâche ne peut être assignée qu'à une station égale ou supérieure à ses prédécesseurs
                prob += lpSum([j*y[(i,j)] for j in stations]) >= lpSum([j*y[(p,j)] for j in stations]), f"Precedence_constraint_{counter}"
                counter += 1

    # Résolution du problème
    prob.solve(PULP_CBC_CMD(msg=0))

    # Extraction des résultats
    status = LpStatus[prob.status]
    
    assigned_tasks = {j: [] for j in stations}
    station_utilizations = {}
    station_loads = {}

    for i in tasks:
        for j in stations:
            if y[(i,j)].varValue and y[(i,j)].varValue > 0:
                assigned_tasks[j].append(i)

    # Calcul des métriques pour chaque station utilisée
    used_stations = 0
    total_utilization = 0
    max_utilization = 0
    min_utilization = 100

    for j in stations:
        tasks_in_station = assigned_tasks[j]
        if tasks_in_station:  # Si la station est utilisée
            used_stations += 1
            station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
            station_utilization = (station_load / cycle_time) * 100
            
            station_loads[j] = station_load
            station_utilizations[j] = station_utilization
            
            total_utilization += station_utilization
            max_utilization = max(max_utilization, station_utilization)
            if station_utilization > 0:
                min_utilization = min(min_utilization, station_utilization)

    # Métriques globales
    avg_utilization = total_utilization / used_stations if used_stations > 0 else 0
    utilization_variance = np.var(list(station_utilizations.values())) if station_utilizations else 0
    efficiency = (K_min / used_stations) * 100 if used_stations > 0 else 0

    # Préparation des résultats détaillés par station
    stations_details = []
    for j in sorted(station_utilizations.keys()):
        stations_details.append({
            "station": j,
            "tasks": assigned_tasks[j],
            "load": round(station_loads[j], 2),
            "utilization": round(station_utilizations[j], 2)
        })

    results = {
        "status": status,
        "optimal": status == "Optimal",
        "used_stations": used_stations,
        "theoretical_min_stations": round(K_min, 2),
        "efficiency": round(efficiency, 2),
        "avg_utilization": round(avg_utilization, 2),
        "max_utilization": round(max_utilization, 2),
        "min_utilization": round(min_utilization, 2) if min_utilization < 100 else 0,
        "utilization_variance": round(utilization_variance, 2),
        "cycle_time": cycle_time,
        "total_weighted_time": round(T, 2),
        "stations": stations_details,
        "models_demand": models
    }

    return results

def generate_equilibrage_chart(results):
    """
    Génère des graphiques pour visualiser l'équilibrage de la ligne mixte
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Couleurs pour ligne mixte (tons violets/pourpres)
    colors = ['#8B5CF6', '#A78BFA', '#C4B5FD', '#DDD6FE', '#EDE9FE', '#F5F3FF']
    
    # Graphique 1 : Utilisation par station
    stations = [s["station"] for s in results["stations"]]
    utilizations = [s["utilization"] for s in results["stations"]]
    
    bars1 = ax1.bar(stations, utilizations, 
                   color=colors[:len(stations)], 
                   alpha=0.8, 
                   edgecolor='black', 
                   linewidth=0.5)
    
    ax1.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Capacité maximale')
    ax1.axhline(y=results["avg_utilization"], color='orange', linestyle=':', alpha=0.8, label='Utilisation moyenne')
    
    ax1.set_xlabel('Station')
    ax1.set_ylabel('Utilisation (%)')
    ax1.set_title('Utilisation des Stations - Équilibrage Ligne Mixte')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres
    for bar, util in zip(bars1, utilizations):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{util:.1f}%', ha='center', va='bottom', fontsize=9)
    
    # Graphique 2 : Charge de travail par station
    loads = [s["load"] for s in results["stations"]]
    
    bars2 = ax2.bar(stations, loads, 
                   color=colors[:len(stations)], 
                   alpha=0.8, 
                   edgecolor='black', 
                   linewidth=0.5)
    
    ax2.axhline(y=results["cycle_time"], color='red', linestyle='--', alpha=0.7, label='Temps de cycle')
    
    ax2.set_xlabel('Station')
    ax2.set_ylabel('Charge de travail (unités de temps)')
    ax2.set_title('Charge de Travail par Station')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres
    for bar, load in zip(bars2, loads):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{load:.1f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    
    # Conversion en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    
    return image_base64

def solve_mixed_assembly_line(data):
    """
    Interface principale pour résoudre le problème d'équilibrage de ligne mixte
    """
    models = tuple(data["models"])
    tasks_data = data["tasks_data"]
    cycle_time = data["cycle_time"]
    
    # Conversion du format d'entrée
    formatted_tasks = []
    for task in tasks_data:
        task_entry = [task["id"]]
        for model in task["models"]:
            predecessors = model["predecessors"] if model["predecessors"] else None
            task_entry.append([predecessors, model["time"]])
        formatted_tasks.append(tuple(task_entry))
    
    results = mixed_assembly_line_scheduling(models, formatted_tasks, cycle_time)
    return results 