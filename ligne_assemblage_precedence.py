import networkx as nx
import matplotlib.pyplot as plt
import io
import base64
from typing import List, Dict, Optional, Union

def hierarchy_pos(G, root=None, width=1., vert_gap=0.2, vert_loc=0, xcenter=0.5):
    """Calcule les positions hiérarchiques pour les nœuds du graphe"""
    pos = _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter)
    return pos

def _hierarchy_pos(G, root, width=1., vert_gap=0.2, vert_loc=0, xcenter=0.5, pos=None, parent=None, parsed=[]):
    """Fonction récursive pour calculer les positions hiérarchiques"""
    if pos is None:
        pos = {root: (xcenter, vert_loc)}
    else:
        pos[root] = (xcenter, vert_loc)
    
    children = list(G.neighbors(root))
    if not isinstance(G, nx.DiGraph) and parent is not None:
        children.remove(parent)
    
    if len(children) != 0:
        dx = width / len(children)
        nextx = xcenter - width / 2 - dx / 2
        for child in children:
            nextx += dx
            pos = _hierarchy_pos(G, child, width=dx, vert_gap=vert_gap,
                                vert_loc=vert_loc - vert_gap, xcenter=nextx, pos=pos,
                                parent=root, parsed=parsed)
    return pos

def create_precedence_diagram(task_tuples: List[tuple], unite: str = "minutes") -> Dict:
    """
    Crée un diagramme de précédence et retourne les données d'analyse
    
    Args:
        task_tuples: Liste de tuples (tâche, prédécesseurs, durée)
        unite: Unité de temps
    
    Returns:
        Dict avec les métriques et le graphique encodé
    """
    G = nx.DiGraph()
    
    # Identifier les nœuds racines (sans prédécesseurs)
    root_nodes = [task[0] for task in task_tuples if not task[1]]
    root_node = root_nodes[0] if len(root_nodes) == 1 else 0

    node_labels = {}
    task_durations = {}
    
    # Construire le graphe
    for task in task_tuples:
        task_id, predecessors, duration = task
        G.add_node(task_id)
        node_labels[task_id] = f"{task_id}\n({duration} {unite})"
        task_durations[task_id] = duration
        
        if predecessors:
            # Si predecessors est un entier, le convertir en liste
            preds = [predecessors] if isinstance(predecessors, int) else predecessors
            for pred in preds:
                G.add_edge(pred, task_id)
        elif root_node == 0:
            G.add_edge(root_node, task_id)

    # Calculer les métriques
    metrics = calculate_metrics(G, task_durations, unite)
    
    # Générer le graphique
    image_base64 = generate_precedence_chart(G, node_labels, root_node)
    
    # Calculer le chemin critique et sa durée
    critical_path = find_critical_path(G, task_durations)
    critical_duration = sum(task_durations.get(task, 0) for task in critical_path)
    
    return {
        "graphique": image_base64,
        "metrics": metrics,
        "nombre_taches": len(task_tuples),
        "nombre_relations": G.number_of_edges(),
        "taches_critiques": critical_path,
        "unite": unite,
        # Champs attendus par le frontend
        "temps_total_minimal": critical_duration,
        "chemin_critique": critical_path,
        "niveau_parallelisme_max": 1,
        "taches_details": []
    }

def calculate_metrics(G: nx.DiGraph, task_durations: Dict, unite: str) -> Dict:
    """Calcule les métriques du diagramme de précédence"""
    try:
        # Chemin critique
        critical_path = find_critical_path(G, task_durations)
        critical_duration = sum(task_durations.get(task, 0) for task in critical_path)
        
        # Durée totale
        total_duration = sum(task_durations.values())
        
        # Nombre de niveaux
        levels = len(set(nx.shortest_path_length(G, source=0).values())) if 0 in G else 0
        
        return {
            "duree_critique": critical_duration,
            "duree_totale": total_duration,
            "nombre_niveaux": levels,
            "taux_parallelisme": round(total_duration / critical_duration, 2) if critical_duration > 0 else 0,
            "chemin_critique": " → ".join(map(str, critical_path))
        }
    except Exception as e:
        return {
            "duree_critique": 0,
            "duree_totale": sum(task_durations.values()),
            "nombre_niveaux": 0,
            "taux_parallelisme": 0,
            "chemin_critique": "Erreur de calcul"
        }

def find_critical_path(G: nx.DiGraph, task_durations: Dict) -> List:
    """Trouve le chemin critique dans le graphe"""
    try:
        # Utiliser l'algorithme de chemin le plus long
        longest_path = []
        max_duration = 0
        
        # Pour chaque nœud terminal, calculer le chemin le plus long depuis la racine
        terminal_nodes = [node for node in G.nodes() if G.out_degree(node) == 0]
        
        for terminal in terminal_nodes:
            try:
                # Trouver tous les chemins simples vers ce terminal
                for source in [node for node in G.nodes() if G.in_degree(node) == 0]:
                    try:
                        paths = list(nx.all_simple_paths(G, source, terminal))
                        for path in paths:
                            path_duration = sum(task_durations.get(node, 0) for node in path)
                            if path_duration > max_duration:
                                max_duration = path_duration
                                longest_path = path
                    except:
                        continue
            except:
                continue
                
        return longest_path[1:] if longest_path and longest_path[0] == 0 else longest_path
    except:
        return []

def generate_precedence_chart(G: nx.DiGraph, node_labels: Dict, root_node) -> str:
    """Génère le graphique de précédence et retourne l'image encodée en base64"""
    plt.figure(figsize=(12, 8))
    plt.clf()
    
    # Calculer les positions
    pos = hierarchy_pos(G, root_node)
    
    # Dessiner le graphe
    nx.draw(G, pos=pos, with_labels=True, arrows=True, 
            node_color='lightblue', node_size=1500, 
            font_size=10, font_weight='bold',
            edge_color='gray', arrowsize=20)
    
    # Ajouter les labels avec durées
    for node, (x, y) in pos.items():
        if node != 0 and node in node_labels:  # Ignorer le nœud racine factice
            plt.text(x, y, node_labels[node], horizontalalignment='center',
                    verticalalignment='center', fontsize=9, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    
    plt.title("Diagramme de Précédence des Tâches", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    
    # Convertir en base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64 