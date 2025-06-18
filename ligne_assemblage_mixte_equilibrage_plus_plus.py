from pulp import *
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import base64
import math

def mixed_assembly_line_scheduling_plus_plus(models, tasks_data, cycle_time, optimize_balance=True, allow_station_reduction=False):
    """
    Algorithme d'équilibrage de ligne d'assemblage mixte ++
    Approche bi-objectif :
    1. Minimiser le nombre de stations
    2. Minimiser l'écart des taux d'utilisation (max - min)
    """
    # Calcul du temps total pondéré par les modèles
    T = sum([sum(np.multiply(models, [task[i][1] for i in range(1, len(task))])) for task in tasks_data])
    T = float(T)
    K_min = T / cycle_time
    
    # Extraction des tâches et construction du dictionnaire des prédécesseurs
    tasks = [task[0] for task in tasks_data]
    
    # Construction du dictionnaire des prédécesseurs
    predecessors = {task[0]: [pred for sublist in [task[i][0] for i in range(1, len(task))] for pred in (sublist if isinstance(sublist, list) else [sublist])] for task in tasks_data}

    # Calcul des temps de traitement pondérés par la demande de chaque modèle
    weighted_processing_times = {}
    for task in tasks_data:
        task_id = task[0]
        weighted_time = sum(np.multiply(models, [task[i][1] for i in range(1, len(task))]))
        weighted_processing_times[task_id] = float(weighted_time)

    try:
        # ÉTAPE 1 : Minimisation du nombre de stations
        print("ÉTAPE 1 : Minimisation du nombre de stations...")
        
        # Estimation du nombre maximum de stations nécessaires
        estimated_stations = int(np.ceil(K_min)) + 3
        max_stations = min(estimated_stations, len(tasks) + 2)
        stations = list(range(1, max_stations + 1))
        
        # Création du problème de programmation linéaire - Étape 1
        prob1 = LpProblem("MixedAssemblyLineScheduling_Step1", LpMinimize)

        # Variables de décision - Étape 1
        y1 = LpVariable.dicts("Station_Step1", [(i,j) for i in tasks for j in stations], 0, 1, LpBinary)
        
        # Fonction objective - Étape 1 : minimiser le nombre de stations
        prob1 += lpSum([j * y1[(i,j)] for i in tasks for j in stations]), "MinimizeStations"

        # Contraintes - Étape 1
        # 1. Chaque tâche doit être assignée à exactement une station
        for i in tasks:
            prob1 += lpSum([y1[(i,j)] for j in stations]) == 1, f"Each_task_assigned_once_step1_{i}"

        # 2. Contrainte de temps de cycle pour chaque station
        for j in stations:
            prob1 += lpSum([weighted_processing_times[i]*y1[(i,j)] for i in tasks]) <= cycle_time, f"Cycle_time_constraint_step1_{j}"

        # 3. Contraintes de précédence
        counter = 1
        for i in tasks:
            has_precedence = any(pred is not None for pred in predecessors[i])
            if has_precedence:
                all_predecessors = set()
                for pred in predecessors[i]:
                    if pred is not None:
                        if isinstance(pred, list):
                            all_predecessors.update(pred)
                        else:
                            all_predecessors.add(pred)
                
                for p in all_predecessors:
                    prob1 += lpSum([j*y1[(i,j)] for j in stations]) >= lpSum([j*y1[(p,j)] for j in stations]), f"Precedence_constraint_step1_{counter}"
                    counter += 1

        # Résolution - Étape 1
        prob1.solve(PULP_CBC_CMD(msg=0, timeLimit=60))
        
        if LpStatus[prob1.status] != "Optimal":
            raise Exception(f"Étape 1 échouée : {LpStatus[prob1.status]}")
        
        # Extraction du nombre minimum de stations
        min_stations_needed = 0
        step1_assignment = {}
        for i in tasks:
            for j in stations:
                if y1[(i,j)].varValue and y1[(i,j)].varValue > 0:
                    min_stations_needed = max(min_stations_needed, j)
                    step1_assignment[i] = j
        
        print(f"Nombre minimum de stations trouvé : {min_stations_needed}")
        
        # Si l'optimisation d'équilibrage n'est pas demandée, retourner le résultat de l'étape 1
        if not optimize_balance:
            return _format_results_step1(step1_assignment, min_stations_needed, models, tasks_data, cycle_time, weighted_processing_times, K_min)
        
        # ÉTAPE 2 : Minimisation de l'écart des taux d'utilisation
        print("ÉTAPE 2 : Minimisation de l'écart des taux d'utilisation...")
        
        if allow_station_reduction:
            print("Mode réduction de stations activé - test de toutes les combinaisons...")
            return _optimize_with_station_reduction(tasks, predecessors, weighted_processing_times, cycle_time, min_stations_needed, models, tasks_data, K_min)
        else:
            # Mode standard : optimisation simple avec nombre de stations fixe
            stations_step2 = list(range(1, min_stations_needed + 1))
            
            print(f"Optimisation avec {min_stations_needed} stations...")
            prob2 = LpProblem("MixedAssemblyLineScheduling_Step2", LpMinimize)
            y2 = LpVariable.dicts("Station_Step2", [(i,j) for i in tasks for j in stations_step2], 0, 1, LpBinary)
            
            # Objectif : minimiser l'utilisation maximale pour équilibrer
            max_util = LpVariable("MaxUtil", 0, 1, LpContinuous)
            prob2 += max_util, "MinimizeMaxUtilization"

            # Contraintes - Étape 2
            for i in tasks:
                prob2 += lpSum([y2[(i,j)] for j in stations_step2]) == 1, f"Each_task_assigned_once_step2_{i}"

            for j in stations_step2:
                # Contrainte de capacité normale
                prob2 += lpSum([weighted_processing_times[i]*y2[(i,j)] for i in tasks]) <= cycle_time, f"Cycle_time_constraint_step2_{j}"
                # Contrainte pour l'utilisation maximale
                prob2 += lpSum([weighted_processing_times[i]*y2[(i,j)] for i in tasks]) <= max_util * cycle_time, f"MaxUtil_{j}"

            # Contraintes de précédence
            counter = 1
            for i in tasks:
                has_precedence = any(pred is not None for pred in predecessors[i])
                if has_precedence:
                    all_predecessors = set()
                    for pred in predecessors[i]:
                        if pred is not None:
                            if isinstance(pred, list):
                                all_predecessors.update(pred)
                            else:
                                all_predecessors.add(pred)
                    
                    for p in all_predecessors:
                        prob2 += lpSum([j*y2[(i,j)] for j in stations_step2]) >= lpSum([j*y2[(p,j)] for j in stations_step2]), f"Precedence_constraint_step2_{counter}"
                        counter += 1

            prob2.solve(PULP_CBC_CMD(msg=0, timeLimit=120))
            
            if LpStatus[prob2.status] != "Optimal":
                print(f"Étape 2 échouée : {LpStatus[prob2.status]}, utilisation du résultat de l'étape 1")
                return _format_results_step1(step1_assignment, min_stations_needed, models, tasks_data, cycle_time, weighted_processing_times, K_min)
            
            # Extraction des résultats - Étape 2
            step2_assignment = {}
            for i in tasks:
                for j in stations_step2:
                    if y2[(i,j)].varValue and y2[(i,j)].varValue > 0:
                        step2_assignment[i] = j
            
            # Calcul de l'écart d'utilisation
            station_utilizations = []
            for j in stations_step2:
                tasks_in_station = [i for i in tasks if step2_assignment.get(i) == j]
                if tasks_in_station:
                    station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
                    utilization = (station_load / cycle_time) * 100
                    station_utilizations.append(utilization)
            
            if station_utilizations:
                utilization_gap = max(station_utilizations) - min(station_utilizations)
            else:
                utilization_gap = 0
            
            print(f"Écart d'utilisation calculé : {utilization_gap:.2f}%")
            
            return _format_results_step2(step2_assignment, min_stations_needed, [], models, tasks_data, cycle_time, weighted_processing_times, K_min, utilization_gap)

    except Exception as e:
        print(f"Erreur dans l'algorithme ++ : {str(e)}")
        # Fallback vers l'algorithme heuristique standard
        return _fallback_heuristic(models, tasks_data, cycle_time, weighted_processing_times, K_min)

