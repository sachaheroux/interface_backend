import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Tuple, Dict, Any, Optional
import io
import base64
from pydantic import BaseModel
import numpy as np

class FMSLotsChargementHeuristiqueRequest(BaseModel):
    # Configuration des opérations par machine (résultats phase 1 FMS)
    operations_machines: List[List[List[Any]]]  # [machine][operation][nom_operation, temps, outil]
    
    # Configuration des outils
    outils_espace: Dict[str, int]  # {"Y1": 1, "Y2": 1, ...}
    
    # Configuration des machines
    noms_machines: List[str]  # ["Machine A", "Machine B", "Machine C"]
    nb_machines: List[int]    # [2, 2, 1] nombre de machines par type
    capacite_temps: List[int]  # [800, 800, 800] capacité temps par type
    capacite_outils: List[int] # [3, 1, 4] capacité outils par type
    
    # Configuration système
    unite_temps: str = "minutes"

def solve_fms_lots_chargement_heuristique(request: FMSLotsChargementHeuristiqueRequest) -> Dict[str, Any]:
    """
    Résout le problème de lots de chargement FMS avec l'algorithme heuristique en 3 étapes
    """
    try:
        # Copie des données d'entrée
        phase_1 = [machine_ops.copy() for machine_ops in request.operations_machines]
        tools = request.outils_espace
        mj = tuple(request.nb_machines)
        Pj = tuple(request.capacite_temps)
        Kj = tuple(request.capacite_outils)
        
        # Étape 1: Tri des opérations par pièce et opération
        for machine_operations in phase_1:
            machine_operations.sort(key=lambda x: (x[0][2] if len(x[0]) > 2 else x[0], x[0][1] if len(x[0]) > 1 else x[0]))
        
        # Étape 2: Création des clusters
        clusters = create_clusters(phase_1, Pj, Kj, tools)
        
        # Étape 3: Formation des groupes
        g_j = create_groups(clusters, Kj, tools, mj)
        
        # Étape 4: Assignation des clusters aux groupes avec LPT
        assignments = assign_clusters_to_groups_LPT(clusters, g_j, Pj, mj)
        
        # Calcul des métriques
        total_operations = sum(len(machine_ops) for machine_ops in phase_1)
        total_clusters = sum(len(machine_clusters) for machine_clusters in clusters)
        total_groups = sum(g_j)
        
        # Calcul des temps totaux par machine
        temps_totaux_machines = []
        utilisation_machines = []
        
        for i, machine_clusters in enumerate(clusters):
            temps_total = sum(cluster[1] for cluster in machine_clusters)
            temps_totaux_machines.append(temps_total)
            capacite_totale = Pj[i] * mj[i]
            utilisation = (temps_total / capacite_totale * 100) if capacite_totale > 0 else 0
            utilisation_machines.append(utilisation)
        
        # Préparation des résultats détaillés
        resultats_machines = {}
        for i, nom_machine in enumerate(request.noms_machines):
            machine_key = nom_machine.lower().replace(' ', '_')
            resultats_machines[f"nb_operations_{machine_key}"] = len(phase_1[i])
            resultats_machines[f"nb_clusters_{machine_key}"] = len(clusters[i])
            resultats_machines[f"nb_groupes_{machine_key}"] = g_j[i]
            resultats_machines[f"temps_total_{machine_key}"] = temps_totaux_machines[i]
            resultats_machines[f"capacite_totale_{machine_key}"] = Pj[i] * mj[i]
            resultats_machines[f"utilisation_{machine_key}"] = round(utilisation_machines[i], 1)
        
        return {
            "status": "Optimal",
            "methode": "Heuristique de chargement par lots",
            "critere_selection": "LPT (Longest Processing Time)",
            
            # Résultats algorithme
            "nb_etapes": 3,
            "nb_operations_total": total_operations,
            "nb_clusters_total": total_clusters,
            "nb_groupes_total": total_groups,
            
            # Métriques système dynamiques
            **resultats_machines,
            
            # Configuration
            "noms_machines": request.noms_machines,
            "unite_temps": request.unite_temps,
            
            # Résultats détaillés
            "clusters": format_clusters_for_output(clusters, request.noms_machines),
            "groupes": format_groups_for_output(g_j, mj, request.noms_machines),
            "assignations": format_assignments_for_output(assignments, request.noms_machines),
            
            # Efficacité globale
            "efficacite_globale": round(sum(utilisation_machines) / len(utilisation_machines), 1) if utilisation_machines else 0,
            
            # Résumé
            "nombre_machines_types": len(request.noms_machines),
            "nombre_operations": total_operations,
            "nombre_clusters": total_clusters
        }
        
    except Exception as e:
        return {
            "status": "Erreur",
            "methode": "Heuristique de chargement par lots",
            "message": f"Erreur lors du calcul: {str(e)}",
            "clusters": [],
            "nb_operations_total": 0
        }

