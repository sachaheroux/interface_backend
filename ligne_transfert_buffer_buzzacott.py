import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
import io
import base64

def buffer_buzzacott_algorithm(alpha1, alpha2, b_inv_1, b_inv_2, buffer_size, production, jours_annee, profit_unitaire):
    """
    Algorithme Buffer Buzzacott pour l'analyse d'efficacité de ligne de transfert
    
    Paramètres:
    - alpha1, alpha2: Taux de panne des stations 1 et 2
    - b_inv_1, b_inv_2: Nombre de cycles avant de réparer les stations 1 et 2
    - buffer_size: Quantité de buffer (Z)
    - production: Production en pièces/jour
    - jours_annee: Nombre de jours travaillés par année
    - profit_unitaire: Profit unitaire par pièce
    """
    
    # Calculs intermédiaires
    b_1 = 1 / b_inv_1
    b_2 = 1 / b_inv_2
    x1 = alpha1 * b_inv_1
    x2 = alpha2 * b_inv_2
    s = x2 / x1
    r = alpha2 / alpha1
    C = ((alpha1 + alpha2) * (b_1 + b_2) - alpha1 * b_2 * (alpha1 + alpha2 + b_1 + b_2)) / ((alpha1 + alpha2) * (b_1 + b_2) - alpha2 * b_1 * (alpha1 + alpha2 + b_1 + b_2))

    # Calcul de l'efficacité E(Z)
    if abs(s - 1) > 1e-10:  # s != 1 avec tolérance numérique
        E_Z = (1 - s * C**buffer_size) / (1 + x1 - (1 + x2) * s * C**buffer_size)
    else:
        E_Z = (1 + r - b_2 * (1 + x1) + buffer_size * b_2 * (1 + x1)) / ((1 + 2 * x1) * (1 + r - b_2 * (1 + x1)) + buffer_size * b_2 * ((1 + x1)**2))

    # Calcul de l'efficacité E(0)
    if abs(s - 1) > 1e-10:  # s != 1 avec tolérance numérique
        E_0 = (1 - s) / (1 + x1 - (1 + x2) * s)
    else:
        E_0 = (1 + r - b_2 * (1 + x1)) / ((1 + 2 * x1) * (1 + r - b_2 * (1 + x1)))

    # Calculs de production
    production_sans_buffer = production  # Production de référence (avec E_0)
    production_avec_buffer = E_Z * production / E_0
    gain_journalier = production_avec_buffer - production_sans_buffer
    
    # Calculs annuels
    capacite_annuelle_avec_buffer = production_avec_buffer * jours_annee
    capacite_annuelle_sans_buffer = production_sans_buffer * jours_annee
    gain_annuel = capacite_annuelle_avec_buffer - capacite_annuelle_sans_buffer
    profit_annuel_supplementaire = gain_annuel * profit_unitaire

    # Résultats
    results = {
        "status": "Optimal",
        "alpha1": float(alpha1),
        "alpha2": float(alpha2),
        "b_inv_1": float(b_inv_1),
        "b_inv_2": float(b_inv_2),
        "buffer_size": int(buffer_size),
        "x1": float(x1),
        "x2": float(x2),
        "s": float(s),
        "r": float(r),
        "C": float(C),
        "E_0": float(E_0),
        "E_Z": float(E_Z),
        "production_sans_buffer": float(production_sans_buffer),
        "production_avec_buffer": float(production_avec_buffer),
        "gain_journalier": float(gain_journalier),
        "capacite_annuelle_sans_buffer": float(capacite_annuelle_sans_buffer),
        "capacite_annuelle_avec_buffer": float(capacite_annuelle_avec_buffer),
        "gain_annuel": float(gain_annuel),
        "profit_annuel_supplementaire": float(profit_annuel_supplementaire),
        "jours_annee": int(jours_annee),
        "profit_unitaire": float(profit_unitaire),
        "devise": "€"
    }

    return results