def _optimize_with_station_reduction(tasks, predecessors, weighted_processing_times, cycle_time, min_stations_needed, models, tasks_data, K_min):
    """
    Optimise l'équilibrage en testant toutes les combinaisons possibles de réduction de stations
    avec doublement de capacité. Choisit la solution avec le plus petit écart d'utilisation.
    """
    best_solution = None
    best_gap = float('inf')
    best_num_stations = min_stations_needed
    
    print(f"Test des combinaisons de 1 à {min_stations_needed} stations...")
    
    # Tester toutes les possibilités de 1 à min_stations_needed stations
    for num_stations in range(1, min_stations_needed + 1):
        print(f"  Test avec {num_stations} stations...")
        
        try:
            stations = list(range(1, num_stations + 1))
            
            # Création du problème de programmation linéaire
            prob = LpProblem(f"OptimizeWithReduction_{num_stations}stations", LpMinimize)

            # Variables de décision
            y = LpVariable.dicts("Station", [(i,j) for i in tasks for j in stations], 0, 1, LpBinary)
            double = LpVariable.dicts("Double", stations, 0, 1, LpBinary)  # 1 si station a capacité doublée
            
            # Fonction objective : minimiser le nombre de stations doublées
            prob += lpSum([double[j] for j in stations]), "MinimizeDoubledStations"

            # Contraintes
            # 1. Chaque tâche doit être assignée à exactement une station
            for i in tasks:
                prob += lpSum([y[(i,j)] for j in stations]) == 1, f"Each_task_assigned_once_{i}"

            # 2. Contrainte de temps de cycle pour chaque station (avec capacité possiblement doublée)
            for j in stations:
                station_capacity = cycle_time * (1 + double[j])  # Capacité normale ou doublée
                prob += lpSum([weighted_processing_times[i]*y[(i,j)] for i in tasks]) <= station_capacity, f"Cycle_time_constraint_{j}"

            # 3. Contraintes de précédence
            counter = 1
            for i in tasks:
                has_precedence = any(pred is not None for pred in predecessors[i])
                if has_precedence:
                    all_predecessors = set()
                    for pred in predecessors[i]:
                        if pred is not None:
                            if isinstance(pred, list):
                                all_predecessors.update(pred)
                            else:
                                all_predecessors.add(pred)
                    
                    for p in all_predecessors:
                        prob += lpSum([j*y[(i,j)] for j in stations]) >= lpSum([j*y[(p,j)] for j in stations]), f"Precedence_constraint_{counter}"
                        counter += 1

            # Résolution
            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))
            
            if LpStatus[prob.status] == "Optimal":
                # Extraction des résultats
                assignment = {}
                doubled_stations = []
                
                for i in tasks:
                    for j in stations:
                        if y[(i,j)].varValue and y[(i,j)].varValue > 0:
                            assignment[i] = j
                
                for j in stations:
                    if double[j].varValue and double[j].varValue > 0.5:
                        doubled_stations.append(j)
                
                # Calcul manuel de l'écart d'utilisation
                station_utilizations = []
                for j in stations:
                    tasks_in_station = [i for i in tasks if assignment.get(i) == j]
                    if tasks_in_station:
                        station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
                        station_capacity = cycle_time * (2 if j in doubled_stations else 1)
                        utilization = (station_load / station_capacity) * 100
                        station_utilizations.append(utilization)
                
                if station_utilizations:
                    max_utilization_value = max(station_utilizations)
                    min_utilization_value = min(station_utilizations)
                    utilization_gap = max_utilization_value - min_utilization_value
                else:
                    utilization_gap = 0
                
                # Debug : afficher les détails de l'assignation
                station_details = {}
                for i in tasks:
                    for j in stations:
                        if y[(i,j)].varValue and y[(i,j)].varValue > 0:
                            if j not in station_details:
                                station_details[j] = []
                            station_details[j].append(i)
                
                print(f"    Solution trouvée : {num_stations} stations, écart = {utilization_gap:.2f}%")
                print(f"    Assignations : {station_details}")
                print(f"    Stations doublées : {doubled_stations}")
                print(f"    Utilisations : {[f'{u:.1f}%' for u in station_utilizations]}")
                
                # Vérifier si cette solution est meilleure
                if utilization_gap < best_gap or (utilization_gap == best_gap and num_stations < best_num_stations):
                    best_solution = {
                        'assignment': assignment,
                        'num_stations': num_stations,
                        'doubled_stations': doubled_stations,
                        'utilization_gap': utilization_gap,
                        'max_util': max_utilization_value,
                        'min_util': min_utilization_value
                    }
                    best_gap = utilization_gap
                    best_num_stations = num_stations
                    print(f"    *** Nouvelle meilleure solution ! ***")
            else:
                print(f"    Pas de solution faisable avec {num_stations} stations")
                
        except Exception as e:
            print(f"    Erreur avec {num_stations} stations : {str(e)}")
            continue
    
    if best_solution is None:
        print("Aucune solution trouvée, utilisation de l'heuristique de fallback")
        return _fallback_heuristic(models, tasks_data, cycle_time, weighted_processing_times, K_min)
    
    print(f"Meilleure solution : {best_solution['num_stations']} stations, écart = {best_solution['utilization_gap']:.2f}%")
    
    return _format_results_step2(
        best_solution['assignment'], 
        best_solution['num_stations'], 
        best_solution['doubled_stations'], 
        models, 
        tasks_data, 
        cycle_time, 
        weighted_processing_times, 
        K_min, 
        best_solution['utilization_gap'],
        station_reduction_used=True  # Indiquer que la réduction a été utilisée
    )

