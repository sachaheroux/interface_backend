from typing import List, Dict, Optional, Union
from pydantic import BaseModel

# ----------- Validation des données de jobs -----------

def validate_jobs_data(jobs_data: List[List[List[float]]], due_dates: List[float]):
    if not jobs_data:
        raise ValueError("La liste des jobs est vide.")

    if len(jobs_data) != len(due_dates):
        raise ValueError("Le nombre de due_dates doit être égal au nombre de jobs.")

    nb_taches_reference = len(jobs_data[0])
    machine_ids = set()

    for job_index, job in enumerate(jobs_data):
        if not job:
            raise ValueError(f"Le job {job_index} ne contient aucune tâche.")

        if len(job) != nb_taches_reference:
            raise ValueError("Tous les jobs doivent contenir le même nombre de tâches (Flowshop).")

        for task_index, task in enumerate(job):
            if not (isinstance(task, list) or isinstance(task, tuple)) or len(task) != 2:
                raise ValueError(f"Tâche {task_index} du job {job_index} doit être une liste [machine, durée].")

            machine, duration = task

            try:
                machine = int(machine)
            except Exception:
                raise ValueError(f"La machine dans la tâche {task_index} du job {job_index} doit être convertible en entier (ex: 0, 1.0).")

            if not isinstance(duration, (int, float)):
                raise ValueError(f"La durée dans la tâche {task_index} du job {job_index} doit être un nombre.")

            if machine < 0 or duration < 0:
                raise ValueError(f"Tâche {task_index} du job {job_index} contient des valeurs négatives.")

            machine_ids.add(machine)

    max_machine_index = max(machine_ids)
    if max_machine_index >= nb_taches_reference:
        raise ValueError(
            f"Un indice de machine ({max_machine_index}) est supérieur ou égal au nombre de tâches ({nb_taches_reference})."
        )

# ----------- Modèles Pydantic utilisés dans main.py -----------

class ExtendedRequest(BaseModel):
    jobs_data: List[List[List[float]]]
    due_dates: List[float]
    unite: str = "heures"
    job_names: List[str]
    machine_names: Optional[List[str]] = None
    
    # Champs pour flowshop avec machines multiples
    stage_names: Optional[List[str]] = None
    machines_per_stage: Optional[List[int]] = None

    # Champs avancés optionnels
    agenda_start_datetime: Optional[str] = None
    opening_hours: Optional[Dict[str, str]] = None
    weekend_days: Optional[List[str]] = None
    jours_feries: Optional[List[str]] = None
    due_date_times: Optional[List[str]] = None
    pauses: Optional[List[Dict[str, str]]] = None

class FlexibleFlowshopRequest(BaseModel):
    jobs_data: List[List[List[List[float]]]]  # job -> task -> alternatives -> [machine_id, duration]
    due_dates: List[float]
    unite: str = "heures"
    job_names: List[str]
    machine_names: Optional[List[str]] = None
    
    # Champs pour flowshop avec machines multiples
    stage_names: Optional[List[str]] = None
    machines_per_stage: Optional[List[int]] = None

    # Champs avancés optionnels
    agenda_start_datetime: Optional[str] = None
    opening_hours: Optional[Dict[str, str]] = None
    weekend_days: Optional[List[str]] = None
    jours_feries: Optional[List[str]] = None
    due_date_times: Optional[List[str]] = None
    pauses: Optional[List[Dict[str, str]]] = None

class JohnsonRequest(BaseModel):
    jobs_data: List[List[float]]
    due_dates: List[float]
    unite: str = "heures"
    job_names: List[str]
    machine_names: List[str]

class JohnsonModifieRequest(BaseModel):
    jobs_data: List[List[List[float]]]
    due_dates: List[float]
    unite: str = "heures"
    job_names: List[str]
    machine_names: List[str]

class SmithRequest(BaseModel):
    jobs: List[List[float]]
    unite: str = "heures"
    job_names: List[str] = None

class JobshopSPTRequest(BaseModel):
    jobs_data: List[List[List[float]]]
    due_dates: List[float]
    job_names: List[str]
    machine_names: List[str]
    unite: str = "heures"






