import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Tuple, Dict, Any, Optional
import io
import base64
from pydantic import BaseModel
import numpy as np
from pulp import LpProblem, LpVariable, lpSum, LpMinimize, LpStatus, LpBinary

class FMSLotsProductionMIPRequest(BaseModel):
    # Configuration des produits
    noms_produits: List[str]
    grandeurs_commande: List[int]
    temps_operation_machines: List[List[float]]  # [produit][machine] en minutes
    outils_machines: List[List[List[str]]]       # [produit][machine][outils] - Changed to support multiple tools
    dates_dues: List[int]
    couts_inventaire: List[float]               # Coût de maintien en inventaire par produit
    
    # Configuration système
    temps_disponible_jour: float                # En minutes
    noms_machines: List[str]                   # ["Machine A", "Machine B", "Machine C", ...]
    nb_machines: List[int]                     # [1, 1, 2, ...] nombre par type
    capacite_outils: List[int]                 # [2, 2, 3, ...] capacité par type
    outils_disponibles: List[List[str]]        # [["A1", "A2"], ["B1", "B2"], ...] par machine
    espace_outils: List[List[int]]             # [[1, 1], [1, 1], ...] espace requis par outil
    unite_temps: str = "minutes"

def solve_fms_lots_production_mip(request: FMSLotsProductionMIPRequest) -> Dict[str, Any]:
    """
    Résout le problème de lots de production FMS avec l'algorithme MIP (PuLP)
    """
    try:
        # Préparation des données
        produits = []
        for i in range(len(request.noms_produits)):
            produit = (
                request.grandeurs_commande[i],
                request.temps_operation_machines[i],  # Liste des temps par machine
                request.outils_machines[i]             # Liste des outils par machine
            )
            produits.append(produit)
        
        cout_inv = tuple(request.couts_inventaire)
        date_due = tuple(request.dates_dues)
        temps = request.temps_disponible_jour
        nb_machines = tuple(request.nb_machines)
        capacite_outils = tuple(request.capacite_outils)
        outils = request.outils_disponibles
        espace_outil = request.espace_outils
        
        # Paramètres MIP
        T = max(date_due)  # Horizon de planification
        M = 100000  # Grande constante
        temps_max = [temps * nb for nb in nb_machines]
        outils_max = [cap * nb for cap, nb in zip(capacite_outils, nb_machines)]
        
        # Initialisation du problème
        prob = LpProblem("Problème de production FMS", LpMinimize)
        
        # Variables de décision
        # x[i][t]: quantité du produit i produite à la période t
        x = [[LpVariable(f'x_{i+1}_{t+1}', lowBound=0) for t in range(T)] for i in range(len(produits))]
        
        # y[j][l][t]: variable binaire indiquant si l'outil l de la machine j est utilisé à la période t
        y = [[[LpVariable(f'y_{j+1}_{l+1}_{t+1}', cat=LpBinary) for t in range(T)] 
              for l in range(len(outils[j]))] for j in range(len(nb_machines))]
        
        # Fonction objectif : minimiser le coût total d'inventaire
        prob += lpSum(cout_inv[i] * lpSum(
            lpSum(x[i][r] for r in range(t+1)) - 
            lpSum(produits[i][0] if r == date_due[i]-1 else 0 for r in range(t+1)) 
            for t in range(T)
        ) for i in range(len(produits)))
        
        # Contraintes de demande : satisfaire les commandes avant les dates dues
        for i in range(len(produits)):
            for t in range(T):
                prob += lpSum(x[i][r] for r in range(t+1)) >= lpSum(
                    produits[i][0] if r == date_due[i]-1 else 0 for r in range(t+1)
                )
        
        # Contraintes de capacité machines
        for j in range(len(nb_machines)):
            for t in range(T):
                prob += lpSum(produits[i][1][j] * x[i][t] for i in range(len(produits))) <= temps_max[j]
        
        # Contraintes de liaison outil-production (supports multiple tools per product/machine)
        for i in range(len(produits)):
            for j in range(len(nb_machines)):
                tools_required = produits[i][2][j]  # Now a list of tools
                if tools_required:  # If any tools are required
                    # For each required tool, ensure at least one is active
                    for tool_required in tools_required:
                        if tool_required in outils[j]:
                            l = outils[j].index(tool_required)
                            for t in range(T):
                                prob += x[i][t] <= M * y[j][l][t]
        
        # Contraintes de capacité outils
        for j in range(len(nb_machines)):
            for t in range(T):
                prob += lpSum(espace_outil[j][l] * y[j][l][t] for l in range(len(outils[j]))) <= outils_max[j]
        
        # Résoudre le problème
        prob.solve()
        
        # Extraction des résultats
        status = LpStatus[prob.status]
        cout_total = prob.objective.value() if prob.objective.value() else 0
        
        # Planification par période
        planification_periodes = []
        total_produit_par_periode = [0] * T
        
        for t in range(T):
            periode = {
                "numero": t + 1,
                "produits": [],
                "outils_utilises": {}
            }
            
            # Produits produits cette période
            for i in range(len(produits)):
                quantite = x[i][t].varValue if x[i][t].varValue else 0
                if quantite > 0:
                    periode["produits"].append({
                        "nom": request.noms_produits[i],
                        "quantite": round(quantite, 2),
                        "quantite_totale": produits[i][0],
                        "pourcentage": round((quantite / produits[i][0]) * 100, 1),
                        "date_due": date_due[i]
                    })
                    total_produit_par_periode[t] += quantite
            
            # Outils utilisés cette période
            for j in range(len(nb_machines)):
                outils_periode = []
                for l in range(len(outils[j])):
                    if y[j][l][t].varValue and y[j][l][t].varValue > 0:
                        outils_periode.append(outils[j][l])
                periode["outils_utilises"][request.noms_machines[j]] = outils_periode
            
            planification_periodes.append(periode)
        
        # Calcul des métriques (corrected to reflect per-period capacity constraints)
        utilisation_machines = []
        temps_utilise_machines = []
        
        for j in range(len(nb_machines)):
            # Calculate maximum utilization across all periods (not sum)
            utilisation_max_periode = 0
            temps_total_cumule = 0
            
            for t in range(T):
                temps_periode = 0
                for i in range(len(produits)):
                    quantite = x[i][t].varValue if x[i][t].varValue else 0
                    temps_periode += produits[i][1][j] * quantite
                    temps_total_cumule += produits[i][1][j] * quantite
                
                # Check utilization for this period
                utilisation_periode = (temps_periode / temps_max[j] * 100) if temps_max[j] > 0 else 0
                utilisation_max_periode = max(utilisation_max_periode, utilisation_periode)
            
            temps_utilise_machines.append(temps_total_cumule)
            # Use the maximum period utilization (should never exceed 100% if constraints work)
            utilisation_machines.append(utilisation_max_periode)
        
        # Résultats détaillés par machine
        resultats_machines = {}
        for j, nom_machine in enumerate(request.noms_machines):
            machine_key = nom_machine.lower().replace(' ', '_')
            resultats_machines[f"temps_disponible_total_{machine_key}"] = round(temps_max[j] * T, 2)  # Total over all periods
            resultats_machines[f"temps_utilise_{machine_key}"] = round(temps_utilise_machines[j], 2)  # Total over all periods
            resultats_machines[f"utilisation_{machine_key}"] = round(utilisation_machines[j], 1)  # Max period utilization
            resultats_machines[f"nb_{machine_key}"] = request.nb_machines[j]
            resultats_machines[f"temps_disponible_par_periode_{machine_key}"] = round(temps_max[j], 2)  # Per period capacity
        
        return {
            "status": status,
            "methode": "Mixed Integer Programming (MIP)",
            "critere_selection": "Minimisation coût inventaire",
            
            # Résultats optimisation
            "cout_total_inventaire": round(cout_total, 2),
            "horizon_planification": T,
            "statut_optimal": status == "Optimal",
            
            # Métriques système dynamiques
            **resultats_machines,
            
            # Configuration
            "noms_machines": request.noms_machines,
            "unite_temps": request.unite_temps,
            
            # Planification détaillée
            "planification_periodes": planification_periodes,
            "total_produits_par_periode": [round(x, 2) for x in total_produit_par_periode],
            
            # Efficacité globale (vraie efficacité : temps total utilisé / temps total disponible)
            "efficacite_globale": round((sum(temps_utilise_machines) / sum(temps_max[j] * T for j in range(len(nb_machines))) * 100), 1) if sum(temps_max[j] * T for j in range(len(nb_machines))) > 0 else 0,
            "efficacite_pic_moyen": round(sum(utilisation_machines) / len(utilisation_machines), 1) if utilisation_machines else 0,  # Ancienne métrique pour comparaison
            
            # Résumé
            "nombre_periodes": T,
            "nombre_produits": len(request.noms_produits),
            "nombre_machines": len(request.noms_machines)
        }
        
    except Exception as e:
        return {
            "status": "Erreur",
            "methode": "Mixed Integer Programming (MIP)",
            "message": f"Erreur lors du calcul: {str(e)}",
            "planification_periodes": [],
            "cout_total_inventaire": 0
        }

