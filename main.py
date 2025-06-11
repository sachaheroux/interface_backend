from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List
import matplotlib.pyplot as plt
import io
import base64

import spt
import edd
import johnson
import johnson_modifie
import smith
import contraintes
import jobshop_spt
import jobshop_edd
import jobshop_contraintes
import ligne_assemblage_precedence
import ligne_assemblage_comsoal
import ligne_assemblage_lpt
import ligne_assemblage_pl
import ligne_assemblage_mixte_goulot
import ligne_assemblage_mixte_equilibrage
import ligne_transfert_buffer_buzzacott
from validation import validate_jobs_data, ExtendedRequest, JohnsonRequest, JohnsonModifieRequest, SmithRequest, JobshopSPTRequest
from agenda_utils import generer_agenda_json
from fms_sac_a_dos import solve_fms_sac_a_dos, generate_fms_sac_a_dos_chart, FMSSacADosRequest
from fms_sac_a_dos_pl import fms_sac_a_dos_pl, generate_fms_sac_a_dos_pl_chart
from fms_sac_a_dos_glouton import solve_fms_sac_a_dos_glouton, generate_fms_sac_a_dos_glouton_chart, FMSSacADosGloutonRequest
from fms_lots_production_glouton import solve_fms_lots_production_glouton, generate_fms_lots_production_glouton_chart, FMSLotsProductionGloutonRequest
from fms_lots_production_mip import solve_fms_lots_production_mip, generate_fms_lots_production_mip_chart, FMSLotsProductionMIPRequest
from fms_lots_chargement_heuristique import solve_fms_lots_chargement_heuristique, generate_fms_lots_chargement_heuristique_chart, FMSLotsChargementHeuristiqueRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- Gantt utilitaire -----------

def create_gantt_figure(result, title: str, unite="heures", job_names=None, machine_names=None):
    fig, ax = plt.subplots(figsize=(10, 3))
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316"]

    for m_idx, (m, tasks) in enumerate(result["machines"].items()):
        label = machine_names[int(m)] if machine_names else f"Machine {int(m)}"
        for t in tasks:
            job_idx = t["job"] if isinstance(t["job"], int) else job_names.index(t["job"])
            job_label = job_names[job_idx] if job_names else f"J{job_idx}"
            color = colors[job_idx % len(colors)]
            ax.barh(label, t["duration"], left=t["start"], color=color)
            ax.text(t["start"] + t["duration"] / 2, label, job_label,
                    va="center", ha="center", color="white", fontsize=8)

    ax.set_xlabel(f"Temps ({unite})")
    ax.invert_yaxis()
    ax.set_title(title)
    plt.tight_layout()
    return fig

# ----------- Jobshop SPT -----------

@app.post("/jobshop/spt")
def run_jobshop_spt(request: JobshopSPTRequest):
    try:
        result = jobshop_spt.planifier_jobshop_spt(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/spt/gantt")
def run_jobshop_spt_gantt(request: JobshopSPTRequest):
    try:
        result = jobshop_spt.planifier_jobshop_spt(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = request.machine_names.index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["end"] - t["start"]
            })
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop SPT",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Jobshop EDD -----------

@app.post("/jobshop/edd")
def run_jobshop_edd(request: JobshopSPTRequest):
    try:
        result = jobshop_edd.planifier_jobshop_edd(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/edd/gantt")
def run_jobshop_edd_gantt(request: JobshopSPTRequest):
    try:
        result = jobshop_edd.planifier_jobshop_edd(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = request.machine_names.index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["end"] - t["start"]
            })
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop EDD",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Jobshop Contraintes -----------

@app.post("/jobshop/contraintes")
def run_jobshop_contraintes(request: JobshopSPTRequest):
    try:
        result = jobshop_contraintes.planifier_jobshop_contraintes(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/contraintes/gantt")
def run_jobshop_contraintes_gantt(request: JobshopSPTRequest):
    try:
        result = jobshop_contraintes.planifier_jobshop_contraintes(request.job_names, request.machine_names, request.jobs_data, request.due_dates)
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = request.machine_names.index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["duration"]
            })
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop Contraintes (CP)",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Algorithme SPT -----------

@app.post("/spt")
def run_spt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)
        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/spt/gantt")
