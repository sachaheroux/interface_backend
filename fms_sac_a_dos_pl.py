import numpy as np
from pulp import LpMaximize, LpProblem, LpStatus, lpSum, LpVariable
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import base64

def fms_sac_a_dos_pl(vente_unite, cout_mp_unite, demande_periode, temps_fabrication_unite, cout_op, capacite_max, noms_produits, unite):
    """
    Résout le problème du sac à dos FMS avec programmation linéaire (PuLP)
    
    Args:
        vente_unite: Prix de vente par unité pour chaque produit
        cout_mp_unite: Coût matière première par unité pour chaque produit  
        demande_periode: Demande par période pour chaque produit
        temps_fabrication_unite: Temps de fabrication par unité pour chaque produit
        cout_op: Coût d'opération par heure
        capacite_max: Capacité maximale en heures
        noms_produits: Noms des produits
        unite: Unité de temps
    
    Returns:
        dict: Résultats de l'optimisation
    """
    
    # Conversion en arrays numpy
    vente_unite = np.array(vente_unite)
    cout_mp_unite = np.array(cout_mp_unite)
    demande_periode = np.array(demande_periode)
    temps_fabrication_unite = np.array(temps_fabrication_unite)
    
    n_produits = len(vente_unite)
    
    # Calcul des profits totaux par produit (si sélectionné)
    profits_unitaires = vente_unite - (cout_op * temps_fabrication_unite + cout_mp_unite)
    profits_totaux = profits_unitaires * demande_periode
    
    # Calcul des temps requis totaux par produit
    temps_requis_totaux = temps_fabrication_unite * demande_periode
    
    # Création du problème de programmation linéaire
    model = LpProblem(name="fms-sac-a-dos-pl", sense=LpMaximize)
    
    # Création des variables binaires (x[i] = 1 si produit i sélectionné, 0 sinon)
    x = {i: LpVariable(name=f"x{i}", lowBound=0, upBound=1, cat='Binary') for i in range(n_produits)}
    
    # Fonction objectif : maximiser le profit total
    model += lpSum(profits_totaux[i] * x[i] for i in range(n_produits))
    
    # Contrainte de capacité : temps total ≤ capacité maximale
    model += lpSum(temps_requis_totaux[i] * x[i] for i in range(n_produits)) <= capacite_max
    
    # Résolution du problème
    model.solve()
    
    # Extraction des résultats
    status = LpStatus[model.status]
    profit_maximal = float(model.objective.value()) if model.objective.value() else 0.0
    
    # Identification des produits sélectionnés
    produits_selectionnes_indices = [i for i in range(n_produits) if x[i].value() and x[i].value() > 0.5]
    produits_non_selectionnes_indices = [i for i in range(n_produits) if not x[i].value() or x[i].value() < 0.5]
    
    # Calcul de la capacité utilisée
    capacite_utilisee = sum(float(temps_requis_totaux[i]) for i in produits_selectionnes_indices)
    utilisation_capacite = round((capacite_utilisee / capacite_max) * 100, 1)
    
    # Calcul de l'efficacité (profit par unité de capacité utilisée)
    efficacite = round((profit_maximal / (capacite_utilisee * cout_op)) * 100, 1) if capacite_utilisee > 0 else 0.0
    
    # Détails des produits sélectionnés
    produits_selectionnes = []
    for i in produits_selectionnes_indices:
        produits_selectionnes.append({
            'nom': noms_produits[i],
            'profit_unitaire': round(float(profits_unitaires[i]), 2),
            'profit_total': round(float(profits_totaux[i]), 2),
            'temps_requis': round(float(temps_requis_totaux[i]), 1),
            'demande': int(demande_periode[i]),
            'prix_vente': round(float(vente_unite[i]), 2),
            'cout_mp': round(float(cout_mp_unite[i]), 2),
            'temps_fabrication': round(float(temps_fabrication_unite[i]), 2)
        })
    
    # Détails des produits non sélectionnés
    produits_non_selectionnes = []
    for i in produits_non_selectionnes_indices:
        raison = "Profit négatif" if profits_unitaires[i] < 0 else "Capacité insuffisante"
        produits_non_selectionnes.append({
            'nom': noms_produits[i],
            'profit_unitaire': round(float(profits_unitaires[i]), 2),
            'raison_exclusion': raison
        })
    
    return {
        'status': status,
        'profit_maximal': round(profit_maximal, 2),
        'capacite_utilisee': int(capacite_utilisee),
        'capacite_totale': int(capacite_max),
        'utilisation_capacite': utilisation_capacite,
        'efficacite': efficacite,
        'nombre_produits_selectionnes': len(produits_selectionnes_indices),
        'produits_selectionnes': produits_selectionnes,
        'produits_non_selectionnes': produits_non_selectionnes,
        'unite': unite,
        'methode': 'Programmation Linéaire (PuLP)'
    }

