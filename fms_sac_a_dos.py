import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from pydantic import BaseModel
from typing import List
import matplotlib
matplotlib.use('Agg')

class FMSSacADosRequest(BaseModel):
    vente_unite: List[float]  # Prix de vente par unité
    cout_mp_unite: List[float]  # Coût matière première par unité
    demande_periode: List[int]  # Demande par période
    temps_fabrication_unite: List[float]  # Temps de fabrication par unité
    cout_op: float  # Coût d'opération par heure
    capacite_max: int  # Capacité maximale en heures
    noms_produits: List[str] = None  # Noms des produits (optionnel)
    unite: str = "heures"

def solve_fms_sac_a_dos(request: FMSSacADosRequest):
    try:
        # Conversion en arrays numpy
        vente_unite = np.array(request.vente_unite)
        cout_mp_unite = np.array(request.cout_mp_unite)
        demande_periode = np.array(request.demande_periode)
        temps_fabrication_unite = np.array(request.temps_fabrication_unite)
        cout_op = request.cout_op
        capacite_max = request.capacite_max
        
        # Validation des données
        n = len(vente_unite)
        if not all(len(arr) == n for arr in [cout_mp_unite, demande_periode, temps_fabrication_unite]):
            raise ValueError("Toutes les listes doivent avoir la même longueur")
        
        # Noms des produits par défaut si non fournis
        if request.noms_produits is None:
            noms_produits = [f"Produit {i+1}" for i in range(n)]
        else:
            noms_produits = request.noms_produits
        
        # Calculs préliminaires
        p = (temps_fabrication_unite * demande_periode).astype(int)  # Temps requis par produit
        profits_unitaires = vente_unite - (cout_op * temps_fabrication_unite + cout_mp_unite)
        s = profits_unitaires * demande_periode  # Profits totaux par produit
        
        # Initialisation du tableau pour la programmation dynamique
        dp = np.zeros((n+1, capacite_max+1))
        
        # Algorithme de programmation dynamique
        for i in range(1, n+1):
            for j in range(capacite_max+1):
                if p[i-1] <= j:
                    dp[i, j] = max(dp[i-1, j], s[i-1] + dp[i-1, j-p[i-1]])
                else:
                    dp[i, j] = dp[i-1, j]
        
        # Reconstruction de la solution
        produits_selectionnes_idx = []
        j = capacite_max
        for i in range(n, 0, -1):
            if dp[i, j] != dp[i-1, j]:
                produits_selectionnes_idx.append(i-1)  # Index 0-based
                j -= p[i-1]
        
        produits_selectionnes_idx.reverse()  # Ordre original
        
        # Calcul des métriques
        profit_maximal = dp[n, capacite_max]
        capacite_utilisee = sum(p[i] for i in produits_selectionnes_idx)
        utilisation_capacite = (capacite_utilisee / capacite_max) * 100 if capacite_max > 0 else 0
        
        # Détails des produits sélectionnés
        produits_details = []
        for idx in produits_selectionnes_idx:
            produits_details.append({
                "nom": noms_produits[idx],
                "index": int(idx + 1),
                "profit_unitaire": round(float(profits_unitaires[idx]), 2),
                "profit_total": round(float(s[idx]), 2),
                "temps_requis": int(p[idx]),
                "demande": int(demande_periode[idx]),
                "prix_vente": float(vente_unite[idx]),
                "cout_mp": float(cout_mp_unite[idx]),
                "temps_fabrication": float(temps_fabrication_unite[idx])
            })
        
        # Produits non sélectionnés
        produits_non_selectionnes = []
        for idx in range(n):
            if idx not in produits_selectionnes_idx:
                produits_non_selectionnes.append({
                    "nom": noms_produits[idx],
                    "index": int(idx + 1),
                    "profit_unitaire": round(float(profits_unitaires[idx]), 2),
                    "profit_total": round(float(s[idx]), 2),
                    "temps_requis": int(p[idx]),
                    "demande": int(demande_periode[idx]),
                    "raison_exclusion": "Capacité insuffisante ou profit faible"
                })
        
        return {
            "status": "Optimal",
            "profit_maximal": float(profit_maximal),
            "capacite_utilisee": int(capacite_utilisee),
            "capacite_totale": int(capacite_max),
            "utilisation_capacite": round(float(utilisation_capacite), 1),
            "nombre_produits_selectionnes": len(produits_selectionnes_idx),
            "produits_selectionnes": produits_details,
            "produits_non_selectionnes": produits_non_selectionnes,
            "cout_operation_horaire": float(cout_op),
            "unite": request.unite,
            "efficacite": round((float(profit_maximal) / (capacite_max * cout_op)) * 100, 1) if capacite_max > 0 else 0
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

def generate_fms_sac_a_dos_chart(result):
    """Génère les graphiques d'analyse du sac à dos FMS"""
    try:
        if result["status"] == "Erreur":
            raise ValueError(result.get("message", "Erreur inconnue"))
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Analyse FMS - Algorithme du Sac à Dos', fontsize=16, fontweight='bold')
        
        # Graphique 1: Profits par produit sélectionné
        if result["produits_selectionnes"]:
            noms = [p["nom"] for p in result["produits_selectionnes"]]
            profits = [p["profit_total"] for p in result["produits_selectionnes"]]
            
            bars1 = ax1.bar(range(len(noms)), profits, color='#2E8B57', alpha=0.8)
            ax1.set_title('Profits des Produits Sélectionnés', fontweight='bold')
            ax1.set_xlabel('Produits')
            ax1.set_ylabel('Profit Total ($)')
            ax1.set_xticks(range(len(noms)))
            ax1.set_xticklabels(noms, rotation=45, ha='right')
            ax1.grid(axis='y', alpha=0.3)
            
            # Ajout des valeurs sur les barres
            for bar, profit in zip(bars1, profits):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'${profit:.0f}', ha='center', va='bottom', fontweight='bold')
        else:
            ax1.text(0.5, 0.5, 'Aucun produit sélectionné', ha='center', va='center', 
                    transform=ax1.transAxes, fontsize=12)
            ax1.set_title('Profits des Produits Sélectionnés', fontweight='bold')
        
        # Graphique 2: Utilisation de la capacité
        capacite_utilisee = result["capacite_utilisee"]
        capacite_restante = result["capacite_totale"] - capacite_utilisee
        
        sizes = [capacite_utilisee, capacite_restante]
        labels = [f'Utilisée\n{capacite_utilisee}h', f'Disponible\n{capacite_restante}h']
        colors = ['#FF6B6B', '#95E1D3']
        
        wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                          startangle=90, textprops={'fontweight': 'bold'})
        ax2.set_title(f'Utilisation de la Capacité\n({result["utilisation_capacite"]}% utilisée)', 
                     fontweight='bold')
        
        # Graphique 3: Comparaison profit unitaire vs temps requis
        tous_produits = result["produits_selectionnes"] + result["produits_non_selectionnes"]
        if tous_produits:
            profits_unitaires = [p["profit_unitaire"] for p in tous_produits]
            temps_requis = [p["temps_requis"] for p in tous_produits]
            noms_tous = [p["nom"] for p in tous_produits]
            
            # Couleurs différentes pour sélectionnés vs non sélectionnés
            colors = ['#2E8B57' if i < len(result["produits_selectionnes"]) else '#FF6B6B' 
                     for i in range(len(tous_produits))]
            
            scatter = ax3.scatter(temps_requis, profits_unitaires, c=colors, s=100, alpha=0.7)
            ax3.set_title('Profit Unitaire vs Temps Requis', fontweight='bold')
            ax3.set_xlabel('Temps Requis (heures)')
            ax3.set_ylabel('Profit Unitaire ($/unité)')
            ax3.grid(True, alpha=0.3)
            
            # Annotations
            for i, nom in enumerate(noms_tous):
                ax3.annotate(nom, (temps_requis[i], profits_unitaires[i]), 
                           xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        # Graphique 4: Métriques de performance
        metriques = ['Profit Total', 'Efficacité', 'Utilisation', 'Nb Produits']
        valeurs = [
            result["profit_maximal"] / 100,  # Normalisation pour affichage
            result["efficacite"],
            result["utilisation_capacite"],
            result["nombre_produits_selectionnes"] * 10  # Multiplication pour visibilité
        ]
        
        bars4 = ax4.bar(metriques, valeurs, color=['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'])
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
        ax.set_title('Erreur - Graphique FMS Sac à Dos')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return image_base64 