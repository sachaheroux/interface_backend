from datetime import datetime, timedelta

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures", machine_names=None, job_names=None, pauses=None):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    # Configurer jours exclus
    weekend_indices = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
        "samedi": 5, "dimanche": 6
    }
    weekend_indexes = {weekend_indices[d] for d in weekend_days if d in weekend_indices}
    feries = {datetime.fromisoformat(d).date() for d in jours_feries if d}

    # Convertir heures d'ouverture
    open_hour = int(opening_hours["start"].split(":")[0])
    open_min = int(opening_hours["start"].split(":")[1])
    close_hour = int(opening_hours["end"].split(":")[0])
    close_min = int(opening_hours["end"].split(":")[1])
    max_daily_minutes = (close_hour * 60 + close_min) - (open_hour * 60 + open_min)

    # Groupes = machines
    groups = [
        {"id": int(mid), "title": machine_names[int(mid)] if machine_names else f"Machine {mid}"}
        for mid in result["machines"].keys()
    ]

    items = []

    # Fonction pour trouver le prochain créneau disponible (évite pauses et heures fermeture)
    def find_next_available_slot(current_dt, duration_minutes):
        while True:
            current_day = current_dt.date()
            weekday = current_dt.weekday()
            
            # Vérifier si c'est un jour ouvré
            if current_day not in feries and weekday not in weekend_indexes:
                # Ajuster à l'heure d'ouverture si nécessaire
                day_start = current_dt.replace(hour=open_hour, minute=open_min, second=0, microsecond=0)
                day_end = current_dt.replace(hour=close_hour, minute=close_min, second=0, microsecond=0)
                
                # Si on est avant l'ouverture, commencer à l'ouverture
                if current_dt < day_start:
                    current_dt = day_start
                
                # CORRECTION CRITIQUE : Vérifier que la tâche FINIT avant la fermeture
                task_end_time = current_dt + timedelta(minutes=duration_minutes)
                if task_end_time <= day_end:
                    # Vérifier les conflits avec les pauses
                    has_pause_conflict = False
                    for pause in pauses:
                        start_time_obj = datetime.strptime(pause["start"], "%H:%M").time()
                        end_time_obj = datetime.strptime(pause["end"], "%H:%M").time()
                        pause_start = current_dt.replace(hour=start_time_obj.hour, minute=start_time_obj.minute, second=0, microsecond=0)
                        pause_end = current_dt.replace(hour=end_time_obj.hour, minute=end_time_obj.minute, second=0, microsecond=0)
                        
                        if current_dt < pause_end and task_end_time > pause_start:
                            # Conflit détecté, décaler après cette pause
                            current_dt = pause_end
                            has_pause_conflict = True
                            break
                    
                    if not has_pause_conflict:
                        return current_dt
                    # Si conflit, recommencer la boucle avec la nouvelle heure
                    continue
            
            # Passer au jour suivant à l'heure d'ouverture
            current_dt = (current_dt + timedelta(days=1)).replace(hour=open_hour, minute=open_min, second=0, microsecond=0)

    # Suivre le temps par machine ET par job pour respecter les contraintes Flowshop
    machine_current_time = {}
    job_current_time = {}
    
    # Structure pour stocker toutes les tâches avec leurs informations de job et machine
    all_tasks = []
    for machine_id_str, tasks in result["machines"].items():
        machine_id = int(machine_id_str)
        for task in tasks:
            all_tasks.append({
                "machine": machine_id,
                "job": task["job"],
                "task_id": task.get("task", 0),
                "duration": task["duration"] * minute_multiplier,
                "original_start": task["start"]
            })
    
    # Trier les tâches par leur temps de début original pour respecter l'ordre optimal
    all_tasks.sort(key=lambda t: t["original_start"])
    
    # Initialiser les temps
    for machine_id_str in result["machines"].keys():
        machine_current_time[int(machine_id_str)] = base_datetime
    
    # CORRECTION : Gérer les pauses une seule fois, avant la boucle
    if not pauses:
        pauses = [{"start": "12:00", "end": "13:00", "name": "Pause déjeuner"}]
    
    print(f"🔍 PAUSES UTILISÉES DANS AGENDA: {pauses}")
    
    items = []
    
    for task_info in all_tasks:
        machine_id = task_info["machine"]
        job_id = task_info["job"]
        duration_minutes = task_info["duration"]
        
        # Pour Flowshop: une tâche ne peut pas commencer avant que :
        # 1. La machine soit libre
        # 2. Le job précédent sur cette machine soit fini
        # 3. La tâche précédente du même job soit finie (contrainte Flowshop)
        
        # Temps minimum = max(temps machine, temps job précédent)
        machine_available_time = machine_current_time.get(machine_id, base_datetime)
        job_available_time = job_current_time.get(job_id, base_datetime)
        
        start_time = max(machine_available_time, job_available_time)
            
        # Trouver le prochain créneau disponible (évite automatiquement les pauses)
        actual_start = find_next_available_slot(start_time, duration_minutes)
        actual_end = actual_start + timedelta(minutes=duration_minutes)
        
        # Créer la tâche (les pauses sont automatiquement évitées)
        job_label = job_names[job_id] if job_names and isinstance(job_id, int) and job_id < len(job_names) else f"Job {job_id}"
        items.append({
            "id": f"{machine_id}_{job_id}_{task_info['task_id']}",
            "group": machine_id,
            "title": job_label,
            "start_time": actual_start.isoformat(),
            "end_time": actual_end.isoformat(),
            "job_info": task_info,
            "task_type": "production"
        })
        
        # Mettre à jour le temps de la machine ET du job (contrainte Flowshop)
        machine_current_time[machine_id] = actual_end
        job_current_time[job_id] = actual_end

    return {
        "groups": groups,
        "items": items,
        "opening_hours": opening_hours,
        "pauses": pauses,
        "total_machines": len(groups),
        "planning_period": {
            "start": base_datetime.isoformat(),
            "estimated_end": max(machine_current_time.values()).isoformat() if machine_current_time else base_datetime.isoformat()
        },
        "agenda_config": {
            "opening_hours": opening_hours,
            "weekend_days": weekend_days,
            "jours_feries": jours_feries,
            "pauses": pauses
        }
    }


