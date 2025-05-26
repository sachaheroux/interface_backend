from typing import List, Union

def validate_jobs_data(jobs_data: List[List[List[Union[int, float]]]], due_dates: List[Union[int, float]]):
    """
    Validation complète des données :
    - Format des tâches
    - Valeurs positives
    - Nombre de due dates
    - Cohérence des indices de machine
    - Uniformité du nombre de tâches (Flowshop)
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

            if not isinstance(machine, int):
                raise ValueError(f"La machine dans la tâche {task_index} du job {job_index} doit être un entier.")
            if not isinstance(duration, (int, float)):
                raise ValueError(f"La durée dans la tâche {task_index} du job {job_index} doit être un entier ou un nombre décimal.")

            if machine < 0 or duration <= 0:
                raise ValueError(f"Tâche {task_index} du job {job_index} contient des valeurs négatives ou nulles.")

            machine_ids.add(machine)

    for i, due in enumerate(due_dates):
        if not isinstance(due, (int, float)):
            raise ValueError(f"La date due du job {i} doit être un entier ou un nombre décimal.")
        if due <= 0:
            raise ValueError(f"La date due du job {i} doit être positive.")

    max_machine_index = max(machine_ids)
    if max_machine_index >= nb_taches_reference:
        raise ValueError(
            f"Un indice de machine ({max_machine_index}) est supérieur au nombre de tâches ({nb_taches_reference})."
        )

