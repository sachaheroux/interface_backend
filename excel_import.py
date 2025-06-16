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
        errors = []
        
        # Parcourir les lignes 6-15 (index 5-14)
        for i in range(5, 15):
            row_num = i + 1  # Numéro de ligne Excel (1-indexé)
            
            # Nom du job (colonne C)
            job_name = df.iloc[i, 2]
            if pd.isna(job_name) or not str(job_name).strip():
                continue  # Ligne vide, on passe
            
            job_name = str(job_name).strip()
            
            # Vérifier les durées sur les machines (colonnes D-M, index 3-12)
            job_durations = []
            duration_errors = []
            
            for j in range(3, 13):  # colonnes D à M
                col_letter = chr(68 + j - 3)  # D, E, F, G, H, I, J, K, L, M
                duration = df.iloc[i, j]
                
                if pd.notna(duration) and str(duration).strip():
                    try:
                        duration_val = float(duration)
                        if duration_val < 0:
                            duration_errors.append(f"Durée négative en {col_letter}{row_num}: {duration}")
                        elif duration_val == 0:
                            # Durée nulle acceptée mais pas ajoutée
                            pass
                        else:
                            job_durations.append([j-3, duration_val])  # [machine_id, duration]
                    except (ValueError, TypeError):
                        duration_errors.append(f"Valeur invalide en {col_letter}{row_num}: '{duration}' (doit être un nombre)")
            
            # Vérifier la date due (colonne N, index 13)
            due_date = df.iloc[i, 13]
            due_date_val = 10.0  # valeur par défaut
            
            if pd.notna(due_date) and str(due_date).strip():
                try:
                    due_date_val = float(due_date)
                    if due_date_val < 0:
                        errors.append(f"Date due négative pour '{job_name}' en N{row_num}: {due_date}")
                        due_date_val = 10.0
                except (ValueError, TypeError):
                    errors.append(f"Date due invalide pour '{job_name}' en N{row_num}: '{due_date}' (doit être un nombre)")
                    due_date_val = 10.0
            
            # Ajouter les erreurs de durée si il y en a
            if duration_errors:
                errors.extend([f"Job '{job_name}': {err}" for err in duration_errors])
            
            # Ajouter le job seulement s'il a au moins une durée valide
            if job_durations:
                job_names.append(job_name)
                jobs_data.append(job_durations)
                due_dates.append(due_date_val)
            elif not duration_errors:  # Pas d'erreurs mais pas de durées non plus
                errors.append(f"Job '{job_name}' (ligne {row_num}): aucune durée valide trouvée")
        
        # Si il y a des erreurs, les signaler
        if errors:
            error_msg = "Erreurs dans le fichier Excel:\n" + "\n".join(f"• {err}" for err in errors[:10])
            if len(errors) > 10:
                error_msg += f"\n... et {len(errors) - 10} autres erreurs"
            raise HTTPException(status_code=400, detail=error_msg)
        
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

