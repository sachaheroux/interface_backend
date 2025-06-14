import pandas as pd
import io
from typing import Dict, List, Tuple, Optional
from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

def parse_flowshop_excel(file_content: bytes) -> Dict:
    """
    Parse un fichier Excel pour les algorithmes flowshop (SPT, EDD, etc.)
    Supporte deux formats:
    1. Format avec onglets (ancien)
    2. Format matrice unique (nouveau - 12 colonnes x 11 lignes)
    
    Args:
        file_content: Contenu du fichier Excel en bytes
        
    Returns:
        Dict contenant les données formatées pour l'API
    """
    try:
        # Essayer d'abord le nouveau format (matrice unique)
        try:
            return parse_matrix_format(file_content)
        except:
            pass
        
        # Fallback vers l'ancien format avec onglets
        excel_file = pd.ExcelFile(io.BytesIO(file_content))
        
        # Vérifier que les onglets requis existent
        required_sheets = ['Machines', 'Jobs']
        missing_sheets = [sheet for sheet in required_sheets if sheet not in excel_file.sheet_names]
        
        if missing_sheets:
            raise HTTPException(
                status_code=400, 
                detail=f"Format Excel non reconnu. Utilisez le template fourni."
            )
        
        # Lire les onglets
        machines_df = pd.read_excel(excel_file, sheet_name='Machines')
        jobs_df = pd.read_excel(excel_file, sheet_name='Jobs')
        
        # Parser les machines
        machine_names, machine_mapping = parse_machines(machines_df)
        
        # Parser les jobs
        jobs_data, due_dates, job_names = parse_jobs(jobs_df, machine_names)
        
        return {
            "jobs_data": jobs_data,
            "due_dates": due_dates,
            "job_names": job_names,
            "machine_names": machine_names,
            "unite": "heures"  # Par défaut
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Erreur lors de la lecture du fichier Excel: {str(e)}")

def parse_matrix_format(file_content: bytes) -> Dict:
    """
    Parse le nouveau format matrice (12 colonnes x 11 lignes)
    Structure:
    - Cellule C5: "Job" (coin haut gauche du tableau)
    - Colonne C (lignes 6-15): noms des jobs
    - Colonnes D-M: durées sur les machines (10 machines max)
    - Colonne N: dates dues
    - Cellule C20: unité de temps (j/h/m)
    
    Args:
        file_content: Contenu du fichier Excel en bytes
        
    Returns:
        Dict contenant les données formatées pour l'API
    """
    try:
        # Lire le fichier Excel sans en-tête automatique
        excel_file = io.BytesIO(file_content)
        df = pd.read_excel(excel_file, header=None)
        
        # Vérifier la structure minimale
        if df.shape[0] < 20 or df.shape[1] < 14:
            raise ValueError("Structure de fichier incorrecte")
        
        # Vérifier que c'est bien le bon format (cellule C5 doit contenir "Job")
        job_header = df.iloc[4, 2]  # C5 (ligne 5, colonne C)
        if pd.isna(job_header) or str(job_header).strip().lower() != "job":
            raise ValueError("Format non reconnu - cellule C5 doit contenir 'Job'")
        
        # Extraire l'unité de temps (cellule C20)
        unite = "heures"  # valeur par défaut
        try:
            unite_cell = df.iloc[19, 2]  # C20
            if pd.notna(unite_cell):
                unite_str = str(unite_cell).lower().strip()
                if unite_str == 'j':
                    unite = "jours"
                elif unite_str == 'h':
                    unite = "heures"
                elif unite_str == 'm':
                    unite = "minutes"
        except:
            pass
        
        # Extraire les données des jobs
        job_names = []
        jobs_data = []
        due_dates = []
        
        # Parcourir les lignes 6-15 (index 5-14)
        for i in range(5, 15):
            try:
                # Nom du job (colonne C)
                job_name = df.iloc[i, 2]
                if pd.isna(job_name) or not str(job_name).strip():
                    continue
                
                job_name = str(job_name).strip()
                job_names.append(job_name)
                
                # Durées sur les machines (colonnes D-M, index 3-12)
                job_durations = []
                for j in range(3, 13):  # colonnes D à M
                    duration = df.iloc[i, j]
                    if pd.notna(duration) and str(duration).strip():
                        try:
                            duration_val = float(duration)
                            if duration_val > 0:  # Ignorer les durées nulles ou négatives
                                job_durations.append([j-3, duration_val])  # [machine_id, duration]
                        except:
                            pass
                
                # Date due (colonne N, index 13)
                due_date = df.iloc[i, 13]
                try:
                    due_date_val = float(due_date) if pd.notna(due_date) else 10.0
                except:
                    due_date_val = 10.0
                
                # Ajouter seulement si le job a au moins une durée
                if job_durations:
                    jobs_data.append(job_durations)
                    due_dates.append(due_date_val)
                else:
                    job_names.pop()  # Retirer le nom si pas de durées
                    
            except Exception as e:
                continue
        
        if not job_names:
            raise HTTPException(
                status_code=400,
                detail="Aucun job valide trouvé. Vérifiez que vous avez rempli les noms de jobs et au moins une durée par job."
            )
        
        # Lire les noms des machines depuis les en-têtes (ligne 5, colonnes D-M)
        machine_names = []
        for j in range(3, 13):  # colonnes D à M (index 3-12)
            try:
                header = df.iloc[4, j]  # ligne 5 (index 4)
                if pd.notna(header) and str(header).strip():
                    machine_names.append(str(header).strip())
                else:
                    machine_names.append(f"Machine_{j-3}")
            except:
                machine_names.append(f"Machine_{j-3}")
        
        # Déterminer le nombre de machines réellement utilisées
        max_machine_id = 0
        for job in jobs_data:
            for machine_id, _ in job:
                max_machine_id = max(max_machine_id, machine_id)
        
        # Garder seulement les noms des machines utilisées
        machine_names = machine_names[:max_machine_id + 1]
        
        return {
            "jobs_data": jobs_data,
            "due_dates": due_dates,
            "job_names": job_names,
            "machine_names": machine_names,
            "unite": unite
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise ValueError(f"Erreur parsing format matrice: {str(e)}")

def parse_machines(machines_df: pd.DataFrame) -> Tuple[List[str], Dict[int, str]]:
    """
    Parse l'onglet Machines
    
    Returns:
        Tuple[List[str], Dict[int, str]]: (noms des machines, mapping ID->nom)
    """
    # Vérifier les colonnes requises
    required_columns = ['ID_Machine', 'Nom_Machine']
    missing_columns = [col for col in required_columns if col not in machines_df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes manquantes dans l'onglet Machines: {', '.join(missing_columns)}"
        )
    
    # Nettoyer les données
    machines_df = machines_df.dropna(subset=['ID_Machine', 'Nom_Machine'])
    
    if machines_df.empty:
        raise HTTPException(status_code=400, detail="Aucune machine valide trouvée dans l'onglet Machines")
    
    # Vérifier que les ID sont des entiers consécutifs commençant à 0
    machine_ids = sorted(machines_df['ID_Machine'].astype(int).tolist())
    expected_ids = list(range(len(machine_ids)))
    
    if machine_ids != expected_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Les ID des machines doivent être des entiers consécutifs commençant à 0. Trouvé: {machine_ids}, Attendu: {expected_ids}"
        )
    
    # Créer le mapping et la liste des noms
    machine_mapping = {}
    machine_names = [''] * len(machine_ids)
    
    for _, row in machines_df.iterrows():
        machine_id = int(row['ID_Machine'])
        machine_name = str(row['Nom_Machine']).strip()
        
        if not machine_name or machine_name.lower() in ['nan', 'none', '[à remplir]']:
            raise HTTPException(
                status_code=400,
                detail=f"Nom de machine manquant pour l'ID {machine_id}"
            )
        
        machine_mapping[machine_id] = machine_name
        machine_names[machine_id] = machine_name
    
    return machine_names, machine_mapping

def parse_jobs(jobs_df: pd.DataFrame, machine_names: List[str]) -> Tuple[List[List[List[float]]], List[float], List[str]]:
    """
    Parse l'onglet Jobs
    
    Returns:
        Tuple: (jobs_data, due_dates, job_names)
    """
    # Vérifier les colonnes de base
    base_columns = ['Nom_Job', 'Date_Echeance']
    missing_base = [col for col in base_columns if col not in jobs_df.columns]
    
    if missing_base:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes manquantes dans l'onglet Jobs: {', '.join(missing_base)}"
        )
    
    # Vérifier les colonnes des machines (Machine_0, Machine_1, etc.)
    machine_columns = [f'Machine_{i}' for i in range(len(machine_names))]
    missing_machines = [col for col in machine_columns if col not in jobs_df.columns]
    
    if missing_machines:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes de machines manquantes dans l'onglet Jobs: {', '.join(missing_machines)}"
        )
    
    # Nettoyer les données
    jobs_df = jobs_df.dropna(subset=['Nom_Job', 'Date_Echeance'])
    
    if jobs_df.empty:
        raise HTTPException(status_code=400, detail="Aucun job valide trouvé dans l'onglet Jobs")
    
    jobs_data = []
    due_dates = []
    job_names = []
    
    for index, row in jobs_df.iterrows():
        # Nom du job
        job_name = str(row['Nom_Job']).strip()
        if not job_name or job_name.lower() in ['nan', 'none', '[à remplir]']:
            raise HTTPException(
                status_code=400,
                detail=f"Nom de job manquant à la ligne {index + 2}"
            )
        
        # Date d'échéance
        try:
            due_date = float(row['Date_Echeance'])
            if due_date < 0:
                raise ValueError("Date d'échéance négative")
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Date d'échéance invalide pour le job '{job_name}' à la ligne {index + 2}"
            )
        
        # Durées des tâches
        job_tasks = []
        for machine_id, machine_name in enumerate(machine_names):
            machine_col = f'Machine_{machine_id}'
            
            try:
                duration = float(row[machine_col])
                if duration < 0:
                    raise ValueError("Durée négative")
                
                # Format: [machine_id, duration]
                job_tasks.append([machine_id, duration])
                
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Durée invalide pour le job '{job_name}' sur la machine '{machine_name}' à la ligne {index + 2}"
                )
        
        jobs_data.append(job_tasks)
        due_dates.append(due_date)
        job_names.append(job_name)
    
    return jobs_data, due_dates, job_names