def generate_fms_sac_a_dos_pl_chart(vente_unite, cout_mp_unite, demande_periode, temps_fabrication_unite, cout_op, capacite_max, noms_produits, unite):
    """
    Génère les graphiques pour l'analyse FMS Sac à Dos PL
    """
    
    # Résoudre le problème pour obtenir les données
    result = fms_sac_a_dos_pl(vente_unite, cout_mp_unite, demande_periode, temps_fabrication_unite, cout_op, capacite_max, noms_produits, unite)
    
    # Configuration matplotlib
    plt.style.use('default')
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Analyse FMS - Sac à Dos (Programmation Linéaire)', fontsize=16, fontweight='bold')
    
    # Calcul des données
    profits_unitaires = np.array(vente_unite) - (cout_op * np.array(temps_fabrication_unite) + np.array(cout_mp_unite))
    temps_requis = np.array(temps_fabrication_unite) * np.array(demande_periode)
    profits_totaux = profits_unitaires * np.array(demande_periode)
    
    # Identification des produits sélectionnés
    produits_selectionnes = [p['nom'] for p in result['produits_selectionnes']]
    colors = ['#10b981' if nom in produits_selectionnes else '#ef4444' for nom in noms_produits]
    
    # Graphique 1: Profits par produit
    ax1.bar(range(len(noms_produits)), profits_totaux, color=colors, alpha=0.7)
    ax1.set_title('Profits Totaux par Produit', fontweight='bold')
    ax1.set_xlabel('Produits')
    ax1.set_ylabel('Profit Total ($)')
    ax1.set_xticks(range(len(noms_produits)))
    ax1.set_xticklabels([f'P{i+1}' for i in range(len(noms_produits))], rotation=45)
    ax1.grid(True, alpha=0.3)
    
    # Légende pour les couleurs
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='#10b981', label='Sélectionné'),
                      Patch(facecolor='#ef4444', label='Non sélectionné')]
    ax1.legend(handles=legend_elements, loc='upper right')
    
    # Graphique 2: Utilisation de la capacité
    capacite_utilisee = result['capacite_utilisee']
    capacite_libre = capacite_max - capacite_utilisee
    
    sizes = [capacite_utilisee, capacite_libre]
    labels = [f'Utilisée\n{capacite_utilisee} {unite}', f'Libre\n{capacite_libre} {unite}']
    colors_pie = ['#3b82f6', '#e5e7eb']
    
    wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.1f%%', startangle=90)
    ax2.set_title(f'Utilisation de la Capacité\n({result["utilisation_capacite"]}%)', fontweight='bold')
    
    # Graphique 3: Analyse Profit vs Temps
    ax3.scatter(temps_requis, profits_totaux, c=colors, s=100, alpha=0.7)
    ax3.set_title('Analyse Profit vs Temps Requis', fontweight='bold')
    ax3.set_xlabel(f'Temps Requis Total ({unite})')
    ax3.set_ylabel('Profit Total ($)')
    ax3.grid(True, alpha=0.3)
    
    # Annotations pour les points
    for i, (x, y) in enumerate(zip(temps_requis, profits_totaux)):
        ax3.annotate(f'P{i+1}', (x, y), xytext=(5, 5), textcoords='offset points', fontsize=8)
    
    # Graphique 4: Métriques de performance
    ax4.axis('off')
    
    # Tableau des métriques
    metrics_data = [
        ['Méthode', 'Programmation Linéaire'],
        ['Statut', result['status']],
        ['Profit Maximal', f"${result['profit_maximal']}"],
        ['Capacité Utilisée', f"{result['capacite_utilisee']}/{result['capacite_totale']} {unite}"],
        ['Utilisation', f"{result['utilisation_capacite']}%"],
        ['Efficacité', f"{result['efficacite']}%"],
        ['Produits Sélectionnés', str(result['nombre_produits_selectionnes'])],
        ['Solveur', 'PuLP (CBC)']
    ]
    
    table = ax4.table(cellText=metrics_data,
                      colLabels=['Métrique', 'Valeur'],
                      cellLoc='left',
                      loc='center',
                      colWidths=[0.4, 0.6])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style du tableau
    for i in range(len(metrics_data) + 1):
        for j in range(2):
            if i == 0:  # En-tête
                table[(i, j)].set_facecolor('#8b5cf6')
                table[(i, j)].set_text_props(weight='bold', color='white')
            else:
                table[(i, j)].set_facecolor('#f8fafc' if i % 2 == 0 else 'white')
    
    ax4.set_title('Métriques de Performance', fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    # Sauvegarde en buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    return buffer 