import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import base64
from pydantic import BaseModel
from typing import List

class FMSSacADosGloutonRequest(BaseModel):
    vente_unite: List[float]  # Prix de vente par unité
    cout_mp_unite: List[float]  # Coût matière première par unité
    demande_periode: List[int]  # Demande par période
    temps_fabrication_unite: List[float]  # Temps de fabrication par unité
    cout_op: float  # Coût d'opération par heure
    capacite_max: int  # Capacité maximale en heures
    noms_produits: List[str] = None  # Noms des produits (optionnel)
    unite: str = "heures"

def solve_fms_sac_a_dos_glouton(request: FMSSacADosGloutonRequest):
    """
    Résout le problème du sac à dos FMS avec l'algorithme glouton
    Utilise la désirabilité (profit/temps) comme critère de sélection
    """
    try:
        # Extraction des données
        vente_unite = np.array(request.vente_unite)
        cout_mp_unite = np.array(request.cout_mp_unite)
        demande_periode = np.array(request.demande_periode)
        temps_fabrication_unite = np.array(request.temps_fabrication_unite)
        cout_op = request.cout_op
        capacite_max = request.capacite_max
        
        # Noms des produits par défaut si non fournis
        if request.noms_produits is None:
            noms_produits = [f"Produit {i+1}" for i in range(len(vente_unite))]
        else:
            noms_produits = request.noms_produits
        
        n = len(vente_unite)
        
        # Calculs préliminaires
        profits_unitaires = vente_unite - (cout_op * temps_fabrication_unite + cout_mp_unite)
        s = profits_unitaires * demande_periode  # Profits totaux par produit
        p = demande_periode * temps_fabrication_unite  # Temps requis par produit
        
        # Calcul de la désirabilité (profit/temps) - critère glouton
        desirabilite = np.where(p > 0, s / p, 0)  # Éviter division par zéro
        
        # Tri des indices par désirabilité décroissante
        indices_tries = np.argsort(-desirabilite)
        
        # Algorithme glouton
        capacite_actuelle = 0
        profit_total = 0
        produits_selectionnes_idx = []
        
        for i in indices_tries:
            # Vérifier si on peut ajouter ce produit
            if capacite_actuelle + p[i] <= capacite_max and s[i] > 0:  # Profit positif
                capacite_actuelle += p[i]
                profit_total += s[i]
                produits_selectionnes_idx.append(i)
        
        # Calcul des métriques
        utilisation_capacite = (capacite_actuelle / capacite_max) * 100 if capacite_max > 0 else 0
        
        # Détails des produits sélectionnés
        produits_details = []
        for idx in produits_selectionnes_idx:
            produits_details.append({
                "nom": noms_produits[idx],
                "index": int(idx + 1),
                "profit_unitaire": round(float(profits_unitaires[idx]), 2),
                "profit_total": round(float(s[idx]), 2),
                "temps_requis": round(float(p[idx]), 1),
                "demande": int(demande_periode[idx]),
                "prix_vente": float(vente_unite[idx]),
                "cout_mp": float(cout_mp_unite[idx]),
                "temps_fabrication": float(temps_fabrication_unite[idx]),
                "desirabilite": round(float(desirabilite[idx]), 2)
            })
        
        # Produits non sélectionnés avec raison
        produits_non_selectionnes = []
        for idx in range(n):
            if idx not in produits_selectionnes_idx:
                if s[idx] <= 0:
                    raison = "Profit négatif ou nul"
                elif p[idx] > (capacite_max - sum(p[i] for i in produits_selectionnes_idx if indices_tries.tolist().index(i) < indices_tries.tolist().index(idx))):
                    raison = "Capacité insuffisante"
                else:
                    raison = "Désirabilité faible"
                
                produits_non_selectionnes.append({
                    "nom": noms_produits[idx],
                    "index": int(idx + 1),
                    "profit_unitaire": round(float(profits_unitaires[idx]), 2),
                    "profit_total": round(float(s[idx]), 2),
                    "temps_requis": round(float(p[idx]), 1),
                    "demande": int(demande_periode[idx]),
                    "desirabilite": round(float(desirabilite[idx]), 2),
                    "raison_exclusion": raison
                })
        
        return {
            "status": "Solution Gloutonne",
            "profit_maximal": float(profit_total),
            "capacite_utilisee": round(float(capacite_actuelle), 1),
            "capacite_totale": int(capacite_max),
            "utilisation_capacite": round(float(utilisation_capacite), 1),
            "nombre_produits_selectionnes": len(produits_selectionnes_idx),
            "produits_selectionnes": produits_details,
            "produits_non_selectionnes": produits_non_selectionnes,
            "cout_operation_horaire": float(cout_op),
            "unite": request.unite,
            "efficacite": round((float(profit_total) / (capacite_max * cout_op)) * 100, 1) if capacite_max > 0 else 0,
            "methode": "Algorithme Glouton (Désirabilité)",
            "critere_selection": "Profit/Temps (Désirabilité)"
        }
        
    except Exception as e:
        return {
            "status": "Erreur",
            "message": str(e),
            "profit_maximal": 0,
            "capacite_utilisee": 0,
            "capacite_totale": capacite_max,
            "utilisation_capacite": 0,
            "nombre_produits_selectionnes": 0,
            "produits_selectionnes": [],
            "produits_non_selectionnes": []
        }

