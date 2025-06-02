import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Tuple, Dict, Any, Optional
import io
import base64
from pydantic import BaseModel
import numpy as np

class FMSLotsProductionGloutonRequest(BaseModel):
    # Configuration des produits
    noms_produits: List[str]
    grandeurs_commande: List[int]
    temps_operation_machines: List[List[float]]  # [produit][machine]
    outils_machines: List[List[Optional[str]]]   # [produit][machine]
    dates_dues: List[int]
    
    # Configuration système
    temps_disponible_jour: float
    noms_machines: List[str]           # ["Machine A", "Machine B", "Machine C", ...]
    nb_machines: List[int]             # [3, 1, 2, ...] nombre par type
    capacite_outils: List[int]         # [2, 2, 3, ...] capacité par type
    unite_temps: str = "heures"

def solve_fms_lots_production_glouton(request: FMSLotsProductionGloutonRequest) -> Dict[str, Any]:
    """
    Résout le problème de lots de production FMS avec l'algorithme glouton
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
        
        date_due = tuple(request.dates_dues)
        temps = request.temps_disponible_jour
        nb_machines = tuple(request.nb_machines)
        capacite_outils = tuple(request.capacite_outils)
        
        # Appel de l'algorithme
        assigned_products, used_time, used_tools = assign_products(
            produits, date_due, temps, nb_machines, capacite_outils
        )
        
        # Calcul des métriques
        temps_max = [temps * machine for machine in nb_machines]
        utilisation_machines = [(used_time[i] / temps_max[i] * 100) if temps_max[i] > 0 else 0 
                               for i in range(len(nb_machines))]
        
        # Formatage des résultats
        produits_assignes = []
        for idx, quantity, times, tools in assigned_products:
            produit_original = produits[idx-1]
            grandeur_originale = produit_original[0]
            pourcentage_assigne = (quantity / grandeur_originale) * 100
            
            # Créer les temps et outils par machine
            temps_machines = {}
            outils_machines = {}
            for i, nom_machine in enumerate(request.noms_machines):
                temps_machines[f"temps_{nom_machine.lower().replace(' ', '_')}"] = round(times[i], 2)
                outils_machines[f"outil_{nom_machine.lower().replace(' ', '_')}"] = tools[i][0] if tools[i] and tools[i][0] else None
            
            produit_assigne = {
                "nom": request.noms_produits[idx-1],
                "index": idx,
                "quantite_assignee": round(quantity),
                "quantite_totale": grandeur_originale,
                "pourcentage_assigne": round(pourcentage_assigne, 1),
                "date_due": request.dates_dues[idx-1],
                **temps_machines,
                **outils_machines
            }
            produits_assignes.append(produit_assigne)
        
        # Produits non assignés
        produits_non_assignes = []
        assigned_indices = [p[0] for p in assigned_products]
        for i, nom in enumerate(request.noms_produits):
            if (i+1) not in assigned_indices:
                produits_non_assignes.append({
                    "nom": nom,
                    "index": i+1,
                    "raison": "Contraintes de capacité ou d'outils non satisfaites",
                    "date_due": request.dates_dues[i],
                    "grandeur_commande": request.grandeurs_commande[i]
                })
        
        # Résultats par machine
        resultats_machines = {}
        outils_utilises = {}
        for i, nom_machine in enumerate(request.noms_machines):
            resultats_machines[f"temps_disponible_total_{nom_machine.lower().replace(' ', '_')}"] = round(temps_max[i], 2)
            resultats_machines[f"temps_utilise_{nom_machine.lower().replace(' ', '_')}"] = round(used_time[i], 2)
            resultats_machines[f"utilisation_{nom_machine.lower().replace(' ', '_')}"] = round(utilisation_machines[i], 1)
            resultats_machines[f"nb_{nom_machine.lower().replace(' ', '_')}"] = request.nb_machines[i]
            resultats_machines[f"capacite_outils_{nom_machine.lower().replace(' ', '_')}"] = request.capacite_outils[i]
            outils_utilises[f"outils_utilises_{nom_machine.lower().replace(' ', '_')}"] = list(used_tools[i]) if used_tools[i] else []
        
        return {
            "status": "Optimal" if len(assigned_products) > 0 else "Aucune solution",
            "methode": "Algorithme Glouton",
            "critere_selection": "Priorité par date due croissante",
            
            # Métriques système dynamiques
            **resultats_machines,
            **outils_utilises,
            
            # Configuration
            "noms_machines": request.noms_machines,
            "unite_temps": request.unite_temps,
            
            # Résultats
            "nombre_produits_assignes": len(produits_assignes),
            "nombre_produits_non_assignes": len(produits_non_assignes),
            "produits_assignes": produits_assignes,
            "produits_non_assignes": produits_non_assignes,
            
            # Efficacité globale
            "efficacite_globale": round(sum(utilisation_machines) / len(utilisation_machines), 1) if utilisation_machines else 0
        }
        
    except Exception as e:
        return {
            "status": "Erreur",
            "methode": "Algorithme Glouton",
            "message": f"Erreur lors du calcul: {str(e)}",
            "produits_assignes": [],
            "produits_non_assignes": []
        }

def assign_products(produits, date_due, temps, nb_machines, capacite_outils):
    """
    Fonction d'assignation des produits adaptée pour un nombre variable de machines
    """
    temps_max = [temps * machine for machine in nb_machines]
    outils_max = [capacite * machine for capacite, machine in zip(capacite_outils, nb_machines)]

    # Créer un tableau contenant les informations des produits, en y ajoutant l'index original du produit
    products = sorted([(dd, p, i+1) for i, (dd, p) in enumerate(zip(date_due, produits))], key=lambda x: x[0])

    assigned_products = []
    used_time = [0] * len(nb_machines)
    used_tools = [set() for _ in range(len(nb_machines))]

    for due_date, product, idx in products:
        grandeur, op_time, tools = product

        # S'assurer que tools sont des listes
        tools = [tool if isinstance(tool, list) else [tool] for tool in tools]

        # Calculer la fraction de la commande qui peut être assignée
        fractions = [min(grandeur, int((max_t - used) / op)) if op > 0 else grandeur 
                    for used, op, max_t in zip(used_time, op_time, temps_max)]
        fraction = min(fractions)

        # Vérifier si le produit (ou une portion du produit) peut être assigné sans violer les contraintes
        can_assign = True
        
        # Vérification des contraintes d'outils
        for toolset, used_toolset, max_tools in zip(tools, used_tools, outils_max):
            if toolset and toolset[0] is not None:
                # Calculer combien d'outils seraient nécessaires
                new_tools = [tool for tool in toolset if tool is not None and tool not in used_toolset]
                if len(used_toolset) + len(new_tools) > max_tools:
                    can_assign = False
                    break
        
        if can_assign and fraction > 0:
            # Assigner le produit (ou une portion du produit)
            assigned_products.append((idx, fraction, [op * fraction for op in op_time], tools))

            # Mettre à jour le temps et les outils utilisés
            used_time = [used + op * fraction for used, op in zip(used_time, op_time)]
            for toolset, used_toolset in zip(tools, used_tools):
                if toolset and toolset[0] is not None:
                    used_toolset.update([tool for tool in toolset if tool is not None])

    return assigned_products, used_time, used_tools

def generate_fms_lots_production_glouton_chart(request: FMSLotsProductionGloutonRequest):
    """
    Génère un graphique d'analyse pour les lots de production avec nombre variable de machines
    """
    try:
        result = solve_fms_lots_production_glouton(request)
        
        # Configuration du graphique
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Analyse FMS - Lots de Production (Algorithme Glouton)', fontsize=16, fontweight='bold')
        
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
                    f'{util:.1f}%\n({temps_u:.1f}h/{temps_t:.1f}h)',
                    ha='center', va='bottom', fontsize=9)
        
        # Rotation des labels si beaucoup de machines
        if len(noms_machines) > 3:
            ax1.tick_params(axis='x', rotation=45)
        
        # 2. Répartition des produits assignés vs non assignés
        nb_assignes = result.get('nombre_produits_assignes', 0)
        nb_non_assignes = result.get('nombre_produits_non_assignes', 0)
        total_produits = nb_assignes + nb_non_assignes
        
        if total_produits > 0:
            labels = ['Assignés', 'Non assignés']
            sizes = [nb_assignes, nb_non_assignes]
            colors_pie = ['#10b981', '#ef4444']
            explode = (0.05, 0)
            
            wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors_pie, explode=explode,
                                              autopct='%1.1f%%', startangle=90)
            ax2.set_title('Répartition des Produits', fontweight='bold')
        else:
            ax2.text(0.5, 0.5, 'Aucun produit', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Répartition des Produits', fontweight='bold')
        
        # 3. Utilisation des outils
        utilisation_outils = []
        capacite_outils_list = []
        
        for nom_machine in noms_machines:
            machine_key = nom_machine.lower().replace(' ', '_')
            outils_utilises = result.get(f'outils_utilises_{machine_key}', [])
            capacite = result.get(f'capacite_outils_{machine_key}', 0)
            utilisation_outils.append(len(outils_utilises))
            capacite_outils_list.append(capacite)
        
        x_pos = np.arange(len(noms_machines))
        bars_utilises = ax3.bar(x_pos - 0.2, utilisation_outils, 0.4, label='Outils utilisés', color='#8b5cf6', alpha=0.8)
        bars_capacite = ax3.bar(x_pos + 0.2, capacite_outils_list, 0.4, label='Capacité totale', color='#e2e8f0', alpha=0.8)
        
        ax3.set_title('Utilisation des Outils', fontweight='bold')
        ax3.set_ylabel('Nombre d\'outils')
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(noms_machines)
        ax3.legend()
        
        if len(noms_machines) > 3:
            ax3.tick_params(axis='x', rotation=45)
        
        # Ajouter les valeurs sur les barres
        for bar, val in zip(bars_utilises, utilisation_outils):
            if val > 0:
                ax3.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05,
                        str(val), ha='center', va='bottom', fontsize=10)
        
        for bar, val in zip(bars_capacite, capacite_outils_list):
            if val > 0:
                ax3.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05,
                        str(val), ha='center', va='bottom', fontsize=10)
        
        # 4. Gantt des produits assignés par date due
        produits_assignes = result.get('produits_assignes', [])
        if produits_assignes:
            # Trier par date due
            produits_assignes_tries = sorted(produits_assignes, key=lambda x: x['date_due'])
            
            y_positions = range(len(produits_assignes_tries))
            dates_dues = [p['date_due'] for p in produits_assignes_tries]
            noms = [p['nom'] for p in produits_assignes_tries]
            
            # Créer le diagramme de Gantt
            for i, produit in enumerate(produits_assignes_tries):
                ax4.barh(i, 1, left=produit['date_due'], height=0.6, 
                        color='#3b82f6', alpha=0.7, edgecolor='black')
                
                # Ajouter le pourcentage assigné
                ax4.text(produit['date_due'] + 0.5, i, 
                        f"{produit['pourcentage_assigne']:.1f}%",
                        ha='center', va='center', fontsize=8, fontweight='bold')
            
            ax4.set_yticks(y_positions)
            ax4.set_yticklabels(noms)
            ax4.set_xlabel('Date due (jours)')
            ax4.set_title('Planning des Produits Assignés', fontweight='bold')
            ax4.grid(axis='x', alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'Aucun produit assigné', ha='center', va='center', 
                    transform=ax4.transAxes, fontsize=12)
            ax4.set_title('Planning des Produits Assignés', fontweight='bold')
        
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
        ax.set_title('Erreur - Analyse FMS Lots de Production')
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        return img_buffer 