def _format_results_step1(assignment, num_stations, models, tasks_data, cycle_time, weighted_processing_times, K_min):
    """
    Formate les résultats de l'étape 1 (minimisation des stations uniquement)
    """
    # Calcul des métriques par station
    station_assignments = {j: [] for j in range(1, num_stations + 1)}
    station_loads = {}
    station_utilizations = {}
    
    for task, station in assignment.items():
        station_assignments[station].append(task)
    
    total_utilization = 0
    max_utilization = 0
    min_utilization = 100
    
    for j in range(1, num_stations + 1):
        tasks_in_station = station_assignments[j]
        if tasks_in_station:
            station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
            station_utilization = (station_load / cycle_time) * 100
            
            station_loads[j] = station_load
            station_utilizations[j] = station_utilization
            
            total_utilization += station_utilization
            max_utilization = max(max_utilization, station_utilization)
            if station_utilization > 0:
                min_utilization = min(min_utilization, station_utilization)
    
    avg_utilization = total_utilization / num_stations if num_stations > 0 else 0
    utilization_variance = float(np.var(list(station_utilizations.values()))) if station_utilizations else 0
    efficiency = (K_min / num_stations) * 100 if num_stations > 0 else 0
    utilization_gap = max_utilization - min_utilization
    
    # Préparation des résultats détaillés par station
    stations_details = []
    for j in sorted(station_assignments.keys()):
        if station_assignments[j]:  # Seulement les stations utilisées
            stations_details.append({
                "station": int(j),
                "tasks": station_assignments[j],
                "load": round(float(station_loads[j]), 2),
                "utilization": round(float(station_utilizations[j]), 2),
                "doubled_capacity": False
            })
    
    return {
        "status": "Optimal",
        "optimal": True,
        "method": "Programmation Linéaire ++ (Étape 1 uniquement)",
        "info": f"✅ Minimisation du nombre de stations uniquement ({len(tasks_data)} tâches, {num_stations} stations)",
        "optimization_step": "Étape 1 : Minimisation des stations",
        "balance_optimized": False,
        "stations_used": int(num_stations),
        "theoretical_minimum": round(float(K_min), 2),
        "efficiency": round(float(efficiency), 2),
        "average_utilization": round(float(avg_utilization), 2),
        "max_utilization": round(float(max_utilization), 2),
        "min_utilization": round(float(min_utilization), 2) if min_utilization < 100 else 0,
        "utilization_gap": round(float(utilization_gap), 2),
        "utilization_variance": round(float(utilization_variance), 2),
        "cycle_time": float(cycle_time),
        "total_weighted_time": round(float(sum([sum(np.multiply(models, [task[i][1] for i in range(1, len(task))])) for task in tasks_data])), 2),
        "station_assignments": stations_details,
        "doubled_stations": [],
        "models_demand": list(models)
    }