def export_manual_data_to_excel(
    jobs_data: List[List[float]], 
    due_dates: List[float], 
    job_names: List[str], 
    machine_names: List[str],
    unite: str = "heures"
) -> bytes:
    """
    Exporte les données saisies manuellement vers un fichier Excel au format matriciel FIXE 12x12
    Structure exacte du template (TOUJOURS 12 colonnes et 12 lignes) :
    - C5: "JOB"
    - C6-C16: Noms des jobs (max 11 jobs)
    - D5-M5: Noms des machines (max 10 machines) 
    - N5: "Due Date" (TOUJOURS colonne N = 14)
    - N6-N16: Dates d'échéance 
    - D6-M16: Matrice des temps de traitement
    
    Args:
        jobs_data: Données des jobs [[durée_machine_0, durée_machine_1, ...], ...]
        due_dates: Dates d'échéance des jobs
        job_names: Noms des jobs
        machine_names: Noms des machines
        unite: Unité de temps
        
    Returns:
        bytes: Contenu du fichier Excel
    """
    # Validation des données d'entrée
    if not jobs_data or not due_dates or not job_names or not machine_names:
        raise ValueError("Toutes les données (jobs_data, due_dates, job_names, machine_names) sont requises")
    
    # Vérifier que toutes les listes ont la même longueur
    num_jobs = len(job_names)
    if len(jobs_data) != num_jobs:
        raise ValueError(f"Le nombre de jobs dans jobs_data ({len(jobs_data)}) ne correspond pas au nombre de noms de jobs ({num_jobs})")
    
    if len(due_dates) != num_jobs:
        raise ValueError(f"Le nombre de dates d'échéance ({len(due_dates)}) ne correspond pas au nombre de jobs ({num_jobs})")
    
    # Debug : afficher les données reçues
    print(f"DEBUG - jobs_data: {jobs_data}")
    print(f"DEBUG - due_dates: {due_dates}")
    print(f"DEBUG - job_names: {job_names}")
    print(f"DEBUG - machine_names: {machine_names}")
    
    # Normaliser les données des jobs pour s'assurer qu'elles ont toutes la bonne longueur
    normalized_jobs_data = []
    for job_idx, job in enumerate(jobs_data):
        try:
            if isinstance(job, list):
                # Étendre ou tronquer le job pour qu'il ait exactement le nombre de machines
                normalized_job = []
                for i in range(len(machine_names)):
                    if i < len(job):
                        duration = float(job[i]) if job[i] is not None else 0.0
                    else:
                        duration = 0.0
                    normalized_job.append(duration)
                normalized_jobs_data.append(normalized_job)
                print(f"DEBUG - Job {job_idx} ({job_names[job_idx]}): {job} -> {normalized_job}")
            else:
                # Si ce n'est pas une liste, créer une liste de zéros
                normalized_jobs_data.append([0.0] * len(machine_names))
                print(f"DEBUG - Job {job_idx} ({job_names[job_idx]}): Not a list, created zeros")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Erreur dans les données du job '{job_names[job_idx]}': {str(e)}")
    
    # Créer un BytesIO pour le fichier Excel
    output = io.BytesIO()
    
    # Créer un workbook avec openpyxl pour un contrôle précis de la structure
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Données"
    
    # Style pour les en-têtes
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # STRUCTURE FIXE 12x12 - TOUJOURS utiliser ces positions exactes
    
    # C5: "JOB" (coin supérieur gauche)
    ws['C5'] = "JOB"
    ws['C5'].font = header_font
    ws['C5'].fill = header_fill
    ws['C5'].alignment = Alignment(horizontal="center")
    ws['C5'].border = border
    
    # C6-C16: Noms des jobs (colonne C = 3, lignes 6 à 16 = max 11 jobs)
    for i in range(11):  # TOUJOURS 11 lignes (C6 à C16)
        if i < len(job_names):
            job_name = job_names[i]
        else:
            job_name = ""  # Cellule vide si pas assez de jobs
        
        cell = ws.cell(row=6+i, column=3, value=job_name)  # Colonne C = 3
        cell.border = border
    
    # D5-M5: Noms des machines (ligne 5, colonnes D=4 à M=13 = max 10 machines)
    for i in range(10):  # TOUJOURS 10 colonnes (D à M)
        if i < len(machine_names):
            machine_name = machine_names[i]
        else:
            machine_name = ""  # Cellule vide si pas assez de machines
            
        cell = ws.cell(row=5, column=4+i, value=machine_name)  # Colonnes D=4 à M=13
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = border
    
    # N5: "Due Date" (TOUJOURS colonne N = 14)
    ws.cell(row=5, column=14, value="Due Date")  # Colonne N = 14
    ws.cell(row=5, column=14).font = header_font
    ws.cell(row=5, column=14).fill = header_fill
    ws.cell(row=5, column=14).alignment = Alignment(horizontal="center")
    ws.cell(row=5, column=14).border = border
    
    # N6-N16: Dates d'échéance (colonne N=14, lignes 6 à 16)
    for i in range(11):  # TOUJOURS 11 lignes (N6 à N16)
        if i < len(due_dates):
            due_date = due_dates[i]
        else:
            due_date = ""  # Cellule vide si pas assez de dates
            
        cell = ws.cell(row=6+i, column=14, value=due_date)  # Colonne N = 14
        cell.border = border
    
    # D6-M16: Matrice des temps de traitement (colonnes D=4 à M=13, lignes 6 à 16)
    for job_idx in range(11):  # TOUJOURS 11 lignes de jobs
        for machine_idx in range(10):  # TOUJOURS 10 colonnes de machines
            if job_idx < len(normalized_jobs_data) and machine_idx < len(normalized_jobs_data[job_idx]):
                duration = normalized_jobs_data[job_idx][machine_idx]
                print(f"DEBUG - Writing job {job_idx}, machine {machine_idx}: duration = {duration} (type: {type(duration)})")
            else:
                duration = ""  # Cellule vide si pas de données
                print(f"DEBUG - No data for job {job_idx}, machine {machine_idx}: setting empty")
                
            cell = ws.cell(row=6+job_idx, column=4+machine_idx, value=duration)
            cell.border = border
            print(f"DEBUG - Cell ({6+job_idx}, {4+machine_idx}) = {cell.value}")
    
    # Ajuster la largeur des colonnes (C à N)
    for col in range(3, 15):  # De C=3 à N=14
        column_letter = ws.cell(row=1, column=col).column_letter
        ws.column_dimensions[column_letter].width = 12
    
    # Ajouter un onglet d'instructions
    instructions_ws = wb.create_sheet("Instructions")
    instructions_ws['A1'] = "DONNÉES EXPORTÉES - Format Matriciel 12x12"
    instructions_ws['A1'].font = Font(bold=True, size=14)
    
    instructions = [
        "",
        "Structure FIXE du fichier (12 colonnes x 12 lignes) :",
        "- C5: 'JOB' (coin supérieur gauche)",
        "- C6-C16: Noms des jobs (max 11 jobs)",
        "- D5-M5: Noms des machines (max 10 machines)",
        "- N5: 'Due Date' (TOUJOURS colonne N)",
        "- N6-N16: Dates d'échéance",
        "- D6-M16: Matrice des temps de traitement",
        "",
        "Paramètres actuels :",
        f"- Unité de temps: {unite}",
        f"- Nombre de machines utilisées: {len(machine_names)}/10",
        f"- Nombre de jobs utilisés: {num_jobs}/11",
        "",
        "IMPORTANT :",
        "- La structure 12x12 est FIXE pour compatibilité d'import",
        "- Les cellules vides sont normales si moins de données",
        "- La colonne 'Due Date' est TOUJOURS en colonne N",
        "",
        "Ce fichier peut être modifié et réimporté dans l'application."
    ]
    
    for i, instruction in enumerate(instructions):
        instructions_ws.cell(row=2+i, column=1, value=instruction)
    
    # Sauvegarder dans le BytesIO
    wb.save(output)
    output.seek(0)
    return output.getvalue()

 