from smith import smith_algorithm

jobs = [
    [12, 40],
    [6, 25],
    [9, 30],
    [15, 50],
    [7, 20]
]

try:
    result = smith_algorithm(jobs)
    print("✅ Résultat :", result)
except Exception as e:
    print("❌ Erreur :", e)
