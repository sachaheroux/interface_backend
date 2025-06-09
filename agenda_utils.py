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

    # Fonction pour trouver le prochain créneau disponible (peut commencer même si finit le jour suivant)
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
                
                # NOUVEAU : Permettre de commencer même si la tâche se termine le jour suivant
                # On vérifie juste qu'on peut commencer dans les heures d'ouverture
                if current_dt < day_end:
                    return current_dt
            
            # Passer au jour suivant à l'heure d'ouverture
            current_dt = (current_dt + timedelta(days=1)).replace(hour=open_hour, minute=open_min, second=0, microsecond=0)

    # Fonction pour gérer les pauses intelligemment (avec division si nécessaire + entre jours)
    def handle_pauses(start_dt, duration_minutes, configured_pauses, machine_id, job_id, task_info, job_names):
        current_items = []
        remaining_duration = duration_minutes
        current_start = start_dt
        part_counter = 1
        
        max_iterations = 10  # Sécurité contre les boucles infinies
        iteration_count = 0
        
        while remaining_duration > 0 and iteration_count < max_iterations:
            iteration_count += 1
            
            # Calculer la fin de journée pour le jour courant
            current_day_end = current_start.replace(hour=close_hour, minute=close_min, second=0, microsecond=0)
            
            # Calculer combien de temps on peut travailler aujourd'hui
            time_until_close = max(0, int((current_day_end - current_start).total_seconds() / 60))
            work_today = min(remaining_duration, time_until_close)
            
            if work_today <= 0:
                # Plus de temps aujourd'hui, passer au jour suivant
                current_start = find_next_available_slot(current_start + timedelta(days=1), remaining_duration)
                continue
                
            current_end = current_start + timedelta(minutes=work_today)
            
            # Chercher la première pause qui interfère
            conflicting_pause = None
            earliest_pause_start = None
            
            for pause in configured_pauses:
                try:
                    start_time_obj = datetime.strptime(pause["start"], "%H:%M").time()
                    end_time_obj = datetime.strptime(pause["end"], "%H:%M").time()
                    pause_start = current_start.replace(hour=start_time_obj.hour, minute=start_time_obj.minute, second=0, microsecond=0)
                    pause_end = current_start.replace(hour=end_time_obj.hour, minute=end_time_obj.minute, second=0, microsecond=0)
                    
                    # Si la tâche chevauche avec cette pause
                    if current_start < pause_end and current_end > pause_start:
                        if earliest_pause_start is None or pause_start < earliest_pause_start:
                            conflicting_pause = pause
                            earliest_pause_start = pause_start
                except Exception:
                    continue
            
            if conflicting_pause is None:
                # Aucune pause ne gêne, créer la partie pour aujourd'hui
                job_label = job_names[job_id] if job_names and isinstance(job_id, int) and job_id < len(job_names) else f"Job {job_id}"
                
                if work_today == remaining_duration:
                    # Tâche complète dans la journée
                    suffix = f" ({part_counter}/{part_counter})" if part_counter > 1 else ""
                else:
                    # Partie de tâche
                    suffix = f" (partie {part_counter})"
                
                current_items.append({
                    "id": f"{machine_id}_{job_id}_{task_info['task_id']}_part{part_counter}",
                    "group": machine_id,
                    "title": f"{job_label}{suffix}",
                    "start_time": current_start.isoformat(),
                    "end_time": current_end.isoformat(),
                    "job_info": task_info,
                    "task_type": "production"
                })
                
                remaining_duration -= work_today
                if remaining_duration > 0:
                    # Continuer le jour suivant
                    part_counter += 1
                    current_start = find_next_available_slot(current_start + timedelta(days=1), remaining_duration)
                else:
                    break
            else:
                # Une pause interfère, diviser la tâche
                start_time_obj = datetime.strptime(conflicting_pause["start"], "%H:%M").time()
                end_time_obj = datetime.strptime(conflicting_pause["end"], "%H:%M").time()
                pause_start = current_start.replace(hour=start_time_obj.hour, minute=start_time_obj.minute, second=0, microsecond=0)
                pause_end = current_start.replace(hour=end_time_obj.hour, minute=end_time_obj.minute, second=0, microsecond=0)
                
                if current_start < pause_start:
                    # Créer une partie avant la pause
                    part_end = min(pause_start, current_end)  # Ne pas dépasser la fin de journée
                    part_duration = int((part_end - current_start).total_seconds() / 60)
                    
                    if part_duration > 0:
                        job_label = job_names[job_id] if job_names and isinstance(job_id, int) and job_id < len(job_names) else f"Job {job_id}"
                        
                        current_items.append({
                            "id": f"{machine_id}_{job_id}_{task_info['task_id']}_part{part_counter}",
                            "group": machine_id,
                            "title": f"{job_label} (partie {part_counter})",
                            "start_time": current_start.isoformat(),
                            "end_time": part_end.isoformat(),
                            "job_info": task_info,
                            "task_type": "production"
                        })
                        
                        remaining_duration -= part_duration
                        part_counter += 1
                
                # Continuer après la pause
                current_start = find_next_available_slot(pause_end, remaining_duration)
        
        # Si on sort de la boucle à cause de max_iterations, créer le reste de la tâche
        if remaining_duration > 0 and iteration_count >= max_iterations:
            job_label = job_names[job_id] if job_names and isinstance(job_id, int) and job_id < len(job_names) else f"Job {job_id}"
            final_end = current_start + timedelta(minutes=remaining_duration)
            
            current_items.append({
                "id": f"{machine_id}_{job_id}_{task_info['task_id']}_final",
                "group": machine_id,
                "title": f"{job_label} (fin)",
                "start_time": current_start.isoformat(),
                "end_time": final_end.isoformat(),
                "job_info": task_info,
                "task_type": "production"
            })
        
        return current_items

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
            
        # Trouver le prochain créneau disponible
        actual_start = find_next_available_slot(start_time, duration_minutes)
        
        # Gérer les pauses avec division si nécessaire
        task_items = handle_pauses(actual_start, duration_minutes, pauses, machine_id, job_id, task_info, job_names)
        items.extend(task_items)
        
        # Calculer la fin réelle en prenant la dernière partie de la tâche
        if task_items:
            actual_end = datetime.fromisoformat(task_items[-1]["end_time"])
        else:
            actual_end = actual_start + timedelta(minutes=duration_minutes)
        
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


