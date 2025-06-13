import requests
import json

# Test des données exactement comme le frontend les envoie
test_data = {
    "jobs_data": [
        [
            [[11, 10.0]],  # Job 1, Étape 1: machine 11 (M1) avec durée 10
            [[21, 15.0]]   # Job 1, Étape 2: machine 21 (M2) avec durée 15
        ],
        [
            [[11, 12.0]],  # Job 2, Étape 1: machine 11 (M1) avec durée 12
            [[21, 18.0]]   # Job 2, Étape 2: machine 21 (M2) avec durée 18
        ],
        [
            [[11, 8.0]],   # Job 3, Étape 1: machine 11 (M1) avec durée 8
            [[21, 20.0]]   # Job 3, Étape 2: machine 21 (M2) avec durée 20
        ]
    ],
    "due_dates": [10, 15, 20],
    "unite": "heures",
    "job_names": ["Job 1", "Job 2", "Job 3"],
    "machine_names": ["Machine 1", "Machine 2"],
    "stage_names": ["Machine 1", "Machine 2"],
    "machines_per_stage": [1, 1]
}

def test_api():
    url = "http://localhost:8000/flowshop/machines_multiples"
    
    try:
        print("Envoi des données de test...")
        print("Structure des données:")
        print(f"jobs_data type: {type(test_data['jobs_data'])}")
        print(f"jobs_data[0] type: {type(test_data['jobs_data'][0])}")
        print(f"jobs_data[0][0] type: {type(test_data['jobs_data'][0][0])}")
        print(f"jobs_data[0][0][0] type: {type(test_data['jobs_data'][0][0][0])}")
        print(f"Données: {json.dumps(test_data, indent=2)}")
        
        response = requests.post(url, json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Succès!")
            print(f"Makespan: {result['makespan']}")
            print(f"Flowtime: {result['flowtime']}")
            print(f"Status: {result['status']}")
            return True
        else:
            print(f"❌ Erreur {response.status_code}")
            try:
                error = response.json()
                print(f"Détail: {error}")
            except:
                print(f"Réponse: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    test_api() 