def _format_results_step2(assignment, num_stations, doubled_stations, models, tasks_data, cycle_time, weighted_processing_times, K_min, utilization_gap, station_reduction_used=False):
    """
    Formate les résultats de l'étape 2 (optimisation de l'équilibrage)
    """
    # Calcul des métriques par station
    station_assignments = {j: [] for j in range(1, num_stations + 1)}
    station_loads = {}
    station_utilizations = {}
    
    for task, station in assignment.items():
        station_assignments[station].append(task)
    
    total_utilization = 0
    max_utilization = 0
    min_utilization = 100
    
    for j in range(1, num_stations + 1):
        tasks_in_station = station_assignments[j]
        if tasks_in_station:
            station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
            # Capacité de la station (normale ou doublée)
            station_capacity = cycle_time * (2 if j in doubled_stations else 1)
            station_utilization = (station_load / station_capacity) * 100
            
            station_loads[j] = station_load
            station_utilizations[j] = station_utilization
            
            total_utilization += station_utilization
            max_utilization = max(max_utilization, station_utilization)
            if station_utilization > 0:
                min_utilization = min(min_utilization, station_utilization)
    
    avg_utilization = total_utilization / num_stations if num_stations > 0 else 0
    utilization_variance = float(np.var(list(station_utilizations.values()))) if station_utilizations else 0
    efficiency = (K_min / num_stations) * 100 if num_stations > 0 else 0
    
    # Préparation des résultats détaillés par station
    stations_details = []
    for j in sorted(station_assignments.keys()):
        if station_assignments[j]:  # Seulement les stations utilisées
            stations_details.append({
                "station": int(j),
                "tasks": station_assignments[j],
                "load": round(float(station_loads[j]), 2),
                "utilization": round(float(station_utilizations[j]), 2),
                "doubled_capacity": j in doubled_stations
            })
    
    method_description = "Programmation Linéaire ++ (Bi-objectif)"
    if station_reduction_used:
        method_description += " avec réduction de stations"
    
    info_text = f"✅ Optimisation bi-objectif complète ({len(tasks_data)} tâches, {num_stations} stations"
    if len(doubled_stations) > 0:
        info_text += f", {len(doubled_stations)} stations doublées"
    if station_reduction_used:
        info_text += ", réduction de stations activée"
    info_text += ")"
    
    return {
        "status": "Optimal",
        "optimal": True,
        "method": method_description,
        "info": info_text,
        "optimization_step": "Étape 2 : Minimisation de l'écart d'utilisation",
        "balance_optimized": True,
        "station_reduction_used": station_reduction_used,
        "stations_used": int(num_stations),
        "theoretical_minimum": round(float(K_min), 2),
        "efficiency": round(float(efficiency), 2),
        "average_utilization": round(float(avg_utilization), 2),
        "max_utilization": round(float(max_utilization), 2),
        "min_utilization": round(float(min_utilization), 2) if min_utilization < 100 else 0,
        "utilization_gap": round(float(utilization_gap), 2),
        "utilization_variance": round(float(utilization_variance), 2),
        "cycle_time": float(cycle_time),
        "total_weighted_time": round(float(sum([sum(np.multiply(models, [task[i][1] for i in range(1, len(task))])) for task in tasks_data])), 2),
        "station_assignments": stations_details,
        "doubled_stations": doubled_stations,
        "models_demand": list(models)
    }