def create_flowshop_template(template_type: str = "exemple") -> bytes:
    """
    Crée un template Excel pour les algorithmes flowshop
    
    Args:
        template_type: "exemple" ou "vide"
        
    Returns:
        bytes: Contenu du fichier Excel
    """
    # Créer un BytesIO pour le fichier Excel
    output = io.BytesIO()
    
    # Préparer les données
    if template_type == "exemple":
        machines_data = {
            'ID_Machine': [0, 1, 2],
            'Nom_Machine': ['Découpe', 'Assemblage', 'Finition']
        }
        jobs_data = {
            'Nom_Job': ['Job_A', 'Job_B', 'Job_C'],
            'Date_Echeance': [12, 15, 18],
            'Machine_0': [4, 3, 5],
            'Machine_1': [2, 4, 2],
            'Machine_2': [3, 2, 4]
        }
    else:
        machines_data = {
            'ID_Machine': [0, 1, 2],
            'Nom_Machine': ['[À remplir]', '[À remplir]', '[À remplir]']
        }
        jobs_data = {
            'Nom_Job': ['[À remplir]', '[À remplir]', '[À remplir]'],
            'Date_Echeance': ['[À remplir]', '[À remplir]', '[À remplir]'],
            'Machine_0': ['[À remplir]', '[À remplir]', '[À remplir]'],
            'Machine_1': ['[À remplir]', '[À remplir]', '[À remplir]'],
            'Machine_2': ['[À remplir]', '[À remplir]', '[À remplir]']
        }
    
    # Instructions
    instructions_data = {
        'Section': [
            'INSTRUCTIONS GÉNÉRALES',
            '',
            '1. Structure du fichier',
            '',
            '2. Onglet Machines',
            '',
            '3. Onglet Jobs',
            '',
            '4. Règles importantes',
            '',
            '5. Exemple de données',
            ''
        ],
        'Description': [
            'Template pour import de données Flowshop (SPT, EDD, etc.)',
            '',
            '- Onglet "Machines": Définit les machines et leurs noms',
            '- Onglet "Jobs": Définit les jobs avec leurs durées sur chaque machine',
            '',
            '- ID_Machine: Numéro de la machine (0, 1, 2, ...)',
            '- Nom_Machine: Nom personnalisé de votre machine',
            '',
            '- Nom_Job: Nom de votre job/produit',
            '- Date_Echeance: Date limite en heures',
            '- Machine_X: Durée du job sur la machine X',
            '',
            '- Les ID machines doivent commencer à 0 et être consécutifs',
            '- Toutes les durées doivent être positives',
            '- Aucune cellule ne doit être vide dans les colonnes obligatoires',
            '',
            'Job_A: 4h sur Découpe, 2h sur Assemblage, 3h sur Finition',
            'Date d\'échéance: 12 heures'
        ]
    }
    
    # Créer les DataFrames
    machines_df = pd.DataFrame(machines_data)
    jobs_df = pd.DataFrame(jobs_data)
    instructions_df = pd.DataFrame(instructions_data)
    
    # Écrire dans le fichier Excel avec pandas
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        machines_df.to_excel(writer, sheet_name='Machines', index=False)
        jobs_df.to_excel(writer, sheet_name='Jobs', index=False)
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
    
    output.seek(0)
    return output.getvalue()

 