def generate_buffer_buzzacott_chart(results):
    """
    Génère des graphiques pour visualiser l'analyse Buffer Buzzacott
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    
    # Couleurs pour ligne de transfert (tons rouges)
    colors = ['#dc2626', '#ef4444', '#f87171', '#fca5a5', '#fecaca', '#fee2e2']
    
    # Graphique 1: Comparaison des efficacités
    efficacites = [results["E_0"], results["E_Z"]]
    labels_eff = ['Sans buffer\nE(0)', f'Avec buffer\nE({results["buffer_size"]})']
    
    bars1 = ax1.bar(labels_eff, efficacites, color=[colors[0], colors[1]], alpha=0.8)
    ax1.set_ylabel('Efficacité')
    ax1.set_title('Comparaison des Efficacités')
    ax1.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres
    for bar, eff in zip(bars1, efficacites):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.001,
                f'{eff:.6f}', ha='center', va='bottom', fontsize=10)
    
    # Graphique 2: Production journalière
    productions = [results["production_sans_buffer"], results["production_avec_buffer"]]
    labels_prod = ['Sans buffer', 'Avec buffer']
    
    bars2 = ax2.bar(labels_prod, productions, color=[colors[0], colors[1]], alpha=0.8)
    ax2.set_ylabel('Production (pièces/jour)')
    ax2.set_title('Impact sur la Production Journalière')
    ax2.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres
    for bar, prod in zip(bars2, productions):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{prod:.1f}', ha='center', va='bottom', fontsize=10)
    
    # Graphique 3: Gains annuels
    gains_data = [results["gain_annuel"]]
    profit_data = [results["profit_annuel_supplementaire"]]
    
    x_pos = [0]
    width = 0.35
    
    bars3a = ax3.bar([p - width/2 for p in x_pos], gains_data, width, 
                     label='Gain en pièces', color=colors[2], alpha=0.8)
    ax3_twin = ax3.twinx()
    bars3b = ax3_twin.bar([p + width/2 for p in x_pos], profit_data, width,
                          label='Profit supplémentaire', color=colors[3], alpha=0.8)
    
    ax3.set_ylabel('Gain en pièces/an', color=colors[2])
    ax3_twin.set_ylabel(f'Profit ({results["devise"]}/an)', color=colors[3])
    ax3.set_title('Retour sur Investissement Annuel')
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(['Buffer Buzzacott'])
    
    # Ajouter les valeurs
    for bar, gain in zip(bars3a, gains_data):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + gain*0.01,
                f'{gain:.0f}', ha='center', va='bottom', fontsize=10)
    
    for bar, profit in zip(bars3b, profit_data):
        height = bar.get_height()
        ax3_twin.text(bar.get_x() + bar.get_width()/2., height + profit*0.01,
                      f'{profit:.0f} {results["devise"]}', ha='center', va='bottom', fontsize=10)
    
    # Graphique 4: Paramètres calculés (radar/bar chart)
    params = ['x₁', 'x₂', 's', 'r']
    values = [results["x1"], results["x2"], results["s"], results["r"]]
    
    bars4 = ax4.bar(params, values, color=colors[:4], alpha=0.8)
    ax4.set_ylabel('Valeur')
    ax4.set_title('Paramètres Calculés du Modèle')
    ax4.grid(True, alpha=0.3)
    
    # Ajouter les valeurs sur les barres
    for bar, val in zip(bars4, values):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                f'{val:.4f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    
    # Conversion en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    
    return image_base64

def solve_buffer_buzzacott(data):
    """
    Interface principale pour résoudre le problème Buffer Buzzacott
    """
    alpha1 = data["alpha1"]
    alpha2 = data["alpha2"]
    b_inv_1 = data["b_inv_1"]
    b_inv_2 = data["b_inv_2"]
    buffer_size = data["buffer_size"]
    production = data["production"]
    jours_annee = data["jours_annee"]
    profit_unitaire = data["profit_unitaire"]
    
    results = buffer_buzzacott_algorithm(
        alpha1, alpha2, b_inv_1, b_inv_2, 
        buffer_size, production, jours_annee, profit_unitaire
    )
    
    return results 