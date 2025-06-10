from typing import List
def validate_jobs_data(jobs_data: List[List[List[int]]], due_dates: List[int]):
    """
    Validation complète des données :
    - Format des tâches
    - Valeurs positives
    - Nombre de due dates
    - Cohérence des indices de machine
    - Uniformité du nombre de tâches (flowshop)
    """
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
            if not isinstance(machine, int) or not isinstance(duration, int):
                raise ValueError(f"Tâche {task_index} du job {job_index} contient des valeurs non entières.")
            if machine < 0 or duration < 0:
                raise ValueError(f"Tâche {task_index} du job {job_index} contient des valeurs négatives.")

            machine_ids.add(machine)

    max_machine_index = max(machine_ids)
    if max_machine_index >= nb_taches_reference:
        raise ValueError(
            f"Un indice de machine ({max_machine_index}) est supérieur au nombre de tâches ({nb_taches_reference})."
        )

