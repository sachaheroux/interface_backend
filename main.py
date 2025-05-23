from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from backend import spt
from backend.validation import validate_jobs_data
import matplotlib.pyplot as plt
import io

app = FastAPI()

# ✅ CORS élargi temporairement pour Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod, remplace par l'URL Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SPTRequest(BaseModel):
    jobs_data: List[List[List[int]]]
    due_dates: List[int]

@app.post("/spt")
def run_spt(request: SPTRequest):
    jobs_data = request.jobs_data
    due_dates = request.due_dates

    try:
        validate_jobs_data(jobs_data, due_dates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = spt.schedule(jobs_data, due_dates)

    planification = {
        f"Machine {machine}": tasks
        for machine, tasks in result["machines"].items()
    }

    return {
        "makespan": result["makespan"],
        "flowtime": result["flowtime"],
        "retard_cumule": result["retard_cumule"],
        "completion_times": {f"Job {j}": t for j, t in result["completion_times"].items()},
        "planification": planification
    }

@app.post("/spt/gantt")
def run_spt_gantt(request: SPTRequest):
    jobs_data = request.jobs_data
    due_dates = request.due_dates

    try:
        validate_jobs_data(jobs_data, due_dates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = spt.schedule(jobs_data, due_dates)

    fig, ax = plt.subplots(figsize=(10, 3))
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1"]

    for m, tasks in result["machines"].items():
        for t in tasks:
            ax.barh(f"Machine {m}", t["duration"], left=t["start"], color=colors[t["job"] % len(colors)])
            ax.text(t["start"] + t["duration"] / 2, f"Machine {m}", f"J{t['job']}",
                    va="center", ha="center", color="white", fontsize=8)

    ax.set_xlabel("Temps")
    ax.invert_yaxis()
    ax.set_title("Diagramme de Gantt - Flowshop SPT")

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
