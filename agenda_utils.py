from datetime import datetime, timedelta

def generer_agenda_json(result, start_datetime_str, opening_hours, weekend_days, jours_feries, unite="heures", machine_names=None, job_names=None):
    base_datetime = datetime.fromisoformat(start_datetime_str)
    unit_multipliers = {"minutes": 1, "heures": 60, "jours": 1440}
    minute_multiplier = unit_multipliers.get(unite, 60)

    weekend_indices = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
        "samedi": 5, "dimanche": 6
    }
    weekend_indexes = {weekend_indices[d] for d in weekend_days if d in weekend_indices}
    feries = {datetime.fromisoformat(d).date() for d in jours_feries if d}

    groups = [
        {"id": int(mid), "title": machine_names[int(mid)] if machine_names else f"Machine {mid}"}
        for mid in result["machines"].keys()
    ]

    # Ajout des événements pour jours fériés et week-ends
    special_days = set()

    items = []
    for machine_id, tasks in result["machines"].items():
        current_dt = base_datetime
        for idx, t in enumerate(tasks):
            duration_min = t["duration"] * minute_multiplier
            while True:
                is_weekend = current_dt.weekday() in weekend_indexes
                is_ferie = current_dt.date() in feries
                day_start = datetime.combine(current_dt.date(), datetime.strptime(opening_hours["start"], "%H:%M").time())
                day_end = datetime.combine(current_dt.date(), datetime.strptime(opening_hours["end"], "%H:%M").time())

                available_time = (day_end - day_start).total_seconds() / 60

                if is_weekend:
                    if current_dt.date() not in special_days:
                        items.append({
                            "id": f"conge_{machine_id}_{current_dt.date()}",
                            "group": int(machine_id),
                            "title": "Congé",
                            "start_time": day_start.isoformat(),
                            "end_time": day_end.isoformat(),
                            "style": "background-color: #f3f4f6; color: #9ca3af;"
                        })
                        special_days.add(current_dt.date())
                    current_dt += timedelta(days=1)
                    continue

                if is_ferie:
                    if current_dt.date() not in special_days:
                        items.append({
                            "id": f"ferie_{machine_id}_{current_dt.date()}",
                            "group": int(machine_id),
                            "title": "Férié",
                            "start_time": day_start.isoformat(),
                            "end_time": day_end.isoformat(),
                            "style": "background-color: #fef3c7; color: #92400e;"
                        })
                        special_days.add(current_dt.date())
                    current_dt += timedelta(days=1)
                    continue

                if available_time >= duration_min:
                    start_dt = day_start
                    end_dt = start_dt + timedelta(minutes=duration_min)
                    job_label = job_names[t["job"]] if job_names else f"Job {t['job']}"
                    items.append({
                        "id": f"{machine_id}_{idx}",
                        "group": int(machine_id),
                        "title": job_label,
                        "start_time": start_dt.isoformat(),
                        "end_time": end_dt.isoformat()
                    })
                    current_dt = end_dt
                    break
                else:
                    current_dt += timedelta(days=1)

    return {"groups": groups, "items": items, "opening_hours": opening_hours}