def _fallback_heuristic(models, tasks_data, cycle_time, weighted_processing_times, K_min):
    """
    Algorithme heuristique de fallback en cas d'échec de la programmation linéaire
    """
    tasks = [task[0] for task in tasks_data]
    predecessors = {task[0]: [pred for sublist in [task[i][0] for i in range(1, len(task))] for pred in (sublist if isinstance(sublist, list) else [sublist])] for task in tasks_data}
    
    # Algorithme glouton simple
    stations = []
    current_station = 1
    station_loads = {}
    station_tasks = {}
    assigned_tasks = set()

    def get_available_tasks():
        available = []
        for task in tasks:
            if task not in assigned_tasks:
                task_predecessors = [p for p in predecessors.get(task, []) if p is not None]
                if all(pred in assigned_tasks for pred in task_predecessors):
                    available.append(task)
        return available

    while len(assigned_tasks) < len(tasks):
        if current_station not in station_loads:
            station_loads[current_station] = 0
            station_tasks[current_station] = []

        station_has_capacity = True
        while station_has_capacity:
            available_tasks = get_available_tasks()
            if not available_tasks:
                break

            available_tasks.sort(key=lambda t: weighted_processing_times[t], reverse=True)
            
            task_assigned = False
            for task in available_tasks:
                if station_loads[current_station] + weighted_processing_times[task] <= cycle_time:
                    station_tasks[current_station].append(task)
                    station_loads[current_station] += weighted_processing_times[task]
                    assigned_tasks.add(task)
                    task_assigned = True
                    break
            
            if not task_assigned:
                station_has_capacity = False

        if len(assigned_tasks) < len(tasks):
            current_station += 1

    # Calcul des métriques
    used_stations = len(station_tasks)
    total_utilization = 0
    max_utilization = 0
    min_utilization = 100
    station_utilizations = {}

    for station in range(1, used_stations + 1):
        utilization = (station_loads[station] / cycle_time) * 100
        station_utilizations[station] = utilization
        total_utilization += utilization
        max_utilization = max(max_utilization, utilization)
        if utilization > 0:
            min_utilization = min(min_utilization, utilization)

    avg_utilization = total_utilization / used_stations if used_stations > 0 else 0
    utilization_variance = float(np.var(list(station_utilizations.values()))) if station_utilizations else 0
    efficiency = (K_min / used_stations) * 100 if used_stations > 0 else 0
    utilization_gap = max_utilization - min_utilization

    stations_details = []
    for station in range(1, used_stations + 1):
        stations_details.append({
            "station": int(station),
            "tasks": station_tasks[station],
            "load": round(float(station_loads[station]), 2),
            "utilization": round(float(station_utilizations[station]), 2),
            "doubled_capacity": False
        })

    return {
        "status": "Heuristique",
        "optimal": False,
        "method": "Algorithme Glouton ++ (Fallback)",
        "warning": f"⚠️ Fallback vers l'heuristique. Solution approximative mais rapide.",
        "optimization_step": "Fallback",
        "balance_optimized": False,
        "stations_used": int(used_stations),
        "theoretical_minimum": round(float(K_min), 2),
        "efficiency": round(float(efficiency), 2),
        "average_utilization": round(float(avg_utilization), 2),
        "max_utilization": round(float(max_utilization), 2),
        "min_utilization": round(float(min_utilization), 2) if min_utilization < 100 else 0,
        "utilization_gap": round(float(utilization_gap), 2),
        "utilization_variance": round(float(utilization_variance), 2),
        "cycle_time": float(cycle_time),
        "total_weighted_time": round(float(sum([sum(np.multiply(models, [task[i][1] for i in range(1, len(task))])) for task in tasks_data])), 2),
        "station_assignments": stations_details,
        "doubled_stations": [],
        "models_demand": list(models)
    }

