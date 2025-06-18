from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import matplotlib.pyplot as plt
import io
import base64
import os

import spt
import edd
import johnson
import johnson_modifie
import smith
import contraintes
import jobshop_spt
import jobshop_edd
import jobshop_contraintes
import excel_import
import ligne_assemblage_precedence
import ligne_assemblage_comsoal
import ligne_assemblage_lpt
import ligne_assemblage_pl
import ligne_assemblage_mixte_goulot
import ligne_assemblage_mixte_equilibrage
import ligne_transfert_buffer_buzzacott
import flowshop_machines
from validation import validate_jobs_data, validate_johnson_data, validate_johnson_modifie_data, ExtendedRequest, FlexibleFlowshopRequest, JohnsonRequest, JohnsonModifieRequest, SmithRequest, JobshopSPTRequest
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

# Servir les fichiers statiques (images Gantt)
try:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)  # Créer le dossier s'il n'existe pas
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception as e:
    print(f"Attention: Impossible de configurer les fichiers statiques: {e}")

# ----------- Gantt utilitaire -----------

def get_nice_time_intervals(max_time):
    """
    Retourne des intervalles de temps 'ronds' pour le cadrillage
    """
    # Valeurs rondes prédéfinies
    nice_values = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250, 300, 350, 400, 450, 500, 750, 1000]
    
    # Trouver la valeur qui donne environ 10-20 divisions
    target_divisions = 15  # Nombre idéal de divisions
    ideal_step = max_time / target_divisions
    
    # Trouver la valeur ronde la plus proche
    best_step = nice_values[0]
    for value in nice_values:
        if value >= ideal_step:
            best_step = value
            break
        best_step = value  # Garder la dernière valeur si aucune n'est assez grande
    
    # Si max_time est très grand, multiplier par des facteurs
    if best_step < ideal_step and max_time > 1000:
        multipliers = [2, 5, 10, 20, 50, 100]
        for mult in multipliers:
            candidate = best_step * mult
            if candidate >= ideal_step:
                best_step = candidate
                break
    
    return best_step

def create_gantt_figure(result, title: str, unite="heures", job_names=None, machine_names=None, due_dates=None):
    """
    Crée un diagramme de Gantt professionnel avec couleurs différentes par tâche et cadrillage
    """
    import matplotlib.patches as patches
    import numpy as np
    
    # Calculer la taille optimale selon le nombre de machines
    num_machines = len(result["machines"])
    fig_height = max(4, num_machines * 0.8 + 2)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    
    # Style professionnel
    ax.set_facecolor('#f8f9fa')
    fig.patch.set_facecolor('white')
    
    # Couleurs différentes pour chaque tâche
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316", 
              "#06b6d4", "#84cc16", "#f43f5e", "#8b5a2b", "#6b7280", "#ec4899", "#3b82f6", "#22c55e"]
    
    # Trier les machines par index pour un affichage cohérent
    sorted_machines = sorted(result["machines"].items(), key=lambda x: int(x[0]))
    
    # Hauteur des barres
    bar_height = 0.6
    
    # Calculer le temps maximum pour définir la grille
    max_time = 0
    for m, tasks in result["machines"].items():
        for t in tasks:
            max_time = max(max_time, t["start"] + t["duration"])
    
    # Créer un mapping des dates dues vers les couleurs des tâches
    due_date_colors = {}
    if due_dates:
        for job_idx, due_date in enumerate(due_dates):
            if due_date and due_date > 0:
                job_color = colors[job_idx % len(colors)]
                due_date_colors[due_date] = (job_color, job_idx)
    
    # Dessiner les tâches
    for m_idx, (m, tasks) in enumerate(sorted_machines):
        label = machine_names[int(m)] if machine_names and int(m) < len(machine_names) else f"Machine {int(m)}"
        
        if len(tasks) == 0:
            # Machine vide : afficher une ligne vide mais visible
            ax.barh(label, 0, left=0, color='#e9ecef', alpha=0.5, height=0.2, 
                   edgecolor='#6c757d', linewidth=0.5)
        else:
            # Machine avec tâches : afficher avec couleurs différentes par tâche
            for t in tasks:
                job_idx = t["job"] if isinstance(t["job"], int) else job_names.index(t["job"])
                job_label = job_names[job_idx] if job_names else f"J{job_idx}"
                
                # Couleur différente pour chaque tâche
                color = colors[job_idx % len(colors)]
                
                # Créer la barre avec bordure
                bar = ax.barh(label, t["duration"], left=t["start"], color=color, 
                             height=bar_height, edgecolor='white', linewidth=1.5, alpha=0.9)
                
                # Ajouter une ombre subtile
                shadow = ax.barh(label, t["duration"], left=t["start"] + 0.1, color='black', 
                               height=bar_height, alpha=0.1, zorder=0)
                
                # Texte du job avec style amélioré
                text_color = 'white'
                ax.text(t["start"] + t["duration"] / 2, label, job_label,
                       va="center", ha="center", color=text_color, fontsize=9, 
                       fontweight='bold', zorder=10)

    # Créer un cadrillage avec coloration des cases selon les dates dues
    if max_time > 0:
        # Définir les intervalles de temps pour le cadrillage avec des nombres entiers
        time_step = get_nice_time_intervals(max_time)  # Utiliser la nouvelle fonction
        time_ticks = np.arange(0, int(max_time) + time_step + 1, time_step)
        
        # Grille verticale et horizontale très foncée
        ax.set_xticks(time_ticks)
        ax.grid(True, axis='x', alpha=1.0, linestyle='-', linewidth=1.2, color='#6c757d')
        ax.grid(True, axis='y', alpha=0.8, linestyle='-', linewidth=1.0, color='#6c757d')
        ax.set_axisbelow(True)
        
        # Afficher les dates dues empilées en haut du graphique
        if due_date_colors:
            # Créer des étiquettes normales pour l'axe x
            x_labels = [str(int(tick)) for tick in time_ticks]
            ax.set_xticklabels(x_labels)
            
            # Obtenir les limites actuelles de l'axe y
            y_min, y_max = ax.get_ylim()
            
            # Grouper les dates dues par position pour les empiler
            due_dates_at_position = {}
            
            for due_date, (color, job_idx) in due_date_colors.items():
                if due_date <= max_time:
                    if due_date not in due_dates_at_position:
                        due_dates_at_position[due_date] = []
                    
                    # Trouver le nom du job correspondant
                    job_name = job_names[job_idx] if job_names and job_idx < len(job_names) else f'J{job_idx+1}'
                    due_dates_at_position[due_date].append((color, job_name))
            
            # Afficher les dates dues empilées AU-DESSUS de la Machine 0
            max_stack_height = 0
            for due_date, job_info_list in due_dates_at_position.items():
                # Ajouter une ligne verticale pour marquer la date due
                main_color = job_info_list[0][0]  # Couleur du premier job
                ax.axvline(x=due_date, color=main_color, linestyle='--', linewidth=2, alpha=0.8, zorder=5)
                
                # Empiler les dates dues verticalement AU-DESSUS de la Machine 0
                # Comme l'axe Y est inversé, y_min correspond au haut du graphique
                for i, (color, job_name) in enumerate(job_info_list):
                    # Position au-dessus de la Machine 0 (utiliser y_min car l'axe est inversé)
                    y_position = y_min - 0.3 - (i * 0.5)  # Empiler vers le haut au-dessus de Machine 0
                    
                    # Texte pour chaque job
                    text = f'{job_name}: {int(due_date)}'
                    
                    # Boîte colorée avec la couleur du job
                    bbox_props = dict(boxstyle='round,pad=0.2', facecolor=color, alpha=0.8, 
                                    edgecolor='black', linewidth=1)
                    
                    # Ajouter le texte de la date due au-dessus de Machine 0
                    ax.text(due_date, y_position, text,
                           ha='center', va='center', fontsize=8, fontweight='bold',
                           color='white', rotation=0, zorder=11,
                           bbox=bbox_props)
                
                # Mettre à jour la hauteur maximale de l'empilement
                max_stack_height = max(max_stack_height, len(job_info_list))
            
            # Ajuster les limites de l'axe y pour faire de la place aux dates dues AU-DESSUS
            if max_stack_height > 0:
                # Étendre vers le haut pour les due dates (réduire y_min car l'axe est inversé)
                ax.set_ylim(y_min - 0.5 - (max_stack_height * 0.5), y_max)
    
    # Améliorer les axes
    ax.set_xlabel(f"Temps ({unite})", fontsize=12, fontweight='bold')
    ax.set_ylabel("Machines", fontsize=12, fontweight='bold')
    ax.invert_yaxis()
    
    # Titre avec style
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    # Créer la légende pour les tâches (si on a les noms des jobs)
    if job_names and len(job_names) <= 8:  # Limiter la légende si trop de jobs
        legend_elements = []
        for i, job_name in enumerate(job_names):
            # Utiliser la même logique de couleur que pour les barres
            color = colors[i % len(colors)]
            legend_elements.append(patches.Patch(color=color, label=job_name))
        
        # Positionner la légende en haut à droite
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1), 
                 frameon=True, fancybox=True, shadow=True, fontsize=9)
    
    # Ajuster les marges
    plt.tight_layout()
    
    # Ajouter une bordure autour du graphique
    for spine in ax.spines.values():
        spine.set_edgecolor('#dee2e6')
        spine.set_linewidth(1)
    
    return fig

