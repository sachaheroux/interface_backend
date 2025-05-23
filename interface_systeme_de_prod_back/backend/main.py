from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from backend import spt  # Algorithme SPT
from backend.validation import validate_jobs_data  # Validation externe

app = FastAPI()

# ----------- Modèle d’entrée -----------

class SPTRequest(BaseModel):
    jobs_data: List[List[List[int]]]
    due_dates: List[int]

# ----------- Route principale -----------

@app.post("/spt")
def run_spt(request: SPTRequest):
    jobs_data = request.jobs_data
    due_dates = request.due_dates

    # Validation avancée
    try:
        validate_jobs_data(jobs_data, due_dates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Traitement
    result = spt.schedule(jobs_data, due_dates)

    # Formatage du résultat
    planification = {
        f"Machine {machine}": tasks
        for machine, tasks in result["machines"].items()
    }

    # Construction de la réponse finale
    return {
        "makespan": result["makespan"],
        "flowtime": result["flowtime"],
        "retard_cumule": result["retard_cumule"],
        "completion_times": {f"Job {j}": t for j, t in result["completion_times"].items()},
        "planification": planification
    }