def create_clusters(phase, Pj, Kj, tools):
    """Étape 1: Création des clusters d'opérations"""
    clusters = []
    for i, machine_operations in enumerate(phase):
        machine_clusters = []
        cluster_time = 0
        cluster_tools = set()
        cluster_operations = []
        current_piece = None
        
        for operation in machine_operations:
            op_time = operation[1]
            op_tool = operation[2]
            piece = operation[0][2] if len(operation[0]) > 2 else operation[0][0]  # Extrait l'ID de la pièce
            
            if (current_piece is None or piece == current_piece) and \
               (cluster_time + op_time <= Pj[i] and len(cluster_tools | {op_tool}) <= Kj[i]):
                # Si le cluster est vide ou si l'opération appartient à la même pièce,
                # et qu'elle respecte les contraintes de temps et d'outil
                cluster_time += op_time
                cluster_tools.add(op_tool)
                cluster_operations.append(operation[0])
                current_piece = piece
            else:
                # Nouveau cluster nécessaire
                if cluster_operations:  # S'assurer que le cluster n'est pas vide
                    machine_clusters.append([cluster_operations, cluster_time, cluster_tools])
                cluster_time = op_time
                cluster_tools = {op_tool}
                cluster_operations = [operation[0]]
                current_piece = piece
        
        # Ajouter le dernier cluster s'il n'est pas vide
        if cluster_operations:
            machine_clusters.append([cluster_operations, cluster_time, cluster_tools])
        
        clusters.append(machine_clusters)
    
    return clusters