def create_gantt_figure_with_setup(result, title: str, unite="heures", job_names=None, machine_names=None, due_dates=None):
    """
    Fonction de Gantt spécialisée pour afficher les temps de setup en rouge pâle
    AVEC le même visuel que create_gantt_figure (due dates en haut, cadrillage rond)
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#6366f1", "#8b5cf6", "#14b8a6", "#f97316"]
    setup_color = "#ffcccb"  # Rouge pâle pour les temps de setup

    # Trier les machines par index pour un affichage cohérent
    sorted_machines = sorted(result["machines"].items(), key=lambda x: int(x[0]))
    
    # Calculer le temps maximum pour les axes
    max_time = 0
    for m_idx, (m, tasks) in enumerate(sorted_machines):
        for t in tasks:
            max_time = max(max_time, t["start"] + t["duration"])
    
    for m_idx, (m, tasks) in enumerate(sorted_machines):
        label = machine_names[int(m)] if machine_names and int(m) < len(machine_names) else f"Machine {int(m)}"
        
        if len(tasks) == 0:
            # Machine vide : afficher une ligne vide mais visible
            ax.barh(label, 0, left=0, color='lightgray', alpha=0.3, height=0.1)
        else:
            # Machine avec tâches : afficher normalement
            for t in tasks:
                if t.get("type") == "setup":
                    # Temps de setup : rouge pâle
                    ax.barh(label, t["duration"], left=t["start"], color=setup_color, alpha=0.8)
                    ax.text(t["start"] + t["duration"] / 2, label, "Setup",
                            va="center", ha="center", color="darkred", fontsize=7, weight="bold")
                else:
                    # Tâche normale : couleur selon le job
                    job_idx = t["job"] if isinstance(t["job"], int) else job_names.index(t["job"])
                    job_label = job_names[job_idx] if job_names else f"J{job_idx}"
                    color = colors[job_idx % len(colors)]
                    ax.barh(label, t["duration"], left=t["start"], color=color)
                    ax.text(t["start"] + t["duration"] / 2, label, job_label,
                            va="center", ha="center", color="white", fontsize=8)

    # Ajouter le cadrillage avec des valeurs rondes (comme create_gantt_figure)
    if max_time > 0:
        time_step = get_nice_time_intervals(max_time)
        time_ticks = list(range(0, int(max_time) + time_step, time_step))
        ax.set_xticks(time_ticks)
        ax.grid(True, axis='x', alpha=1.0, color='#6c757d', linewidth=0.8)

    # Créer un mapping des dates dues vers les couleurs des tâches
    due_date_colors = {}
    if due_dates:
        for job_idx, due_date in enumerate(due_dates):
            if due_date and due_date > 0:
                job_color = colors[job_idx % len(colors)]
                due_date_colors[due_date] = (job_color, job_idx)

    # Afficher les dates dues empilées AU-DESSUS de la première machine (comme create_gantt_figure)
    if due_date_colors:
        # Obtenir les limites actuelles de l'axe y
        y_min, y_max = ax.get_ylim()
        
        # Grouper les dates dues par position
        due_dates_at_position = {}
        for due_date, (color, job_idx) in due_date_colors.items():
            job_name = job_names[job_idx] if job_names and job_idx < len(job_names) else f'J{job_idx+1}'
            if due_date not in due_dates_at_position:
                due_dates_at_position[due_date] = []
            due_dates_at_position[due_date].append((color, job_name))
        
        # Afficher les dates dues empilées AU-DESSUS de la première machine
        max_stack_height = 0
        for due_date, job_info_list in due_dates_at_position.items():
            # Ajouter une ligne verticale pour marquer la date due
            main_color = job_info_list[0][0]  # Couleur du premier job
            ax.axvline(x=due_date, color=main_color, linestyle='--', linewidth=2, alpha=0.8, zorder=5)
            
            # Empiler les dates dues verticalement AU-DESSUS de la première machine
            # Comme l'axe Y est inversé, y_min correspond au haut du graphique
            for i, (color, job_name) in enumerate(job_info_list):
                # Position au-dessus de la première machine (utiliser y_min car l'axe est inversé)
                y_position = y_min - 0.3 - (i * 0.5)
                
                # Créer une boîte colorée avec le nom du job et la date due
                bbox_props = dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8, edgecolor='black')
                ax.text(due_date, y_position, f'{job_name}: {due_date}', 
                       ha='center', va='center', fontsize=9, color='white', weight='bold',
                       bbox=bbox_props, zorder=10)
                
                max_stack_height = max(max_stack_height, 0.3 + (i + 1) * 0.5)
        
        # Ajuster les limites de l'axe Y pour faire de la place aux due dates
        if max_stack_height > 0:
            extension = max_stack_height + 0.2
            ax.set_ylim(y_min - extension, y_max)

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
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
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
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Jobshop Contraintes -----------

@app.post("/jobshop/contraintes")
def run_jobshop_contraintes(request: JobshopSPTRequest):
    try:
        result = jobshop_contraintes.planifier_jobshop_contraintes(
            request.job_names, 
            request.machine_names, 
            request.jobs_data, 
            request.due_dates,
            request.setup_times,
            request.release_times
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/contraintes/gantt")
def run_jobshop_contraintes_gantt(request: JobshopSPTRequest):
    try:
        result = jobshop_contraintes.planifier_jobshop_contraintes(
            request.job_names, 
            request.machine_names, 
            request.jobs_data, 
            request.due_dates,
            request.setup_times,
            request.release_times
        )
        machines_dict = {}
        
        # Ajouter les tâches normales
        for t in result["schedule"]:
            m_idx = request.machine_names.index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["duration"] if "duration" in t else t["end"] - t["start"],
                "type": "task"
            })
        
        # Ajouter les temps de setup s'ils existent
        if "setup_schedule" in result and result["setup_schedule"]:
            for setup in result["setup_schedule"]:
                m_idx = request.machine_names.index(setup["machine"])
                machines_dict.setdefault(m_idx, []).append({
                    "job": f"{setup['from_job']}→{setup['to_job']}",
                    "start": setup["start"],
                    "duration": setup["duration"],
                    "type": "setup"
                })
        
        # Trier les tâches par temps de début pour chaque machine
        for m_idx in machines_dict:
            machines_dict[m_idx].sort(key=lambda x: x["start"])
        
        result_formatted = {"machines": machines_dict}
        
        # Utiliser la fonction Gantt STANDARD pour un rendu visuel identique à SPT/EDD
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop Contraintes (CP)",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Jobshop Import/Export -----------

@app.post("/jobshop/spt/import-excel")
async def import_jobshop_spt_excel(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_jobshop_excel(file_content)
        
        # Appeler l'algorithme SPT directement avec les données parsées
        result = jobshop_spt.planifier_jobshop_spt(
            parsed_data["job_names"], 
            parsed_data["machine_names"], 
            parsed_data["jobs_data"], 
            parsed_data["due_dates"]
        )
        
        # Ajouter les données parsées au résultat pour l'affichage frontend
        result.update({
            "imported_data": parsed_data
        })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/spt/import-excel-gantt")
async def import_jobshop_spt_excel_gantt(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_jobshop_excel(file_content)
        
        # Appeler l'algorithme SPT pour obtenir les résultats
        result = jobshop_spt.planifier_jobshop_spt(
            parsed_data["job_names"], 
            parsed_data["machine_names"], 
            parsed_data["jobs_data"], 
            parsed_data["due_dates"]
        )
        
        # Créer le diagramme de Gantt
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = parsed_data["machine_names"].index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["end"] - t["start"]
            })
        
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop SPT (Import Excel)",
                                  unite=parsed_data["unite"],
                                  job_names=parsed_data["job_names"],
                                  machine_names=parsed_data["machine_names"],
                                  due_dates=parsed_data["due_dates"])
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/edd/import-excel")
async def import_jobshop_edd_excel(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_jobshop_excel(file_content)
        
        # Appeler l'algorithme EDD directement avec les données parsées
        result = jobshop_edd.planifier_jobshop_edd(
            parsed_data["job_names"], 
            parsed_data["machine_names"], 
            parsed_data["jobs_data"], 
            parsed_data["due_dates"]
        )
        
        # Ajouter les données parsées au résultat pour l'affichage frontend
        result.update({
            "imported_data": parsed_data
        })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/edd/import-excel-gantt")
async def import_jobshop_edd_excel_gantt(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_jobshop_excel(file_content)
        
        # Appeler l'algorithme EDD pour obtenir les résultats
        result = jobshop_edd.planifier_jobshop_edd(
            parsed_data["job_names"], 
            parsed_data["machine_names"], 
            parsed_data["jobs_data"], 
            parsed_data["due_dates"]
        )
        
        # Créer le diagramme de Gantt
        machines_dict = {}
        for t in result["schedule"]:
            m_idx = parsed_data["machine_names"].index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["end"] - t["start"]
            })
        
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop EDD (Import Excel)",
                                  unite=parsed_data["unite"],
                                  job_names=parsed_data["job_names"],
                                  machine_names=parsed_data["machine_names"],
                                  due_dates=parsed_data["due_dates"])
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/contraintes/import-excel")
async def import_jobshop_contraintes_excel(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_jobshop_excel(file_content)
        
        # Appeler l'algorithme Contraintes directement avec les données parsées
        result = jobshop_contraintes.planifier_jobshop_contraintes(
            parsed_data["job_names"], 
            parsed_data["machine_names"], 
            parsed_data["jobs_data"], 
            parsed_data["due_dates"],
            setup_times=None,  # Valeurs par défaut
            release_times=None
        )
        
        # Ajouter les données parsées au résultat pour l'affichage frontend
        result.update({
            "imported_data": parsed_data
        })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/contraintes/import-excel-gantt")
async def import_jobshop_contraintes_excel_gantt(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_jobshop_excel(file_content)
        
        # Appeler l'algorithme Contraintes pour obtenir les résultats
        result = jobshop_contraintes.planifier_jobshop_contraintes(
            parsed_data["job_names"], 
            parsed_data["machine_names"], 
            parsed_data["jobs_data"], 
            parsed_data["due_dates"],
            setup_times=None,  # Valeurs par défaut
            release_times=None
        )
        
        # Créer le diagramme de Gantt avec setups mais rendu visuel standard
        machines_dict = {}
        
        # Ajouter les tâches normales
        for t in result["schedule"]:
            m_idx = parsed_data["machine_names"].index(t["machine"])
            machines_dict.setdefault(m_idx, []).append({
                "job": t["job"],
                "start": t["start"],
                "duration": t["duration"] if "duration" in t else t["end"] - t["start"],
                "type": "task"
            })
        
        # Ajouter les temps de setup s'ils existent
        if "setup_schedule" in result and result["setup_schedule"]:
            for setup in result["setup_schedule"]:
                m_idx = parsed_data["machine_names"].index(setup["machine"])
                machines_dict.setdefault(m_idx, []).append({
                    "job": f"{setup['from_job']}→{setup['to_job']}",
                    "start": setup["start"],
                    "duration": setup["duration"],
                    "type": "setup"
                })
        
        # Trier les tâches par temps de début pour chaque machine
        for m_idx in machines_dict:
            machines_dict[m_idx].sort(key=lambda x: x["start"])
        
        result_formatted = {"machines": machines_dict}
        fig = create_gantt_figure(result_formatted, "Diagramme de Gantt - Jobshop Contraintes (Import Excel)",
                                  unite=parsed_data["unite"],
                                  job_names=parsed_data["job_names"],
                                  machine_names=parsed_data["machine_names"],
                                  due_dates=parsed_data["due_dates"])
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Modèle pour l'export Jobshop
class JobshopExportDataRequest(BaseModel):
    jobs_data: List[List[List[float]]]  # Format Jobshop: [machine, duration] par job
    due_dates: List[float]
    job_names: List[str]
    machine_names: List[str]
    unite: str = "heures"

@app.post("/jobshop/spt/export-excel")
def export_jobshop_spt_data_to_excel(request: JobshopExportDataRequest):
    try:
        # Convertir les données au format avec séquence pour l'export
        formatted_jobs_data = []
        for job_tasks in request.jobs_data:
            job_formatted = []
            for sequence, (machine, duration) in enumerate(job_tasks, 1):
                job_formatted.append({
                    'sequence': sequence,
                    'machine': int(machine),
                    'duration': float(duration)
                })
            formatted_jobs_data.append(job_formatted)
        
        excel_content = excel_import.export_jobshop_data_to_excel(
            formatted_jobs_data,
            request.due_dates,
            request.job_names,
            request.machine_names,
            request.unite
        )
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=jobshop_spt_export.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/edd/export-excel")
def export_jobshop_edd_data_to_excel(request: JobshopExportDataRequest):
    try:
        # Convertir les données au format avec séquence pour l'export
        formatted_jobs_data = []
        for job_tasks in request.jobs_data:
            job_formatted = []
            for sequence, (machine, duration) in enumerate(job_tasks, 1):
                job_formatted.append({
                    'sequence': sequence,
                    'machine': int(machine),
                    'duration': float(duration)
                })
            formatted_jobs_data.append(job_formatted)
        
        excel_content = excel_import.export_jobshop_data_to_excel(
            formatted_jobs_data,
            request.due_dates,
            request.job_names,
            request.machine_names,
            request.unite
        )
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=jobshop_edd_export.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/jobshop/contraintes/export-excel")
def export_jobshop_contraintes_data_to_excel(request: JobshopExportDataRequest):
    try:
        # Convertir les données au format avec séquence pour l'export
        formatted_jobs_data = []
        for job_tasks in request.jobs_data:
            job_formatted = []
            for sequence, (machine, duration) in enumerate(job_tasks, 1):
                job_formatted.append({
                    'sequence': sequence,
                    'machine': int(machine),
                    'duration': float(duration)
                })
            formatted_jobs_data.append(job_formatted)
        
        excel_content = excel_import.export_jobshop_data_to_excel(
            formatted_jobs_data,
            request.due_dates,
            request.job_names,
            request.machine_names,
            request.unite
        )
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=jobshop_contraintes_export.xlsx"}
        )
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
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
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
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Johnson -----------

@app.post("/johnson")
def run_johnson(request: JohnsonRequest):
    try:
        validate_johnson_data(request.jobs_data, request.due_dates, request.job_names)
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
        validate_johnson_data(request.jobs_data, request.due_dates, request.job_names)
        result = johnson.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Johnson",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Johnson Modifié -----------

@app.post("/johnson_modifie")
def run_johnson_modifie(request: JohnsonModifieRequest):
    try:
        validate_johnson_modifie_data(request.jobs_data, request.due_dates, request.job_names)
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
        validate_johnson_modifie_data(request.jobs_data, request.due_dates, request.job_names)
        result = johnson_modifie.schedule(request.jobs_data, request.due_dates)
        fig = create_gantt_figure(result, "Diagramme de Gantt - Johnson modifié",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
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
        return {
            "sequence": result["sequence"],
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {"Machine 0": result["machines"]["0"]},
            "N": result.get("N", 0),
            "cumulative_delay": result["cumulative_delay"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/smith/gantt")
def run_smith_gantt(request: SmithRequest):
    try:
        result = smith.smith_algorithm(request.jobs)
        
        # Extraire les due dates des jobs (format: [[durée, due_date], ...])
        due_dates = [job[1] for job in request.jobs]
        
        # Utiliser create_gantt_figure comme tous les autres algorithmes
        fig = create_gantt_figure(result, "Diagramme de Gantt - Smith",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=["Machine 1"],  # Smith utilise une seule machine
                                  due_dates=due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Contraintes -----------

@app.post("/contraintes")
def run_contraintes(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        
        # Mode flowshop classique uniquement (une machine par étape)
        result = contraintes.flowshop_contraintes(
            request.jobs_data, 
            request.due_dates,
            request.job_names, 
            request.machine_names,
            None  # machines_per_stage = None pour flowshop classique
        )
        
        # Ajuster les noms pour les machines
        machine_names_to_use = request.machine_names or [f"Machine {i+1}" for i in range(len(request.jobs_data[0]))]
        return {
            "makespan": result["makespan"],
            "flowtime": result["flowtime"],
            "retard_cumule": result["retard_cumule"],
            "completion_times": result["completion_times"],
            "planification": {machine_names_to_use[int(m)]: tasks for m, tasks in result["machines"].items() if str(m).isdigit() and int(m) < len(machine_names_to_use)},
            "raw_machines": result["machines"],
            "gantt_url": result.get("gantt_url")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes/gantt")
def run_contraintes_gantt(request: ExtendedRequest):
    try:
        validate_jobs_data(request.jobs_data, request.due_dates)
        
        # Mode flowshop classique uniquement (une machine par étape)
        result = contraintes.flowshop_contraintes(
            request.jobs_data, 
            request.due_dates,
            request.job_names, 
            request.machine_names,
            None  # machines_per_stage = None pour flowshop classique
        )
        
        fig = create_gantt_figure(result, "Diagramme de Gantt - Contraintes (CP)",
                                  unite=request.unite,
                                  job_names=request.job_names,
                                  machine_names=request.machine_names,
                                  due_dates=request.due_dates)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
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

# ----------- Flowshop Machines Multiples -----------

@app.post("/flowshop/machines_multiples")
def run_flowshop_machines_multiples(request: FlexibleFlowshopRequest):
    try:
        result = flowshop_machines.solve_flexible_flowshop(
            request.jobs_data, 
            request.due_dates,
            machine_names=request.machine_names,
            stage_names=request.stage_names,
            machines_per_stage=request.machines_per_stage,
            machine_priorities=request.machine_priorities
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/flowshop/machines_multiples/gantt")
def run_flowshop_machines_multiples_gantt(request: FlexibleFlowshopRequest):
    try:
        # Utiliser la fonction de création de Gantt intégrée avec le visuel standardisé
        fig = flowshop_machines.create_gantt_chart(
            request.jobs_data, 
            request.due_dates,
            machine_names=request.machine_names,
            stage_names=request.stage_names,
            machines_per_stage=request.machines_per_stage,
            machine_priorities=request.machine_priorities
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/flowshop/machines_multiples/agenda")
def run_flowshop_machines_multiples_agenda(request: FlexibleFlowshopRequest):
    try:
        result = flowshop_machines.solve_flexible_flowshop(
            request.jobs_data, 
            request.due_dates,
            machine_names=request.machine_names,
            stage_names=request.stage_names,
            machines_per_stage=request.machines_per_stage,
            machine_priorities=request.machine_priorities
        )
        
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

# ----------- FlowshopMM Import/Export -----------

@app.post("/flowshop/machines_multiples/import-excel")
async def import_flowshop_mm_excel(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_mm_excel(file_content)
        
        # Appeler l'algorithme FlowshopMM directement avec les données parsées
        result = flowshop_machines.solve_flexible_flowshop(
            parsed_data["jobs_data"], 
            parsed_data["due_dates"],
            machine_names=parsed_data["stage_names"],
            stage_names=parsed_data["stage_names"],
            machines_per_stage=parsed_data["machines_per_stage"],
            machine_priorities=parsed_data["machine_priorities"]
        )
        
        # Ajouter les données parsées au résultat pour l'affichage frontend
        result.update({
            "imported_data": parsed_data
        })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/flowshop/machines_multiples/import-excel-gantt")
async def import_flowshop_mm_excel_gantt(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_mm_excel(file_content)
        
        # Appeler l'algorithme FlowshopMM pour obtenir les résultats
        result = flowshop_machines.solve_flexible_flowshop(
            parsed_data["jobs_data"], 
            parsed_data["due_dates"],
            machine_names=parsed_data["stage_names"],
            stage_names=parsed_data["stage_names"],
            machines_per_stage=parsed_data["machines_per_stage"],
            machine_priorities=parsed_data["machine_priorities"]
        )
        
        # Créer le diagramme de Gantt
        fig = create_gantt_figure(result, "Diagramme de Gantt - FlowshopMM (Import Excel)",
                                  unite=parsed_data["unite"],
                                  job_names=parsed_data["job_names"],
                                  machine_names=parsed_data["stage_names"],
                                  due_dates=parsed_data["due_dates"])
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
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
        
        # Convertir les données de tâches en tuples et extraire les noms
        task_tuples = []
        task_names = {}
        for task in tasks_data:
            task_id = task.get("id")
            task_name = task.get("name", f"Tâche {task_id}")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            task_names[task_id] = task_name
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_comsoal.comsoal_algorithm(task_tuples, cycle_time, unite, seed, task_names)
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
        
        # Convertir les données de tâches en tuples et extraire les noms
        task_tuples = []
        task_names = {}
        for task in tasks_data:
            task_id = task.get("id")
            task_name = task.get("name", f"Tâche {task_id}")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            task_names[task_id] = task_name
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_comsoal.comsoal_algorithm(task_tuples, cycle_time, unite, seed, task_names)
        
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
        
        # Convertir les données de tâches en tuples et extraire les noms
        task_tuples = []
        task_names = {}
        for task in tasks_data:
            task_id = task.get("id")
            task_name = task.get("name", f"Tâche {task_id}")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            task_names[task_id] = task_name
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_lpt.lpt_algorithm(task_tuples, cycle_time, unite, task_names)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/lpt/chart")
def run_lpt_chart(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples et extraire les noms
        task_tuples = []
        task_names = {}
        for task in tasks_data:
            task_id = task.get("id")
            task_name = task.get("name", f"Tâche {task_id}")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            task_names[task_id] = task_name
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_lpt.lpt_algorithm(task_tuples, cycle_time, unite, task_names)
        
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
        
        # Convertir les données de tâches en tuples et extraire les noms
        task_tuples = []
        task_names = {}
        for task in tasks_data:
            task_id = task.get("id")
            task_name = task.get("name", f"Tâche {task_id}")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            task_names[task_id] = task_name
            
            # Convertir predecessors None en None, sinon garder la valeur
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_pl.pl_algorithm(task_tuples, cycle_time, unite, task_names)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage/pl/chart")
def run_pl_chart(request: dict):
    try:
        tasks_data = request.get("tasks_data", [])
        cycle_time = request.get("cycle_time", 70)
        unite = request.get("unite", "minutes")
        
        # Convertir les données de tâches en tuples et extraire les noms
        task_tuples = []
        task_names = {}
        for task in tasks_data:
            task_id = task.get("id")
            task_name = task.get("name", f"Tâche {task_id}")
            predecessors = task.get("predecessors")
            duration = task.get("duration")
            
            task_names[task_id] = task_name
            
            if predecessors is None or predecessors == [] or predecessors == "":
                predecessors = None
            elif isinstance(predecessors, list) and len(predecessors) == 1:
                predecessors = predecessors[0]
            
            task_tuples.append((task_id, predecessors, duration))
        
        result = ligne_assemblage_pl.pl_algorithm(task_tuples, cycle_time, unite, task_names)
        
        # Décoder l'image base64 et la retourner comme réponse image
        image_data = base64.b64decode(result["graphique"])
        buf = io.BytesIO(image_data)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== IMPORT/EXPORT EXCEL POUR LIGNE D'ASSEMBLAGE =====

class LigneAssemblageExportDataRequest(BaseModel):
    tasks_data: List[dict]  # Format: [{"task_id": 1, "name": "Tâche 1", "duration": 20, "predecessors": None}]
    cycle_time: float
    unite: str = "minutes"
    format_type: str = "ligne_assemblage"

@app.post("/ligne_assemblage/pl/export-excel")
def export_ligne_assemblage_pl_data_to_excel(request: LigneAssemblageExportDataRequest):
    try:
        # Utiliser la fonction d'export spécialisée pour ligne d'assemblage
        return excel_import.export_ligne_assemblage_to_excel(
            request.tasks_data,
            request.cycle_time,
            request.unite,
            "PL"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")

@app.post("/ligne_assemblage/lpt/export-excel")
def export_ligne_assemblage_lpt_data_to_excel(request: LigneAssemblageExportDataRequest):
    try:
        return excel_import.export_ligne_assemblage_to_excel(
            request.tasks_data,
            request.cycle_time,
            request.unite,
            "LPT"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")

@app.post("/ligne_assemblage/comsoal/export-excel")
def export_ligne_assemblage_comsoal_data_to_excel(request: LigneAssemblageExportDataRequest):
    try:
        return excel_import.export_ligne_assemblage_to_excel(
            request.tasks_data,
            request.cycle_time,
            request.unite,
            "COMSOAL"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")

@app.post("/ligne_assemblage/pl/import-excel")
async def import_ligne_assemblage_pl_excel(file: UploadFile = File(...), format_type: str = "ligne_assemblage"):
    try:
        # Lire le fichier Excel et parser selon le format ligne d'assemblage
        result = await excel_import.parse_ligne_assemblage_excel(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'import: {str(e)}")

@app.post("/ligne_assemblage/lpt/import-excel")
async def import_ligne_assemblage_lpt_excel(file: UploadFile = File(...), format_type: str = "ligne_assemblage"):
    try:
        result = await excel_import.parse_ligne_assemblage_excel(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'import: {str(e)}")

@app.post("/ligne_assemblage/comsoal/import-excel")
async def import_ligne_assemblage_comsoal_excel(file: UploadFile = File(...), format_type: str = "ligne_assemblage"):
    try:
        result = await excel_import.parse_ligne_assemblage_excel(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'import: {str(e)}")

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

# ----------- Import Excel -----------

@app.post("/flowshop/import-excel")
async def import_flowshop_excel(file: UploadFile = File(...)):
    """Import de données flowshop depuis un fichier Excel"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire le contenu du fichier
        file_content = await file.read()
        
        # Parser le fichier Excel
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        return {
            "success": True,
            "message": f"Fichier '{file.filename}' importé avec succès",
            "data": parsed_data
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")

@app.get("/flowshop/template/{template_type}")
async def download_flowshop_template(template_type: str):
    """Téléchargement des templates Excel pour flowshop"""
    try:
        if template_type not in ["exemple", "vide"]:
            raise HTTPException(status_code=400, detail="Type de template invalide. Utilisez 'exemple' ou 'vide'")
        
        # Générer le template
        template_content = excel_import.create_flowshop_template(template_type)
        
        # Nom du fichier
        filename = f"Template_Flowshop_{template_type.capitalize()}.xlsx"
        
        # Créer la réponse
        response = StreamingResponse(
            io.BytesIO(template_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du template: {str(e)}")

@app.post("/spt/import-excel")
async def import_spt_excel(file: UploadFile = File(...)):
    """Import de données SPT depuis un fichier Excel et exécution de l'algorithme"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Valider les données
        validate_jobs_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme SPT
        result = spt.schedule(parsed_data["jobs_data"], parsed_data["due_dates"])
        
        return {
            "success": True,
            "message": f"Fichier '{file.filename}' importé et traité avec succès",
            "imported_data": {
                "job_names": parsed_data["job_names"],
                "machine_names": parsed_data["machine_names"],
                "jobs_data": parsed_data["jobs_data"],
                "due_dates": parsed_data["due_dates"],
                "unite": parsed_data["unite"],
                "jobs_count": len(parsed_data["jobs_data"]),
                "machines_count": len(parsed_data["machine_names"])
            },
            "results": {
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {parsed_data["machine_names"][int(m)]: tasks for m, tasks in result["machines"].items()}
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et du traitement: {str(e)}")

@app.post("/spt/import-excel-gantt")
async def import_spt_excel_gantt(file: UploadFile = File(...)):
    """Import de données SPT depuis un fichier Excel et génération du diagramme de Gantt"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Valider les données
        validate_jobs_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme SPT
        result = spt.schedule(parsed_data["jobs_data"], parsed_data["due_dates"])
        
        # Générer le diagramme de Gantt
        fig = create_gantt_figure(
            result, 
            "Diagramme de Gantt - SPT (Import Excel)",
            unite=parsed_data["unite"],
            job_names=parsed_data["job_names"],
            machine_names=parsed_data["machine_names"],
            due_dates=parsed_data["due_dates"]
        )
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        
        return StreamingResponse(buf, media_type="image/png")
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et de la génération du Gantt: {str(e)}")

@app.post("/edd/import-excel")
async def import_edd_excel(file: UploadFile = File(...)):
    """Import de données EDD depuis un fichier Excel et exécution de l'algorithme"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Valider les données
        validate_jobs_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme EDD
        result = edd.schedule(parsed_data["jobs_data"], parsed_data["due_dates"])
        
        return {
            "success": True,
            "message": f"Fichier '{file.filename}' importé et traité avec succès",
            "imported_data": {
                "job_names": parsed_data["job_names"],
                "machine_names": parsed_data["machine_names"],
                "jobs_data": parsed_data["jobs_data"],
                "due_dates": parsed_data["due_dates"],
                "unite": parsed_data["unite"],
                "jobs_count": len(parsed_data["jobs_data"]),
                "machines_count": len(parsed_data["machine_names"])
            },
            "results": {
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {parsed_data["machine_names"][int(m)] if int(m) < len(parsed_data["machine_names"]) else f"Machine {int(m)}": tasks for m, tasks in result["machines"].items()}
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et du traitement: {str(e)}")

@app.post("/edd/import-excel-gantt")
async def import_edd_excel_gantt(file: UploadFile = File(...)):
    try:
        # Lire le fichier Excel
        contents = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(contents)
        
        # Valider les données
        validate_jobs_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme EDD
        result = edd.schedule(parsed_data["jobs_data"], parsed_data["due_dates"])
        
        # Créer le graphique Gantt avec due_dates
        fig = create_gantt_figure(result, "Diagramme de Gantt - Flowshop EDD",
                                  unite=parsed_data["unite"],
                                  job_names=parsed_data["job_names"],
                                  machine_names=parsed_data["machine_names"],
                                  due_dates=parsed_data["due_dates"])
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------- Import Excel pour Johnson -----------

@app.post("/johnson/import-excel")
async def import_johnson_excel(file: UploadFile = File(...)):
    """Import de données Johnson depuis un fichier Excel et exécution de l'algorithme"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Convertir au format Johnson (List[List[float]] au lieu de List[List[List[float]]])
        johnson_jobs_data = []
        for job in parsed_data["jobs_data"]:
            job_durations = [task[1] for task in job]  # Extraire seulement les durées
            johnson_jobs_data.append(job_durations)
        
        # Valider les données spécifiquement pour Johnson
        validate_johnson_data(johnson_jobs_data, parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme Johnson
        result = johnson.schedule(johnson_jobs_data, parsed_data["due_dates"])
        
        return {
            "success": True,
            "message": f"Fichier '{file.filename}' importé et traité avec succès",
            "imported_data": {
                "job_names": parsed_data["job_names"],
                "machine_names": parsed_data["machine_names"][:2],  # Johnson = 2 machines
                "jobs_data": johnson_jobs_data,
                "due_dates": parsed_data["due_dates"],
                "unite": parsed_data["unite"],
                "jobs_count": len(johnson_jobs_data),
                "machines_count": 2
            },
            "results": {
                "sequence": result["sequence"],
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {parsed_data["machine_names"][int(m)]: tasks for m, tasks in result["machines"].items()}
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et du traitement: {str(e)}")

# ----------- Import Excel pour Johnson Modifié -----------

@app.post("/johnson_modifie/import-excel")
async def import_johnson_modifie_excel(file: UploadFile = File(...)):
    """Import de données Johnson Modifié depuis un fichier Excel et exécution de l'algorithme"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Valider les données spécifiquement pour Johnson Modifié
        validate_johnson_modifie_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme Johnson Modifié
        result = johnson_modifie.schedule(parsed_data["jobs_data"], parsed_data["due_dates"])
        
        return {
            "success": True,
            "message": f"Fichier '{file.filename}' importé et traité avec succès",
            "imported_data": {
                "job_names": parsed_data["job_names"],
                "machine_names": parsed_data["machine_names"],
                "jobs_data": parsed_data["jobs_data"],
                "due_dates": parsed_data["due_dates"],
                "unite": parsed_data["unite"],
                "jobs_count": len(parsed_data["jobs_data"]),
                "machines_count": len(parsed_data["machine_names"])
            },
            "results": {
                "sequence": result["sequence"],
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {parsed_data["machine_names"][int(m)]: tasks for m, tasks in result["machines"].items()}
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et du traitement: {str(e)}")

# ----------- Import Excel pour Smith -----------

@app.post("/smith/import-excel")
async def import_smith_excel(file: UploadFile = File(...)):
    """Import de données Smith depuis un fichier Excel et exécution de l'algorithme"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Convertir au format Smith (List[List[float]] avec [durée, due_date] par job)
        # Smith utilise seulement la première machine, on ignore les autres
        smith_jobs_data = []
        for job_index, job in enumerate(parsed_data["jobs_data"]):
            if len(job) > 0:
                # Prendre seulement la première durée (première machine)
                first_duration = job[0][1]  # [machine_id, duration] -> duration
                due_date = parsed_data["due_dates"][job_index]
                smith_jobs_data.append([first_duration, due_date])
            else:
                job_name = parsed_data["job_names"][job_index] if job_index < len(parsed_data["job_names"]) else f"Job {job_index}"
                raise ValueError(f"Le job '{job_name}' ne contient aucune durée.")
        
        # Pas besoin de validation spéciale pour Smith car l'algorithme fait sa propre validation
        
        # Exécuter l'algorithme Smith
        result = smith.smith_algorithm(smith_jobs_data)
        
        # Message informatif si plusieurs machines détectées
        machines_detected = len(parsed_data["machine_names"])
        info_message = f"Fichier '{file.filename}' importé et traité avec succès"
        if machines_detected > 1:
            info_message += f" (Smith utilise seulement la première machine '{parsed_data['machine_names'][0]}', les {machines_detected-1} autres machines sont ignorées)"
        
        return {
            "success": True,
            "message": info_message,
            "imported_data": {
                "job_names": parsed_data["job_names"],
                "machine_names": [parsed_data["machine_names"][0]] if parsed_data["machine_names"] else ["Machine_1"],
                "jobs_data": smith_jobs_data,
                "due_dates": parsed_data["due_dates"],
                "unite": parsed_data["unite"],
                "jobs_count": len(smith_jobs_data),
                "machines_count": 1
            },
            "results": {
                "sequence": result["sequence"],
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {"Machine_1": result["machines"]["0"]} if parsed_data["machine_names"] else {"Machine 0": result["machines"]["0"]},
                "N": result.get("N", 0),
                "cumulative_delay": result["cumulative_delay"]
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et du traitement: {str(e)}")

@app.post("/smith/import-excel-gantt")
async def import_smith_excel_gantt(file: UploadFile = File(...)):
    """Import de données Smith depuis un fichier Excel et génération du diagramme de Gantt"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Convertir au format Smith (List[List[float]] avec [durée, due_date] par job)
        # Smith utilise seulement la première machine, on ignore les autres
        smith_jobs_data = []
        for job_index, job in enumerate(parsed_data["jobs_data"]):
            if len(job) > 0:
                # Prendre seulement la première durée (première machine)
                first_duration = job[0][1]  # [machine_id, duration] -> duration
                due_date = parsed_data["due_dates"][job_index]
                smith_jobs_data.append([first_duration, due_date])
            else:
                job_name = parsed_data["job_names"][job_index] if job_index < len(parsed_data["job_names"]) else f"Job {job_index}"
                raise ValueError(f"Le job '{job_name}' ne contient aucune durée.")
        
        # Exécuter l'algorithme Smith
        result = smith.smith_algorithm(smith_jobs_data)
        
        # Extraire les due dates des jobs Smith
        due_dates = [job[1] for job in smith_jobs_data]
        
        # Générer le diagramme de Gantt avec create_gantt_figure
        machines_detected = len(parsed_data["machine_names"])
        title = "Diagramme de Gantt - Smith (Import Excel)"
        if machines_detected > 1:
            title += f" - Utilise seulement '{parsed_data['machine_names'][0]}'"
        
        fig = create_gantt_figure(
            result, 
            title,
            unite=parsed_data["unite"],
            job_names=parsed_data["job_names"],
            machine_names=["Machine 1"],  # Smith utilise une seule machine
            due_dates=due_dates
        )
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        
        return StreamingResponse(buf, media_type="image/png")
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et de la génération du Gantt: {str(e)}")

# ----------- Import Excel pour Contraintes -----------

@app.post("/contraintes/import-excel")
async def import_contraintes_excel(file: UploadFile = File(...)):
    """Import de données Contraintes depuis un fichier Excel et exécution de l'algorithme"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Valider les données
        validate_jobs_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme Contraintes
        result = contraintes.flowshop_contraintes(
            parsed_data["jobs_data"], 
            parsed_data["due_dates"],
            parsed_data["job_names"], 
            parsed_data["machine_names"],
            None  # machines_per_stage
        )
        
        # Ajuster les noms pour les machines
        machine_names_to_use = parsed_data["machine_names"] or [f"Machine {i+1}" for i in range(len(parsed_data["jobs_data"][0]))]
        
        return {
            "success": True,
            "message": f"Fichier '{file.filename}' importé et traité avec succès",
            "imported_data": {
                "job_names": parsed_data["job_names"],
                "machine_names": parsed_data["machine_names"],
                "jobs_data": parsed_data["jobs_data"],
                "due_dates": parsed_data["due_dates"],
                "unite": parsed_data["unite"],
                "jobs_count": len(parsed_data["jobs_data"]),
                "machines_count": len(parsed_data["machine_names"])
            },
            "results": {
                "makespan": result["makespan"],
                "flowtime": result["flowtime"],
                "retard_cumule": result["retard_cumule"],
                "completion_times": result["completion_times"],
                "planification": {machine_names_to_use[int(m)]: tasks for m, tasks in result["machines"].items() if str(m).isdigit() and int(m) < len(machine_names_to_use)},
                "raw_machines": result["machines"],
                "gantt_url": result.get("gantt_url")
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import et du traitement: {str(e)}")

@app.post("/contraintes/import-excel-gantt")
async def import_contraintes_excel_gantt(file: UploadFile = File(...)):
    """Import de données Contraintes depuis un fichier Excel et génération du diagramme de Gantt"""
    try:
        # Vérifier le type de fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être au format Excel (.xlsx ou .xls)")
        
        # Lire et parser le fichier
        file_content = await file.read()
        parsed_data = excel_import.parse_flowshop_excel(file_content)
        
        # Valider les données
        validate_jobs_data(parsed_data["jobs_data"], parsed_data["due_dates"], parsed_data["job_names"])
        
        # Exécuter l'algorithme Contraintes
        result = contraintes.flowshop_contraintes(
            parsed_data["jobs_data"], 
            parsed_data["due_dates"],
            parsed_data["job_names"], 
            parsed_data["machine_names"],
            None  # machines_per_stage
        )
        
        # Générer le diagramme de Gantt
        fig = create_gantt_figure(
            result, 
            "Diagramme de Gantt - Contraintes (Import Excel)",
            unite=parsed_data["unite"],
            job_names=parsed_data["job_names"],
            machine_names=parsed_data["machine_names"],
            due_dates=parsed_data["due_dates"]
        )
        
        # Convertir en image
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close(fig)
        
        return StreamingResponse(
            img_buffer,
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=gantt_contraintes_import.png"}
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du diagramme: {str(e)}")

# Modèle pour l'export des données manuelles
class ExportDataRequest(BaseModel):
    jobs_data: List[List[float]]
    due_dates: List[float]
    job_names: List[str]
    machine_names: List[str]
    unite: str = "heures"

class FlowshopMMExportDataRequest(BaseModel):
    jobs_data: List[List[List[List[float]]]]  # Job -> Stage -> Alternatives -> [machine_id, duration]
    due_dates: List[float]
    job_names: List[str]
    stage_names: List[str]
    machines_per_stage: List[int]
    unite: str = "heures"

@app.post("/spt/export-excel")
def export_spt_data_to_excel(request: ExportDataRequest):
    """Export des données SPT saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_manual_data_to_excel(
            jobs_data=request.jobs_data,
            due_dates=request.due_dates,
            job_names=request.job_names,
            machine_names=request.machine_names,
            unite=request.unite
        )
        
        buf = io.BytesIO(excel_content)
        filename = f"Export_SPT_Donnees_Manuelles.xlsx"
        
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/edd/export-excel")
def export_edd_data_to_excel(request: ExportDataRequest):
    """Export des données EDD saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_manual_data_to_excel(
            jobs_data=request.jobs_data,
            due_dates=request.due_dates,
            job_names=request.job_names,
            machine_names=request.machine_names,
            unite=request.unite
        )
        
        buf = io.BytesIO(excel_content)
        filename = f"Export_EDD_Donnees_Manuelles.xlsx"
        
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson/export-excel")
def export_johnson_data_to_excel(request: ExportDataRequest):
    """Export des données Johnson saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_manual_data_to_excel(
            jobs_data=request.jobs_data,
            due_dates=request.due_dates,
            job_names=request.job_names,
            machine_names=request.machine_names,
            unite=request.unite
        )
        
        buf = io.BytesIO(excel_content)
        filename = f"Export_Johnson_Donnees_Manuelles.xlsx"
        
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/johnson_modifie/export-excel")
def export_johnson_modifie_data_to_excel(request: ExportDataRequest):
    """Export des données Johnson Modifié saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_manual_data_to_excel(
            jobs_data=request.jobs_data,
            due_dates=request.due_dates,
            job_names=request.job_names,
            machine_names=request.machine_names,
            unite=request.unite
        )
        
        buf = io.BytesIO(excel_content)
        filename = f"Export_Johnson_Modifie_Donnees_Manuelles.xlsx"
        
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/contraintes/export-excel")
def export_contraintes_data_to_excel(request: ExportDataRequest):
    """Export des données Contraintes saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_manual_data_to_excel(
            jobs_data=request.jobs_data,
            due_dates=request.due_dates,
            job_names=request.job_names,
            machine_names=request.machine_names,
            unite=request.unite
        )
        
        buf = io.BytesIO(excel_content)
        filename = f"Export_Contraintes_Donnees_Manuelles.xlsx"
        
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/smith/export-excel")
def export_smith_data_to_excel(request: ExportDataRequest):
    """Export des données Smith saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_manual_data_to_excel(
            jobs_data=request.jobs_data,
            due_dates=request.due_dates,
            job_names=request.job_names,
            machine_names=request.machine_names,
            unite=request.unite
        )
        
        buf = io.BytesIO(excel_content)
        filename = f"Export_Smith_Donnees_Manuelles.xlsx"
        
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/flowshop/machines_multiples/export-excel")
def export_flowshop_mm_data_to_excel(request: FlowshopMMExportDataRequest):
    """Export des données FlowshopMM saisies manuellement vers Excel"""
    try:
        excel_content = excel_import.export_flowshop_mm_data_to_excel(
            request.jobs_data,
            request.due_dates,
            request.job_names,
            request.stage_names,
            request.machines_per_stage,
            request.unite
        )
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=flowshop_mm_export.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ===== IMPORT/EXPORT EXCEL POUR PRÉCÉDENCES =====

class PrecedenceExportDataRequest(BaseModel):
    tasks_data: List[dict]  # Format: [{"task_id": 1, "name": "Tâche 1", "duration": 20, "predecessors": None}]
    unite: str = "minutes"
    format_type: str = "precedence"

class LigneAssemblageMixteEquilibrageExportDataRequest(BaseModel):
    products_data: List[dict]  # Format: [{"product_id": 1, "name": "Produit 1", "demand": 4}]
    tasks_data: List[dict]     # Format: [{"task_id": 1, "name": "Tâche 1", "times": [3, 4], "predecessors": [null, "1"]}]
    cycle_time: float
    unite: str = "minutes"
    format_type: str = "ligne_assemblage_mixte_equilibrage"

class LigneAssemblageMixteGoulotExportDataRequest(BaseModel):
    products_data: List[dict]  # Format: [{"product_id": 1, "name": "Produit 1", "demand": 4}]
    tasks_data: List[dict]     # Format: [{"task_id": 1, "name": "Tâche 1", "times": [3, 4]}]
    s1: float
    s2: float
    unite: str = "minutes"
    format_type: str = "ligne_assemblage_mixte_goulot"

@app.post("/ligne_assemblage/precedence/export-excel")
def export_precedence_data_to_excel(request: PrecedenceExportDataRequest):
    try:
        # Utiliser la fonction d'export spécialisée pour précédences (sans cycle_time)
        return excel_import.export_precedence_to_excel(
            request.tasks_data,
            request.unite,
            "Précédences"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")

@app.post("/ligne_assemblage/precedence/import-excel")
async def import_precedence_excel(file: UploadFile = File(...), format_type: str = "precedence"):
    try:
        # Lire le fichier Excel et parser selon le format précédences
        result = await excel_import.parse_precedence_excel(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'import: {str(e)}")

@app.post("/ligne_assemblage_mixte/equilibrage/export-excel")
def export_ligne_assemblage_mixte_equilibrage_data_to_excel(request: LigneAssemblageMixteEquilibrageExportDataRequest):
    try:
        buffer = excel_import.export_ligne_assemblage_mixte_equilibrage_to_excel(
            request.products_data, 
            request.tasks_data, 
            request.cycle_time, 
            request.unite
        )
        return StreamingResponse(
            io.BytesIO(buffer), 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=Export_Equilibrage_Mixte_Donnees_Manuelles.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage_mixte/equilibrage/import-excel")
async def import_ligne_assemblage_mixte_equilibrage_excel(file: UploadFile = File(...), format_type: str = "ligne_assemblage_mixte_equilibrage"):
    try:
        data = await excel_import.parse_ligne_assemblage_mixte_equilibrage_excel(file)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage_mixte/goulot/export-excel")
def export_ligne_assemblage_mixte_goulot_data_to_excel(request: LigneAssemblageMixteGoulotExportDataRequest):
    try:
        buffer = excel_import.export_ligne_assemblage_mixte_goulot_to_excel(
            request.products_data, 
            request.tasks_data, 
            request.s1,
            request.s2,
            request.unite
        )
        return StreamingResponse(
            io.BytesIO(buffer), 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=Export_Goulot_Mixte_Donnees_Manuelles.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ligne_assemblage_mixte/goulot/import-excel")
async def import_ligne_assemblage_mixte_goulot_excel(file: UploadFile = File(...), format_type: str = "ligne_assemblage_mixte_goulot"):
    try:
        data = await excel_import.parse_ligne_assemblage_mixte_goulot_excel(file)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

