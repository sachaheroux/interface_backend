import fms_sac_a_dos

# Test direct de l'algorithme
data = {
    "vente_unite": [200, 155],
    "cout_mp_unite": [45, 35],
    "demande_periode": [100, 50],
    "temps_fabrication_unite": [1, 2],
    "cout_op": 50,
    "capacite_max": 250,
    "noms_produits": ["Produit 1", "Produit 2"],
    "unite": "heures"
}

try:
    print("Creating request object...")
    request = fms_sac_a_dos.FMSSacADosRequest(**data)
    print("Request created successfully")
    
    print("Running algorithm...")
    result = fms_sac_a_dos.solve_fms_sac_a_dos(request)
    print("Algorithm completed successfully")
    
    print(f"Status: {result['status']}")
    print(f"Profit: {result.get('profit_maximal', 'N/A')}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc() 