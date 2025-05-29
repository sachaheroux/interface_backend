from datetime import datetime, timedelta

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures", machine_names=None, job_names=None):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    # Conversion horaires d'ouverture
    opening_start_hour, opening_start_minute = map(int, opening_hours["start"].split(":"))
    opening_end_hour, opening_end_minute = map(int, opening_hours["end"].split(":"))
    opening_start = timedelta(hours=opening_start_hour, minutes=opening_start_minute)
    opening_end = timedelta(hours=opening_end_hour, minutes=opening_end_minute)
    opening_duration = (opening_end - opening_start).total_seconds() / 60  # en minutes

    # Index des jours de weekend et jours fériés
    weekend_indices = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
        "samedi": 5, "dimanche": 6
    }
    weekend_indexes = {weekend_indices[d] for d in weekend_days if d in weekend_indices}
    feries = {datetime.fromisoformat(d).date() for d in jours_feries}

    # Initialisation de la prochaine heure disponible par machine
    machine_next_available = {m: base_datetime for m in result["machines"].keys()}

    # Groupes = machines
    groups = [
        {"id": int(mid), "title": machine_names[int(mid)] if machine_names else f"Machine {mid}"}
        for mid in result["machines"].keys()
    ]

    # Items = tâches
    items = []
    for machine_id, tasks in result["machines"].items():
        current_time = base_datetime

        for idx, t in enumerate(tasks):
            job_label = job_names[t["job"]] if job_names else f"Job {t['job']}"
            duration_min = t["duration"] * minute_multiplier

            # Reprise du dernier instant disponible
            current_time = machine_next_available[machine_id]

            while True:
                current_date = current_time.date()
                current_weekday = current_time.weekday()

                if current_weekday in weekend_indexes or current_date in feries:
                    current_time += timedelta(days=1)
                    current_time = datetime.combine(current_time.date(), datetime.min.time()) + opening_start
                    continue

                day_start = datetime.combine(current_date, datetime.min.time()) + opening_start
                day_end = datetime.combine(current_date, datetime.min.time()) + opening_end

                # Si tâche ne rentre pas entièrement aujourd’hui, on saute la journée
                if (day_end - current_time).total_seconds() / 60 < duration_min:
                    current_time = datetime.combine(current_time.date() + timedelta(days=1), datetime.min.time()) + opening_start
                    continue

                # OK : on place la tâche
                start_dt = current_time
                end_dt = current_time + timedelta(minutes=duration_min)
                items.append({
                    "id": f"{machine_id}_{idx}",
                    "group": int(machine_id),
                    "title": job_label,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat()
                })
                machine_next_available[machine_id] = end_dt
                break

    # Ajouter des plages vides pour afficher visuellement les congés et fériés
    min_start = min([datetime.fromisoformat(i["start_time"]) for i in items]) if items else base_datetime
    max_end = max([datetime.fromisoformat(i["end_time"]) for i in items]) if items else base_datetime + timedelta(days=1)
    current_day = min_start.date()

    while current_day <= max_end.date():
        if current_day.weekday() in weekend_indexes or current_day in feries:
            label = "Congé" if current_day.weekday() in weekend_indexes else "Férié"
            items.append({
                "id": f"ferie_{current_day}",
                "group": groups[0]["id"],  # afficher sur première machine
                "title": label,
                "start_time": datetime.combine(current_day, datetime.min.time()).isoformat(),
                "end_time": (datetime.combine(current_day, datetime.min.time()) + timedelta(hours=24)).isoformat(),
            })
        current_day += timedelta(days=1)

    return {"groups": groups, "items": items, "opening_hours": opening_hours}

