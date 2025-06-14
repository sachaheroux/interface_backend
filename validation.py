from typing import List, Dict, Optional, Union
from pydantic import BaseModel

# ----------- Validation des données de jobs -----------

def validate_jobs_data(jobs_data: List[List[List[float]]], due_dates: List[float], job_names: Optional[List[str]] = None):
    """Validation générale pour tous les algorithmes flowshop"""
    if not jobs_data:
        raise ValueError("La liste des jobs est vide.")

    if len(jobs_data) != len(due_dates):
        raise ValueError("Le nombre de due_dates doit être égal au nombre de jobs.")

    nb_taches_reference = len(jobs_data[0])
    machine_ids = set()

    for job_index, job in enumerate(jobs_data):
        job_name = job_names[job_index] if job_names and job_index < len(job_names) else f"Job {job_index}"
        
        if not job:
            raise ValueError(f"Le job '{job_name}' ne contient aucune tâche.")

        if len(job) != nb_taches_reference:
            first_job_name = job_names[0] if job_names and len(job_names) > 0 else "Job 0"
            raise ValueError(f"Tous les jobs doivent contenir le même nombre de tâches (Flowshop). '{job_name}' a {len(job)} tâches, mais '{first_job_name}' en a {nb_taches_reference}. Vérifiez que toutes les lignes ont le même nombre de durées remplies.")

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

def validate_johnson_data(jobs_data: List[List[float]], due_dates: List[float], job_names: Optional[List[str]] = None):
    """Validation spécifique pour l'algorithme de Johnson (exactement 2 machines)"""
    if not jobs_data:
        raise ValueError("La liste des jobs est vide.")

    if len(jobs_data) != len(due_dates):
        raise ValueError("Le nombre de due_dates doit être égal au nombre de jobs.")

    # Vérifier que chaque job a exactement 2 tâches
    for job_index, job in enumerate(jobs_data):
        job_name = job_names[job_index] if job_names and job_index < len(job_names) else f"Job {job_index}"
        
        if not job:
            raise ValueError(f"Le job '{job_name}' ne contient aucune tâche.")
        
        if len(job) != 2:
            raise ValueError(f"L'algorithme de Johnson nécessite exactement 2 machines. Le job '{job_name}' a {len(job)} durées au lieu de 2. Vérifiez que chaque ligne a exactement 2 valeurs de durée.")
        
        # Vérifier que les durées sont valides
        for task_index, duration in enumerate(job):
            if not isinstance(duration, (int, float)):
                raise ValueError(f"La durée {task_index + 1} du job '{job_name}' doit être un nombre.")
            
            if duration < 0:
                raise ValueError(f"La durée {task_index + 1} du job '{job_name}' ne peut pas être négative.")

def validate_johnson_modifie_data(jobs_data: List[List[List[float]]], due_dates: List[float], job_names: Optional[List[str]] = None):
    """Validation spécifique pour l'algorithme de Johnson Modifié (3 machines ou plus)"""
    if not jobs_data:
        raise ValueError("La liste des jobs est vide.")

    if len(jobs_data) != len(due_dates):
        raise ValueError("Le nombre de due_dates doit être égal au nombre de jobs.")

    nb_taches_reference = len(jobs_data[0])
    
    # Vérifier qu'il y a au moins 3 machines
    if nb_taches_reference < 3:
        raise ValueError(f"L'algorithme de Johnson Modifié nécessite au moins 3 machines. Actuellement {nb_taches_reference} machine(s) détectée(s). Ajoutez au moins une machine supplémentaire.")

    # Utiliser la validation générale pour le reste
    validate_jobs_data(jobs_data, due_dates, job_names)

def validate_smith_data(jobs: List[List[float]], job_names: Optional[List[str]] = None):
    """Validation spécifique pour l'algorithme de Smith (exactement 1 machine)"""
    if not jobs:
        raise ValueError("La liste des jobs est vide.")

    # Vérifier que chaque job a exactement 1 tâche
    for job_index, job in enumerate(jobs):
        job_name = job_names[job_index] if job_names and job_index < len(job_names) else f"Job {job_index}"
        
        if not job:
            raise ValueError(f"Le job '{job_name}' ne contient aucune tâche.")
        
        if len(job) != 1:
            raise ValueError(f"L'algorithme de Smith nécessite exactement 1 machine. Le job '{job_name}' a {len(job)} durées au lieu de 1. Vérifiez que chaque ligne a exactement 1 valeur de durée.")
        
        # Vérifier que la durée est valide
        duration = job[0]
        if not isinstance(duration, (int, float)):
            raise ValueError(f"La durée du job '{job_name}' doit être un nombre.")
        
        if duration < 0:
            raise ValueError(f"La durée du job '{job_name}' ne peut pas être négative.")

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
    machine_priorities: Optional[Dict[int, int]] = None  # {machine_id: priority}

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
    setup_times: Optional[Dict[int, Dict[int, Dict[int, float]]]] = None  # {machine_id: {from_job: {to_job: setup_time}}}
    release_times: Optional[Union[List[float], Dict[int, float]]] = None  # Temps d'arrivée des jobs