def run_spt_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Flowshop SPT",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/spt/agenda")
def run_spt_agenda(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = spt.schedule(request.jobs_data, request.due_dates)
        agenda_json = generer_agenda_json(
            result=result,
            start_datetime_str=request.agenda_start_datetime,
            opening_hours=request.opening_hours,
            weekend_days=request.weekend_days,
            jours_feries=request.jours_feries,
            unite=request.unite,
            machine_names=request.machine_names,
            job_names=request.job_names
        )
        return JSONResponse(content=agenda_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- EDD -----------

@app.post("/edd")
def run_edd(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = edd.schedule(request.jobs_data, request.due_dates)
        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/edd/gantt")
def run_edd_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = edd.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Flowshop EDD",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Johnson -----------

@app.post("/johnson")
def run_johnson(request: JohnsonRequest):
    try:
        result = johnson.schedule(request.jobs_data, request.due_dates)
        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson/gantt")
def run_johnson_gantt(request: JohnsonRequest):
    try:
        result = johnson.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Johnson",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Johnson Modifié -----------

@app.post("/johnson_modifie")
def run_johnson_modifie(request: JohnsonModifieRequest):
    try:
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)
        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson_modifie/gantt")
def run_johnson_modifie_gantt(request: JohnsonModifieRequest):
    try:
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Johnson modifié",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Smith -----------

@app.post("/smith")
def run_smith(request: SmithRequest):
    try:
        result = smith.smith_algorithm(request.jobs)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/smith/gantt")
def run_smith_gantt(request: SmithRequest):
    try:
        result = smith.smith_algorithm(request.jobs)
        fig = smith.generate_gantt(result["sequence"], request.jobs,
                                   unite=request.unite,
                                   job_names=request.job_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Contraintes -----------

@app.post("/contraintes")
def run_contraintes(request: ExtendedRequest):
    try:
        # Vérifier si c'est une demande de flowshop hybride
        if hasattr(request, 'stage_names') and hasattr(request, 'machines_per_stage'):
            # Flowshop Hybride
            from algorithms.flowshop_hybride import flowshop_hybride_contraintes
            result = flowshop_hybride_contraintes(
                request.jobs_data, 
                request.machines_per_stage, 
                request.job_names, 
                request.stage_names, 
                request.due_dates
            )
            
            # Formatage pour flowshop hybride
            return {
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {request.stage_names[int(m)]: tasks for m, tasks in result["machines"].items()},
                "raw_machines": result["machines"],
                "gantt_url": result.get("gantt_url")
            }
        else:
            # Flowshop classique
            validate_jobs_data(request.jobs_data, request.due_dates)
            result = contraintes.schedule(request.jobs_data, request.due_dates)
            return {
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {request.machine_names[int(m)]: tasks for m, tasks in result["machines"].items()},
                "raw_machines": result["machines"]  # Données brutes utilisées par le Gantt
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes/gantt")
def run_contraintes_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = contraintes.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Contraintes (CP)",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes/agenda")
def run_contraintes_agenda(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        result = contraintes.schedule(request.jobs_data, request.due_dates)
        
        # Paramètres par défaut si pas fournis
        start_datetime = getattr(request, 'agenda_start_datetime', None) or "2025-06-01T08:00:00"
        opening_hours = getattr(request, 'opening_hours', None) or {"start": "08:00", "end": "17:00"}
        weekend_days = getattr(request, 'weekend_days', None) or ["samedi", "dimanche"]
        jours_feries = getattr(request, 'jours_feries', None) or []
        due_date_times = getattr(request, 'due_date_times', None) or []
        pauses = getattr(request, 'pauses', None) or [{"start": "12:00", "end": "13:00", "name": "Pause déjeuner"}]
        
        agenda_data = generer_agenda_json(
            result, 
            start_datetime, 
            opening_hours, 
            weekend_days, 
            jours_feries, 
            request.unite,
            request.machine_names,
            request.job_names,
            pauses
        )
        
        # Ajouter les informations de due dates
        agenda_data["due_dates"] = {
            request.job_names[i]: request.due_dates[i] for i in range(len(request.job_names))
        }
        agenda_data["due_date_times"] = due_date_times
        
        return agenda_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Ligne d'assemblage - Précédence -----------

class PrecedenceRequest:
    def __init__(self, tasks_data: List[dict], unite: str = "minutes"):
        self.tasks_data = tasks_data
        self.unite = unite

@app.post("/ligne_assemblage/precedence")
def run_precedence_analysis(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_precedence.create_precedence_diagram(task_tuples, unite)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/precedence/diagram")
def run_precedence_diagram(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_precedence.create_precedence_diagram(task_tuples, unite)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(result["graphique"])
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/comsoal")
def run_comsoal_analysis(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        seed = request.get("seed", None)
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_comsoal.comsoal_algorithm(task_tuples, cycle_time, unite, seed)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/comsoal/chart")
def run_comsoal_chart(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        seed = request.get("seed", None)
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_comsoal.comsoal_algorithm(task_tuples, cycle_time, unite, seed)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(result["graphique"])
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/lpt")
def run_lpt_analysis(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_lpt.lpt_algorithm(task_tuples, cycle_time, unite)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/lpt/chart")
def run_lpt_chart(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_lpt.lpt_algorithm(task_tuples, cycle_time, unite)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(result["graphique"])
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/pl")
def run_pl_analysis(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_pl.pl_algorithm(task_tuples, cycle_time, unite)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/pl/chart")
def run_pl_chart(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples
        task_tuples = []
        for task in tasks_data:
            task_id = task.get("id")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_pl.pl_algorithm(task_tuples, cycle_time, unite)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(result["graphique"])
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage_mixte/goulot")
def run_goulot_analysis(request: dict):
    try:
        models_demand = request.get("models_demand", [4, 6])
        task_times = request.get("task_times", [[3, 3], [2, 3]])
        s1 = request.get("s1", 0.5)
        s2 = request.get("s2", 0.5)
        unite = request.get("unite", "minutes")
        
        result = ligne_assemblage_mixte_goulot.variation_goulot_algorithm(models_demand, task_times, s1, s2, unite)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage_mixte/goulot/chart")
def run_goulot_chart(request: dict):
    try:
        models_demand = request.get("models_demand", [4, 6])
        task_times = request.get("task_times", [[3, 3], [2, 3]])
        s1 = request.get("s1", 0.5)
        s2 = request.get("s2", 0.5)
        unite = request.get("unite", "minutes")
        
        result = ligne_assemblage_mixte_goulot.variation_goulot_algorithm(models_demand, task_times, s1, s2, unite)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(result["graphique"])
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage_mixte/equilibrage")
def run_equilibrage_analysis(request: dict):
    try:
        result = ligne_assemblage_mixte_equilibrage.solve_mixed_assembly_line(request)
        return result
    except Exception as e:
        print(f"Error in equilibrage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur algorithme équilibrage: {str(e)}")

@app.post("/ligne_assemblage_mixte/equilibrage/chart")
def run_equilibrage_chart(request: dict):
    try:
        result = ligne_assemblage_mixte_equilibrage.solve_mixed_assembly_line(request)
        
        # Générer le graphique
        image_base64 = ligne_assemblage_mixte_equilibrage.generate_equilibrage_chart(result)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(image_base64)
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_transfert/buffer_buzzacott")
def run_buffer_buzzacott_analysis(request: dict):
    try:
        result = ligne_transfert_buffer_buzzacott.solve_buffer_buzzacott(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_transfert/buffer_buzzacott/chart")
def run_buffer_buzzacott_chart(request: dict):
    try:
        result = ligne_transfert_buffer_buzzacott.solve_buffer_buzzacott(request)
        
        # Générer le graphique
        image_base64 = ligne_transfert_buffer_buzzacott.generate_buffer_buzzacott_chart(result)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(image_base64)
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- FMS Sac à Dos -----------

@app.post("/fms/sac_a_dos")
def run_fms_sac_a_dos_analysis(request: dict):
    try:
        print(f"Received request: {request}")  # Debug
        fms_request = FMSSacADosRequest(**request)
        print("Request validation successful")  # Debug
        result = solve_fms_sac_a_dos(fms_request)
        print("Algorithm execution successful")  # Debug
        return result
    except Exception as e:
        print(f"Error in FMS endpoint: {str(e)}")  # Debug
        import traceback
        traceback.print_exc()  # Debug
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fms/sac_a_dos/chart")
def run_fms_sac_a_dos_chart(request: dict):
    try:
        print(f"Received chart request: {request}")
        fms_request = FMSSacADosRequest(**request)
        result = solve_fms_sac_a_dos(fms_request)
        
        # Générer le graphique
        image_base64 = generate_fms_sac_a_dos_chart(result)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(image_base64)
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        print(f"Error in FMS chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------- FMS Sac à Dos PL -----------

@app.post("/fms/sac_a_dos_pl")
def run_fms_sac_a_dos_pl_analysis(request: dict):
    try:
        print(f"Received request: {request}")
        print("Request validation successful")
        
        result = fms_sac_a_dos_pl(
            vente_unite=request["vente_unite"],
            cout_mp_unite=request["cout_mp_unite"],
            demande_periode=request["demande_periode"],
            temps_fabrication_unite=request["temps_fabrication_unite"],
            cout_op=request["cout_op"],
            capacite_max=request["capacite_max"],
            noms_produits=request["noms_produits"],
            unite=request["unite"]
        )
        print("Algorithm execution successful")
        return result
    except Exception as e:
        print(f"Error in FMS PL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fms/sac_a_dos_pl/chart")
def run_fms_sac_a_dos_pl_chart(request: dict):
    try:
        print(f"Received PL chart request: {request}")
        buffer = generate_fms_sac_a_dos_pl_chart(
            vente_unite=request["vente_unite"],
            cout_mp_unite=request["cout_mp_unite"],
            demande_periode=request["demande_periode"],
            temps_fabrication_unite=request["temps_fabrication_unite"],
            cout_op=request["cout_op"],
            capacite_max=request["capacite_max"],
            noms_produits=request["noms_produits"],
            unite=request["unite"]
        )
        return StreamingResponse(buffer, media_type="image/png")
    except Exception as e:
        print(f"Error in FMS PL chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------- FMS Sac à Dos Glouton -----------

@app.post("/fms/sac_a_dos_glouton")
def run_fms_sac_a_dos_glouton_analysis(request: dict):
    try:
        print(f"Received glouton request: {request}")
        fms_request = FMSSacADosGloutonRequest(**request)
        print("Glouton request validation successful")
        result = solve_fms_sac_a_dos_glouton(fms_request)
        print("Glouton algorithm execution successful")
        return result
    except Exception as e:
        print(f"Error in FMS glouton endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fms/sac_a_dos_glouton/chart")
def run_fms_sac_a_dos_glouton_chart(request: dict):
    try:
        print(f"Received glouton chart request: {request}")
        fms_request = FMSSacADosGloutonRequest(**request)
        result = solve_fms_sac_a_dos_glouton(fms_request)
        
        # Générer le graphique
        image_base64 = generate_fms_sac_a_dos_glouton_chart(result)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(image_base64)
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        print(f"Error in FMS glouton chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------- FMS Lots de Production Glouton -----------

@app.post("/fms/lots_production_glouton")
def run_fms_lots_production_glouton_analysis(request: dict):
    try:
        print(f"Received lots production glouton request: {request}")
        fms_request = FMSLotsProductionGloutonRequest(**request)
        print("Lots production glouton request validation successful")
        result = solve_fms_lots_production_glouton(fms_request)
        print("Lots production glouton algorithm execution successful")
        return result
    except Exception as e:
        print(f"Error in FMS lots production glouton endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fms/lots_production_glouton/chart")
def run_fms_lots_production_glouton_chart(request: dict):
    try:
        print(f"Received lots production glouton chart request: {request}")
        fms_request = FMSLotsProductionGloutonRequest(**request)
        
        # Générer le graphique directement
        img_buffer = generate_fms_lots_production_glouton_chart(fms_request)
        
        return StreamingResponse(img_buffer, media_type="image/png")
    except Exception as e:
        print(f"Error in FMS lots production glouton chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------- FMS Lots de Production MIP -----------

@app.post("/fms/lots_production_mip")
def run_fms_lots_production_mip_analysis(request: dict):
    try:
        print(f"Received lots production MIP request: {request}")
        fms_request = FMSLotsProductionMIPRequest(**request)
        print("Lots production MIP request validation successful")
        result = solve_fms_lots_production_mip(fms_request)
        print("Lots production MIP algorithm execution successful")
        return result
    except Exception as e:
        print(f"Error in FMS lots production MIP endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fms/lots_production_mip/chart")
def run_fms_lots_production_mip_chart(request: dict):
    try:
        print(f"Received lots production MIP chart request: {request}")
        fms_request = FMSLotsProductionMIPRequest(**request)
        
        # Générer le graphique directement
        img_buffer = generate_fms_lots_production_mip_chart(fms_request)
        
        return StreamingResponse(img_buffer, media_type="image/png")
    except Exception as e:
        print(f"Error in FMS lots production MIP chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------- FMS Lots de Chargement Heuristique -----------

@app.post("/fms/lots_chargement_heuristique")
def run_fms_lots_chargement_heuristique_analysis(request: dict):
    try:
        print(f"Received lots chargement heuristique request: {request}")
        fms_request = FMSLotsChargementHeuristiqueRequest(**request)
        print("Lots chargement heuristique request validation successful")
        result = solve_fms_lots_chargement_heuristique(fms_request)
        print("Lots chargement heuristique algorithm execution successful")
        return result
    except Exception as e:
        print(f"Error in FMS lots chargement heuristique endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fms/lots_chargement_heuristique/chart")
def run_fms_lots_chargement_heuristique_chart(request: dict):
    try:
        print(f"Received lots chargement heuristique chart request: {request}")
        fms_request = FMSLotsChargementHeuristiqueRequest(**request)
        
        # Générer le graphique directement
        img_buffer = generate_fms_lots_chargement_heuristique_chart(fms_request)
        
        return StreamingResponse(img_buffer, media_type="image/png")
    except Exception as e:
        print(f"Error in FMS lots chargement heuristique chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))