def generate_equilibrage_plus_plus_chart(results):
    """
    Génère des graphiques pour visualiser l'équilibrage de la ligne mixte ++
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Couleurs pour ligne mixte ++ (tons verts/bleus)
    colors = ['#10B981', '#34D399', '#6EE7B7', '#A7F3D0', '#D1FAE5', '#ECFDF5']
    
    # Graphique 1 : Utilisation par station avec indication des capacités doublées
    stations = [s["station"] for s in results["station_assignments"]]
    utilizations = [s["utilization"] for s in results["station_assignments"]]
    doubled_stations_list = results.get("doubled_stations", [])
    
    # Couleurs différentes pour les stations normales et doublées
    bar_colors = []
    for i, station in enumerate(stations):
        if station in doubled_stations_list:
            bar_colors.append('#EF4444')  # Rouge pour les stations doublées
        else:
            bar_colors.append(colors[i % len(colors)])  # Vert/bleu pour les stations normales
    
    bars1 = ax1.bar(stations, utilizations, 
                   color=bar_colors, 
                   alpha=0.8, 
                   edgecolor='black', 
                   linewidth=0.5)
    
    ax1.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Capacité maximale')
    ax1.axhline(y=results["average_utilization"], color='orange', linestyle=':', alpha=0.8, label='Utilisation moyenne')
    
    # Ligne pour montrer l'écart min-max
    if results.get("balance_optimized", False):
        ax1.axhline(y=results["max_utilization"], color='purple', linestyle='-', alpha=0.6, label=f'Max: {results["max_utilization"]:.1f}%')
        ax1.axhline(y=results["min_utilization"], color='purple', linestyle='-', alpha=0.6, label=f'Min: {results["min_utilization"]:.1f}%')
    
    ax1.set_xlabel('Station')
    ax1.set_ylabel('Utilisation (%)')
    title = 'Utilisation des Stations - Équilibrage Ligne Mixte ++'
    if results.get("balance_optimized", False):
        title += f'\nÉcart optimisé: {results.get("utilization_gap", 0):.1f}%'
    ax1.set_title(title)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres avec indication des capacités doublées
    for bar, util, station in zip(bars1, utilizations, stations):
        height = bar.get_height()
        label = f'{util:.1f}%'
        if station in doubled_stations_list:
            label += '\n(2x Cap.)'
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                label, ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Graphique 2 : Charge de travail par station
    loads = [s["load"] for s in results["station_assignments"]]
    
    bars2 = ax2.bar(stations, loads, 
                   color=bar_colors, 
                   alpha=0.8, 
                   edgecolor='black', 
                   linewidth=0.5)
    
    ax2.axhline(y=results["cycle_time"], color='red', linestyle='--', alpha=0.7, label='Temps de cycle normal')
    ax2.axhline(y=results["cycle_time"] * 2, color='darkred', linestyle=':', alpha=0.7, label='Temps de cycle doublé')
    
    ax2.set_xlabel('Station')
    ax2.set_ylabel('Charge de travail (unités de temps)')
    ax2.set_title('Charge de Travail par Station')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres
    for bar, load, station in zip(bars2, loads, stations):
        height = bar.get_height()
        label = f'{load:.1f}'
        if station in doubled_stations_list:
            label += '\n(2x Cap.)'
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                label, ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    
    # Conversion en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    
    return image_base64

def solve_mixed_assembly_line_equilibrage_plus_plus(tasks_data, models, cycle_time, optimize_balance=True, allow_station_reduction=False):
    """
    Résout le problème d'équilibrage de ligne d'assemblage mixte avec optimisation bi-objectif simplifiée.
    
    1. Premier objectif : Minimiser le nombre de stations
    2. Deuxième objectif : Minimiser l'écart entre les taux d'utilisation max et min
    """
    try:
        # Validation des données d'entrée
        if not tasks_data or not models or cycle_time <= 0:
            raise ValueError("Données d'entrée invalides")

        print(f"=== ALGORITHME ÉQUILIBRAGE ++ SIMPLIFIÉ ===")
        print(f"Optimisation activée : {optimize_balance}")
        print(f"Temps de cycle : {cycle_time}")

        # Préparation des données
        tasks = [task['id'] for task in tasks_data]
        predecessors = {}
        
        for task in tasks_data:
            task_id = task['id']
            pred_list = []
            if task.get('predecessors'):
                if isinstance(task['predecessors'], list):
                    pred_list = [p for p in task['predecessors'] if p is not None]
                elif task['predecessors'] is not None:
                    pred_list = [task['predecessors']]
            predecessors[task_id] = pred_list if pred_list else [None]

        # Calcul des temps de traitement pondérés
        weighted_processing_times = {}
        total_demand = sum(model['demand'] for model in models)
        
        for task in tasks_data:
            task_id = task['id']
            weighted_time = 0
            for model in models:
                model_time = next((t['time'] for t in task['times'] if t['model'] == model['model']), 0)
                weight = model['demand'] / total_demand
                weighted_time += model_time * weight
            weighted_processing_times[task_id] = weighted_time

        print(f"Temps pondérés calculés : {weighted_processing_times}")

        # ÉTAPE 1 : Trouver le nombre minimum de stations
        print("\n=== ÉTAPE 1 : Nombre minimum de stations ===")
        
        # Estimation du nombre minimum de stations nécessaires
        total_work = sum(weighted_processing_times.values())
        K_min = max(1, math.ceil(total_work / cycle_time))
        print(f"Estimation K_min : {K_min} stations")

        # Recherche du nombre minimum réel par programmation linéaire
        min_stations_needed = None
        step1_assignment = None
        
        for K in range(K_min, len(tasks) + 1):
            print(f"Test avec {K} stations...")
            stations = list(range(1, K + 1))
            
            prob1 = LpProblem("MixedAssemblyLineScheduling_Step1", LpMinimize)
            y1 = LpVariable.dicts("Station_Step1", [(i,j) for i in tasks for j in stations], 0, 1, LpBinary)
            
            # Fonction objective - Étape 1 : faisabilité
            prob1 += 0, "Feasibility"

            # Contraintes - Étape 1
            for i in tasks:
                prob1 += lpSum([y1[(i,j)] for j in stations]) == 1, f"Each_task_assigned_once_step1_{i}"

            for j in stations:
                prob1 += lpSum([weighted_processing_times[i]*y1[(i,j)] for i in tasks]) <= cycle_time, f"Cycle_time_constraint_step1_{j}"

            counter = 1
            for i in tasks:
                has_precedence = any(pred is not None for pred in predecessors[i])
                if has_precedence:
                    all_predecessors = set()
                    for pred in predecessors[i]:
                        if pred is not None:
                            if isinstance(pred, list):
                                all_predecessors.update(pred)
                            else:
                                all_predecessors.add(pred)
                    
                    for p in all_predecessors:
                        prob1 += lpSum([j*y1[(i,j)] for j in stations]) >= lpSum([j*y1[(p,j)] for j in stations]), f"Precedence_constraint_step1_{counter}"
                        counter += 1

            prob1.solve(PULP_CBC_CMD(msg=0, timeLimit=60))
            
            if LpStatus[prob1.status] == "Optimal":
                print(f"✅ Solution trouvée avec {K} stations")
                min_stations_needed = K
                
                step1_assignment = {}
                for i in tasks:
                    for j in stations:
                        if y1[(i,j)].varValue and y1[(i,j)].varValue > 0:
                            step1_assignment[i] = j
                break
            else:
                print(f"❌ Pas de solution avec {K} stations")

        if min_stations_needed is None:
            raise ValueError("Aucune solution faisable trouvée")

        print(f"Nombre minimum de stations nécessaires : {min_stations_needed}")

        # Si l'optimisation n'est pas activée, retourner le résultat de l'étape 1
        if not optimize_balance:
            print("Optimisation désactivée, retour du résultat de l'étape 1")
            return _format_results_step1(step1_assignment, min_stations_needed, models, tasks_data, cycle_time, weighted_processing_times, K_min)

        # ÉTAPE 2 : Optimisation de l'équilibrage avec nombre de stations fixe
        print(f"\n=== ÉTAPE 2 : Optimisation de l'équilibrage ===")
        print(f"Optimisation avec {min_stations_needed} stations...")
        
        stations_step2 = list(range(1, min_stations_needed + 1))
        solution = _solve_for_stations(tasks, stations_step2, predecessors, weighted_processing_times, cycle_time)
        
        if solution:
            gap = solution['gap']
            print(f"Solution optimisée : écart = {gap:.2f}%")
            return _format_results_optimized(solution['assignment'], min_stations_needed, models, tasks_data, cycle_time, weighted_processing_times, K_min, gap, False)
        else:
            print("Optimisation échouée, retour de l'étape 1")
            return _format_results_step1(step1_assignment, min_stations_needed, models, tasks_data, cycle_time, weighted_processing_times, K_min)

    except Exception as e:
        print(f"Erreur dans l'algorithme : {str(e)}")
        raise ValueError(f"Erreur lors de la résolution : {str(e)}")

def _solve_for_stations(tasks, stations, predecessors, weighted_processing_times, cycle_time):
    """
    Résout le problème d'optimisation pour un nombre donné de stations.
    Retourne la solution ou None si pas faisable.
    """
    try:
        prob = LpProblem("OptimizeBalance", LpMinimize)
        y = LpVariable.dicts("Station", [(i,j) for i in tasks for j in stations], 0, 1, LpBinary)
        
        # Objectif : minimiser l'utilisation maximale (pour équilibrer)
        max_util = LpVariable("MaxUtil", 0, 1, LpContinuous)
        prob += max_util, "MinimizeMaxUtilization"
        
        # Contraintes
        for i in tasks:
            prob += lpSum([y[(i,j)] for j in stations]) == 1, f"Task_assigned_{i}"
        
        for j in stations:
            # Contrainte de capacité
            prob += lpSum([weighted_processing_times[i]*y[(i,j)] for i in tasks]) <= cycle_time, f"Capacity_{j}"
            # Contrainte pour l'utilisation maximale
            prob += lpSum([weighted_processing_times[i]*y[(i,j)] for i in tasks]) <= max_util * cycle_time, f"MaxUtil_{j}"
        
        # Contraintes de précédence
        counter = 1
        for i in tasks:
            has_precedence = any(pred is not None for pred in predecessors[i])
            if has_precedence:
                all_predecessors = set()
                for pred in predecessors[i]:
                    if pred is not None:
                        if isinstance(pred, list):
                            all_predecessors.update(pred)
                        else:
                            all_predecessors.add(pred)
                
                for p in all_predecessors:
                    prob += lpSum([j*y[(i,j)] for j in stations]) >= lpSum([j*y[(p,j)] for j in stations]), f"Prec_{counter}"
                    counter += 1
        
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))
        
        if LpStatus[prob.status] == "Optimal":
            assignment = {}
            for i in tasks:
                for j in stations:
                    if y[(i,j)].varValue and y[(i,j)].varValue > 0:
                        assignment[i] = j
            
            # Calcul de l'écart d'utilisation
            station_utilizations = []
            for j in stations:
                tasks_in_station = [i for i in tasks if assignment.get(i) == j]
                if tasks_in_station:
                    station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
                    utilization = (station_load / cycle_time) * 100
                    station_utilizations.append(utilization)
            
            if station_utilizations:
                gap = max(station_utilizations) - min(station_utilizations)
                return {
                    'assignment': assignment,
                    'gap': gap,
                    'utilizations': station_utilizations
                }
        
        return None
        
    except Exception as e:
        print(f"Erreur dans _solve_for_stations : {str(e)}")
        return None

def _format_results_optimized(assignment, num_stations, models, tasks_data, cycle_time, weighted_processing_times, K_min, utilization_gap, allow_station_reduction):
    """
    Formate les résultats de l'étape 2 (optimisation de l'équilibrage)
    """
    # Calcul des métriques par station
    station_assignments = {j: [] for j in range(1, num_stations + 1)}
    station_loads = {}
    station_utilizations = {}
    
    for task, station in assignment.items():
        station_assignments[station].append(task)
    
    total_utilization = 0
    max_utilization = 0
    min_utilization = 100
    
    for j in range(1, num_stations + 1):
        tasks_in_station = station_assignments[j]
        if tasks_in_station:
            station_load = sum([weighted_processing_times[i] for i in tasks_in_station])
            # Capacité normale de la station
            station_utilization = (station_load / cycle_time) * 100
            
            station_loads[j] = station_load
            station_utilizations[j] = station_utilization
            
            total_utilization += station_utilization
            max_utilization = max(max_utilization, station_utilization)
            if station_utilization > 0:
                min_utilization = min(min_utilization, station_utilization)
    
    avg_utilization = total_utilization / num_stations if num_stations > 0 else 0
    utilization_variance = float(np.var(list(station_utilizations.values()))) if station_utilizations else 0
    efficiency = (K_min / num_stations) * 100 if num_stations > 0 else 0
    
    # Préparation des résultats détaillés par station
    stations_details = []
    for j in sorted(station_assignments.keys()):
        if station_assignments[j]:  # Seulement les stations utilisées
            stations_details.append({
                "station": int(j),
                "tasks": station_assignments[j],
                "load": round(float(station_loads[j]), 2),
                "utilization": round(float(station_utilizations[j]), 2),
                "doubled_capacity": False  # Plus de doublement de capacité
            })
    
    method_description = "Programmation Linéaire ++ (Bi-objectif simplifié)"
    if allow_station_reduction:
        method_description += " avec réduction de stations"
    
    info_text = f"✅ Optimisation bi-objectif simplifiée ({len(tasks_data)} tâches, {num_stations} stations"
    if allow_station_reduction:
        info_text += ", réduction de stations activée"
    info_text += ")"
    
    # Calcul du temps total pondéré
    total_weighted_time = 0
    for task in tasks_data:
        task_id = task['id']
        weighted_time = 0
        total_demand = sum(model['demand'] for model in models)
        for model in models:
            model_time = next((t['time'] for t in task['times'] if t['model'] == model['model']), 0)
            weight = model['demand'] / total_demand
            weighted_time += model_time * weight
        total_weighted_time += weighted_time
    
    return {
        "status": "Optimal",
        "optimal": True,
        "method": method_description,
        "info": info_text,
        "optimization_step": "Étape 2 : Minimisation de l'écart d'utilisation",
        "balance_optimized": True,
        "station_reduction_used": allow_station_reduction,
        "stations_used": int(num_stations),
        "theoretical_minimum": round(float(K_min), 2),
        "efficiency": round(float(efficiency), 2),
        "average_utilization": round(float(avg_utilization), 2),
        "max_utilization": round(float(max_utilization), 2),
        "min_utilization": round(float(min_utilization), 2) if min_utilization < 100 else 0,
        "utilization_gap": round(float(utilization_gap), 2),
        "utilization_variance": round(float(utilization_variance), 2),
        "cycle_time": float(cycle_time),
        "total_weighted_time": round(float(total_weighted_time), 2),
        "station_assignments": stations_details,
        "doubled_stations": [],  # Plus de stations doublées
        "models_demand": list(models)
    }

def solve_mixed_assembly_line_plus_plus(data):
    """
    Interface principale pour résoudre le problème d'équilibrage de ligne mixte ++
    """
    models = tuple(data["models"])
    tasks_data = data["tasks_data"]
    cycle_time = data["cycle_time"]
    optimize_balance = data.get("optimize_balance", True)
    allow_station_reduction = data.get("allow_station_reduction", False)
    
    # Conversion du format d'entrée vers l'ancien format
    formatted_tasks = []
    for task in tasks_data:
        task_entry = [task["id"]]
        for model in task["models"]:
            predecessors = model["predecessors"] if model["predecessors"] else None
            task_entry.append([predecessors, model["time"]])
        formatted_tasks.append(tuple(task_entry))
    
    # Appel de l'ancienne fonction qui fonctionne
    results = mixed_assembly_line_scheduling_plus_plus(models, formatted_tasks, cycle_time, optimize_balance, allow_station_reduction)
    return results 