def generate_fms_lots_production_mip_chart(request: FMSLotsProductionMIPRequest):
    """
    Génère un graphique d'analyse pour les lots de production MIP
    """
    try:
        result = solve_fms_lots_production_mip(request)
        
        # Configuration du graphique
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Analyse FMS - Lots de Production (Mixed Integer Programming)', fontsize=16, fontweight='bold')
        
        # 1. Utilisation des machines
        noms_machines = result.get('noms_machines', [])
        utilisation = []
        temps_utilise = []
        temps_total = []
        
        for nom_machine in noms_machines:
            machine_key = nom_machine.lower().replace(' ', '_')
            utilisation.append(result.get(f'utilisation_{machine_key}', 0))
            temps_utilise.append(result.get(f'temps_utilise_{machine_key}', 0))
            temps_total.append(result.get(f'temps_disponible_total_{machine_key}', 0))
        
        colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316']
        bars = ax1.bar(noms_machines, utilisation, color=[colors[i % len(colors)] for i in range(len(noms_machines))], alpha=0.8)
        ax1.set_title('Utilisation des Machines (%)', fontweight='bold')
        ax1.set_ylabel('Pourcentage d\'utilisation')
        ax1.set_ylim(0, 100)
        
        # Ajouter les valeurs sur les barres
        for bar, util, temps_u, temps_t in zip(bars, utilisation, temps_utilise, temps_total):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{util:.1f}%\n({temps_u:.0f}min/{temps_t:.0f}min)',
                    ha='center', va='bottom', fontsize=9)
        
        # Rotation des labels si beaucoup de machines
        if len(noms_machines) > 3:
            ax1.tick_params(axis='x', rotation=45)
        
        # 2. Coût d'inventaire et statut
        statut = result.get('status', 'Unknown')
        cout_total = result.get('cout_total_inventaire', 0)
        optimal = result.get('statut_optimal', False)
        
        # Graphique en secteurs pour le statut
        statut_labels = ['Optimal' if optimal else 'Non-optimal']
        statut_sizes = [100]
        statut_colors = ['#10b981' if optimal else '#f59e0b']
        
        ax2.pie(statut_sizes, labels=statut_labels, colors=statut_colors, autopct='', startangle=90)
        ax2.set_title(f'Statut MIP\nCoût total: {cout_total:.2f}', fontweight='bold')
        
        # 3. Production par période
        planification = result.get('planification_periodes', [])
        total_par_periode = result.get('total_produits_par_periode', [])
        
        if planification:
            periodes = [p['numero'] for p in planification]
            
            bars = ax3.bar(periodes, total_par_periode, color='#8b5cf6', alpha=0.8)
            ax3.set_title('Production Totale par Période', fontweight='bold')
            ax3.set_xlabel('Période')
            ax3.set_ylabel('Quantité produite')
            ax3.set_xticks(periodes)
            ax3.set_xlim(0.5, max(periodes) + 0.5)  # Fix X-axis to start from proper range
            
            # Ajouter les valeurs sur les barres
            for bar, val in zip(bars, total_par_periode):
                if val > 0:
                    ax3.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(total_par_periode)*0.01,
                            f'{val:.1f}', ha='center', va='bottom', fontsize=10)
        else:
            ax3.text(0.5, 0.5, 'Aucune production planifiée', ha='center', va='center', 
                    transform=ax3.transAxes, fontsize=12)
            ax3.set_title('Production Totale par Période', fontweight='bold')
        
        # 4. Diagramme de Gantt des produits par période
        if planification:
            # Créer un graphique de Gantt simplifié
            y_positions = []
            y_labels = []
            y_pos = 0
            
            for periode in planification:
                if periode['produits']:
                    for produit in periode['produits']:
                        # Barre pour chaque produit dans chaque période
                        ax4.barh(y_pos, 1, left=periode['numero']-0.5, height=0.6, 
                                color=colors[hash(produit['nom']) % len(colors)], alpha=0.7)
                        
                        # Texte avec le nom et la quantité
                        ax4.text(periode['numero'], y_pos, 
                                f"{produit['nom']}\n{produit['quantite']:.1f}",
                                ha='center', va='center', fontsize=8, fontweight='bold')
                        
                        y_labels.append(f"P{periode['numero']}-{produit['nom']}")
                        y_pos += 1
            
            if y_labels:
                ax4.set_yticks(range(len(y_labels)))
                ax4.set_yticklabels(y_labels, fontsize=8)
                ax4.set_xlabel('Période')
                ax4.set_title('Planning Production par Période', fontweight='bold')
                ax4.grid(axis='x', alpha=0.3)
                # Set proper X-axis limits for the Gantt chart
                max_periode = max([p['numero'] for p in planification])
                ax4.set_xlim(0.5, max_periode + 0.5)
                ax4.set_xticks(range(1, max_periode + 1))
            else:
                ax4.text(0.5, 0.5, 'Aucune production', ha='center', va='center', 
                        transform=ax4.transAxes, fontsize=12)
                ax4.set_title('Planning Production par Période', fontweight='bold')
        else:
            ax4.text(0.5, 0.5, 'Aucune planification disponible', ha='center', va='center', 
                    transform=ax4.transAxes, fontsize=12)
            ax4.set_title('Planning Production par Période', fontweight='bold')
        
        plt.tight_layout()
        
        # Sauvegarder en mémoire
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        return img_buffer
        
    except Exception as e:
        # Créer un graphique d'erreur
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, f'Erreur lors de la génération du graphique:\n{str(e)}', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12)
        ax.set_title('Erreur - Analyse FMS Lots de Production MIP')
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        return img_buffer 