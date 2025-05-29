from datetime import datetime, timedelta

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures", machine_names=None, job_names=None):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    # Configurer jours exclus
    weekend_indices = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
        "samedi": 5, "dimanche": 6
    }
    weekend_indexes = {weekend_indices[d] for d in weekend_days if d in weekend_indices}
    feries = {datetime.fromisoformat(d).date() for d in jours_feries}

    # Convertir heures d'ouverture
    open_hour = int(opening_hours["start"].split(":")[0])
    open_min = int(opening_hours["start"].split(":")[1])
    close_hour = int(opening_hours["end"].split(":")[0])
    close_min = int(opening_hours["end"].split(":")[1])
    opening_start_minutes = open_hour * 60 + open_min
    opening_end_minutes = close_hour * 60 + close_min
    max_daily_minutes = opening_end_minutes - opening_start_minutes

    # Groupes = machines
    groups = [
        {"id": int(mid), "title": machine_names[int(mid)] if machine_names else f"Machine {mid}"}
        for mid in result["machines"].keys()
    ]

    items = []

    # Dictionnaire de suivi par machine du temps courant (en minutes)
    current_time_by_machine = {int(mid): 0 for mid in result["machines"].keys()}

    for machine_id_str, tasks in result["machines"].items():
        machine_id = int(machine_id_str)
        current_minutes = 0
        current_date = base_datetime

        for idx, t in tasks:
            duration_minutes = t["duration"] * minute_multiplier

            # Avancer le temps jusqu’à un jour ouvré et non férié
            while True:
                current_day = current_date.date()
                weekday = current_date.weekday()
                if current_day not in feries and weekday not in weekend_indexes:
                    break
                current_date += timedelta(days=1)
                current_minutes = 0

            # Calcul du temps disponible dans la journée
            start_of_day = current_date.replace(hour=open_hour, minute=open_min, second=0, microsecond=0)
            end_of_day = current_date.replace(hour=close_hour, minute=close_min, second=0, microsecond=0)
            available_minutes_today = int((end_of_day - current_date).total_seconds() / 60)

            # Si la tâche ne rentre pas dans la journée, avancer au jour suivant
            if duration_minutes > available_minutes_today:
                current_date = current_date + timedelta(days=1)
                current_date = current_date.replace(hour=open_hour, minute=open_min, second=0, microsecond=0)
                continue  # Réévaluer cette tâche au prochain tour

            start_dt = current_date
            end_dt = current_date + timedelta(minutes=duration_minutes)

            job_label = job_names[t["job"]] if job_names else f"Job {t['job']}"
            items.append({
                "id": f"{machine_id}_{idx}",
                "group": machine_id,
                "title": job_label,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat()
            })

            current_date = end_dt  # avancer à la fin de la tâche

    # Ajouter les blocs "férié" et "congé"
    special_items = []
    for day in range(30):  # vérifier les 30 premiers jours à partir de base_datetime
        day_date = base_datetime.date() + timedelta(days=day)
        label = None
        if day_date in feries:
            label = "Férié"
        elif day_date.weekday() in weekend_indexes:
            label = "Congé"

        if label:
            start_dt = datetime.combine(day_date, datetime.min.time())
            end_dt = start_dt + timedelta(hours=24)
            special_items.append({
                "id": f"special_{day}",
                "group": groups[0]["id"],  # juste pour avoir une référence
                "title": label,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "bgColor": "#e5e7eb"
            })

    return {
        "groups": groups,
        "items": items + special_items,
        "opening_hours": opening_hours
    }