def generate_fms_sac_a_dos_glouton_chart(result):
    """Génère les graphiques d'analyse du sac à dos FMS glouton"""
    try:
        if result["status"] == "Erreur":
            raise ValueError(result.get("message", "Erreur inconnue"))
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Analyse FMS - Algorithme Glouton (Désirabilité)', fontsize=16, fontweight='bold')
        
        # Graphique 1: Désirabilité des produits
        tous_produits = result["produits_selectionnes"] + result["produits_non_selectionnes"]
        if tous_produits:
            noms = [p["nom"] for p in tous_produits]
            desirabilites = [p["desirabilite"] for p in tous_produits]
            
            # Couleurs selon sélection
            colors = ['#10b981' if p in result["produits_selectionnes"] else '#ef4444' for p in tous_produits]
            
            bars1 = ax1.bar(range(len(noms)), desirabilites, color=colors, alpha=0.8)
            ax1.set_title('Désirabilité des Produits (Profit/Temps)', fontweight='bold')
            ax1.set_xlabel('Produits')
            ax1.set_ylabel('Désirabilité ($/heure)')
            ax1.set_xticks(range(len(noms)))
            ax1.set_xticklabels([p["nom"] for p in tous_produits], rotation=45, ha='right')
            ax1.grid(axis='y', alpha=0.3)
            
            # Légende
            from matplotlib.patches import Patch
            legend_elements = [Patch(facecolor='#10b981', label='Sélectionné'),
                              Patch(facecolor='#ef4444', label='Non sélectionné')]
            ax1.legend(handles=legend_elements, loc='upper right')
            
            # Ajout des valeurs sur les barres
            for bar, val in zip(bars1, desirabilites):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{val:.1f}', ha='center', va='bottom', fontweight='bold', fontsize=8)
        else:
            ax1.text(0.5, 0.5, 'Aucune donnée disponible', ha='center', va='center', 
                    transform=ax1.transAxes, fontsize=12)
            ax1.set_title('Désirabilité des Produits', fontweight='bold')
        
        # Graphique 2: Utilisation de la capacité
        capacite_utilisee = result["capacite_utilisee"]
        capacite_restante = result["capacite_totale"] - capacite_utilisee
        
        sizes = [capacite_utilisee, capacite_restante]
        labels = [f'Utilisée\n{capacite_utilisee:.1f}h', f'Disponible\n{capacite_restante:.1f}h']
        colors_pie = ['#3b82f6', '#e5e7eb']
        
        wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.1f%%',
                                          startangle=90, textprops={'fontweight': 'bold'})
        ax2.set_title(f'Utilisation de la Capacité\n({result["utilisation_capacite"]:.1f}% utilisée)', 
                     fontweight='bold')
        
        # Graphique 3: Ordre de sélection glouton
        if result["produits_selectionnes"]:
            noms_sel = [p["nom"] for p in result["produits_selectionnes"]]
            profits_sel = [p["profit_total"] for p in result["produits_selectionnes"]]
            desirabilites_sel = [p["desirabilite"] for p in result["produits_selectionnes"]]
            
            # Graphique avec double axe
            ax3_twin = ax3.twinx()
            
            # Barres pour les profits
            bars3 = ax3.bar(range(len(noms_sel)), profits_sel, alpha=0.7, color='#8b5cf6', label='Profit Total')
            ax3.set_ylabel('Profit Total ($)', color='#8b5cf6')
            ax3.tick_params(axis='y', labelcolor='#8b5cf6')
            
            # Ligne pour la désirabilité
            line3 = ax3_twin.plot(range(len(noms_sel)), desirabilites_sel, 'o-', color='#f59e0b', 
                                 linewidth=2, markersize=8, label='Désirabilité')
            ax3_twin.set_ylabel('Désirabilité ($/h)', color='#f59e0b')
            ax3_twin.tick_params(axis='y', labelcolor='#f59e0b')
            
            ax3.set_title('Ordre de Sélection Glouton', fontweight='bold')
            ax3.set_xlabel('Ordre de Sélection')
            ax3.set_xticks(range(len(noms_sel)))
            ax3.set_xticklabels([f'{i+1}' for i in range(len(noms_sel))])
            ax3.grid(axis='y', alpha=0.3)
            
            # Annotations des noms de produits
            for i, nom in enumerate(noms_sel):
                ax3.text(i, profits_sel[i]/2, nom, ha='center', va='center', 
                        rotation=90, fontweight='bold', fontsize=8)
        else:
            ax3.text(0.5, 0.5, 'Aucun produit sélectionné', ha='center', va='center', 
                    transform=ax3.transAxes, fontsize=12)
            ax3.set_title('Ordre de Sélection Glouton', fontweight='bold')
        
        # Graphique 4: Métriques de performance
        metriques = ['Profit Total', 'Efficacité', 'Utilisation', 'Nb Produits']
        valeurs = [
            result["profit_maximal"] / 100,  # Normalisation pour affichage
            result["efficacite"],
            result["utilisation_capacite"],
            result["nombre_produits_selectionnes"] * 10  # Multiplication pour visibilité
        ]
        
        bars4 = ax4.bar(metriques, valeurs, color=['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6'])
        ax4.set_title('Métriques de Performance', fontweight='bold')
        ax4.set_ylabel('Valeurs (normalisées)')
        
        # Ajout des vraies valeurs sur les barres
        vraies_valeurs = [f'${result["profit_maximal"]:.0f}', f'{result["efficacite"]:.1f}%', 
                         f'{result["utilisation_capacite"]:.1f}%', f'{result["nombre_produits_selectionnes"]}']
        for bar, valeur in zip(bars4, vraies_valeurs):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    valeur, ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        
        # Sauvegarde en base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return image_base64
        
    except Exception as e:
        # Créer un graphique d'erreur simple
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, f'Erreur lors de la génération du graphique:\n{str(e)}', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12)
        ax.set_title('Erreur - Graphique FMS Sac à Dos Glouton')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return image_base64 