def create_groups(clusters, Kj, tools, mj):
    """Étape 2: Formation des groupes"""
    sigma_j = []
    for machine_clusters in clusters:
        total_tool_space = 0
        for cluster in machine_clusters:
            for tool in cluster[2]:
                total_tool_space += tools[tool]
        sigma_j.append(total_tool_space)
    
    # Calculer le nombre minimum de groupes faisables pour chaque type de machine
    g_j = [-(sj // -Kj[i]) if Kj[i] > 0 else 1 for i, sj in enumerate(sigma_j)]
    
    # Ajuster le nombre de groupes en fonction du nombre réel de machines disponibles
    for i, g in enumerate(g_j):
        if g > mj[i]:
            g_j[i] = mj[i]
    
    return g_j

def assign_clusters_to_groups_LPT(clusters, g_j, Pj, mj):
    """Étape 3: Assignation des clusters aux groupes avec LPT"""
    group_assignments = []
    
    for i, machine_clusters in enumerate(clusters):
        # Trier les clusters selon LPT (Longest Processing Time first)
        machine_clusters = sorted(machine_clusters, key=lambda x: x[1], reverse=True)
        
        # Initialiser ψ (psi) pour chaque groupe - temps disponible
        psi_values = [Pj[i] * (mj[i] // g_j[i]) for _ in range(g_j[i])]
        
        current_group_assignments = [[] for _ in range(g_j[i])]
        
        for cluster in machine_clusters:
            # Trouver le groupe avec le plus de temps disponible
            max_psi_index = psi_values.index(max(psi_values))
            
            # Assigner le cluster à ce groupe
            current_group_assignments[max_psi_index].append(cluster[0])
            
            # Mettre à jour le temps disponible pour ce groupe
            psi_values[max_psi_index] -= cluster[1]
        
        group_assignments.append(current_group_assignments)
    
    return group_assignments

def format_clusters_for_output(clusters, noms_machines):
    """Formate les clusters pour l'affichage"""
    formatted_clusters = []
    for i, machine_clusters in enumerate(clusters):
        machine_data = {
            "machine": noms_machines[i],
            "clusters": []
        }
        for j, cluster in enumerate(machine_clusters):
            operations, time, tools = cluster
            machine_data["clusters"].append({
                "numero": j + 1,
                "operations": operations,
                "temps_total": time,
                "outils": list(tools)
            })
        formatted_clusters.append(machine_data)
    return formatted_clusters

def format_groups_for_output(g_j, mj, noms_machines):
    """Formate les groupes pour l'affichage"""
    formatted_groups = []
    for i, g in enumerate(g_j):
        avg_machines = mj[i] // g if g > 0 else 0
        groupes_machine = []
        for j in range(g):
            if j < mj[i] % g:
                nb_machines = avg_machines + 1
            else:
                nb_machines = avg_machines
            groupes_machine.append({
                "numero": j + 1,
                "nb_machines": nb_machines
            })
        
        formatted_groups.append({
            "machine": noms_machines[i],
            "nb_groupes": g,
            "groupes": groupes_machine
        })
    return formatted_groups

def format_assignments_for_output(assignments, noms_machines):
    """Formate les assignations pour l'affichage"""
    formatted_assignments = []
    for i, machine_assignment in enumerate(assignments):
        machine_data = {
            "machine": noms_machines[i],
            "assignations": []
        }
        for j, group in enumerate(machine_assignment):
            machine_data["assignations"].append({
                "groupe": j + 1,
                "operations": group
            })
        formatted_assignments.append(machine_data)
    return formatted_assignments

def generate_fms_lots_chargement_heuristique_chart(request: FMSLotsChargementHeuristiqueRequest):
    """
    Génère un graphique d'analyse pour les lots de chargement heuristique
    """
    try:
        result = solve_fms_lots_chargement_heuristique(request)
        
        # Configuration du graphique
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Analyse FMS - Lots de Chargement (Heuristique)', fontsize=16, fontweight='bold')
        
        # 1. Nombre d'opérations vs clusters vs groupes
        noms_machines = result.get('noms_machines', [])
        nb_operations = []
        nb_clusters = []
        nb_groupes = []
        
        for nom_machine in noms_machines:
            machine_key = nom_machine.lower().replace(' ', '_')
            nb_operations.append(result.get(f'nb_operations_{machine_key}', 0))
            nb_clusters.append(result.get(f'nb_clusters_{machine_key}', 0))
            nb_groupes.append(result.get(f'nb_groupes_{machine_key}', 0))
        
        x = np.arange(len(noms_machines))
        width = 0.25
        
        ax1.bar(x - width, nb_operations, width, label='Opérations', color='#3b82f6', alpha=0.8)
        ax1.bar(x, nb_clusters, width, label='Clusters', color='#10b981', alpha=0.8)
        ax1.bar(x + width, nb_groupes, width, label='Groupes', color='#f59e0b', alpha=0.8)
        
        ax1.set_title('Répartition par Machine', fontweight='bold')
        ax1.set_xlabel('Types de machines')
        ax1.set_ylabel('Nombre')
        ax1.set_xticks(x)
        ax1.set_xticklabels(noms_machines, rotation=45 if len(noms_machines) > 3 else 0)
        ax1.legend()
        ax1.grid(axis='y', alpha=0.3)
        
        # 2. Utilisation des machines
        utilisation = []
        for nom_machine in noms_machines:
            machine_key = nom_machine.lower().replace(' ', '_')
            utilisation.append(result.get(f'utilisation_{machine_key}', 0))
        
        colors = ['#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']
        bars = ax2.bar(noms_machines, utilisation, color=[colors[i % len(colors)] for i in range(len(noms_machines))], alpha=0.8)
        ax2.set_title('Utilisation des Machines (%)', fontweight='bold')
        ax2.set_ylabel('Pourcentage d\'utilisation')
        ax2.set_ylim(0, 100)
        
        # Ajouter les valeurs sur les barres
        for bar, util in zip(bars, utilisation):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{util:.1f}%',
                    ha='center', va='bottom', fontsize=10)
        
        if len(noms_machines) > 3:
            ax2.tick_params(axis='x', rotation=45)
        
        # 3. Temps de traitement par machine
        temps_totaux = []
        capacites_totales = []
        
        for nom_machine in noms_machines:
            machine_key = nom_machine.lower().replace(' ', '_')
            temps_totaux.append(result.get(f'temps_total_{machine_key}', 0))
            capacites_totales.append(result.get(f'capacite_totale_{machine_key}', 0))
        
        x = np.arange(len(noms_machines))
        width = 0.35
        
        ax3.bar(x - width/2, temps_totaux, width, label='Temps utilisé', color='#ef4444', alpha=0.8)
        ax3.bar(x + width/2, capacites_totales, width, label='Capacité totale', color='#6b7280', alpha=0.8)
        
        ax3.set_title('Temps de Traitement', fontweight='bold')
        ax3.set_xlabel('Types de machines')
        ax3.set_ylabel(f'Temps ({result.get("unite_temps", "minutes")})')
        ax3.set_xticks(x)
        ax3.set_xticklabels(noms_machines, rotation=45 if len(noms_machines) > 3 else 0)
        ax3.legend()
        ax3.grid(axis='y', alpha=0.3)
        
        # 4. Métriques globales (diagramme en secteurs)
        if result.get('clusters'):
            labels = ['Opérations', 'Clusters', 'Groupes']
            sizes = [
                result.get('nb_operations_total', 0),
                result.get('nb_clusters_total', 0),
                result.get('nb_groupes_total', 0)
            ]
            colors_pie = ['#3b82f6', '#10b981', '#f59e0b']
            
            # Filtrer les valeurs nulles
            filtered_data = [(label, size, color) for label, size, color in zip(labels, sizes, colors_pie) if size > 0]
            if filtered_data:
                labels_f, sizes_f, colors_f = zip(*filtered_data)
                wedges, texts, autotexts = ax4.pie(sizes_f, labels=labels_f, colors=colors_f, autopct='%1.0f', startangle=90)
                ax4.set_title(f'Répartition Globale\nEfficacité: {result.get("efficacite_globale", 0):.1f}%', fontweight='bold')
            else:
                ax4.text(0.5, 0.5, 'Aucune donnée disponible', ha='center', va='center', 
                        transform=ax4.transAxes, fontsize=12)
                ax4.set_title('Répartition Globale', fontweight='bold')
        else:
            ax4.text(0.5, 0.5, 'Aucun cluster généré', ha='center', va='center', 
                    transform=ax4.transAxes, fontsize=12)
            ax4.set_title('Répartition Globale', fontweight='bold')
        
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
        ax.set_title('Erreur - Analyse FMS Lots de Chargement Heuristique')
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        return img_buffer 