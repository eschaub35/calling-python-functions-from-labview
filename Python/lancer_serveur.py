#%%
import sys
import importlib
import LV_Python_TCP_Lib
importlib.reload(LV_Python_TCP_Lib)
from LV_Python_TCP_Lib import demarrer_serveur

def incremente(x):
    return x+1

def convertir_majuscule(chaine: str) -> tuple[str, int]:
    chaine_majuscule = chaine.upper()
    nombre_caracteres = len(chaine)

    return chaine_majuscule, nombre_caracteres

def traiter_donnees(
    nom: str,
    valeur: float,
    configuration: dict
) -> tuple[str, float, list[dict]]:

    nom_majuscule = nom.upper()
    resultat = valeur * configuration["coefficient"]

    details = [
        {"nom": nom, "valeur": resultat},
        {"nom": "seuil", "valeur": configuration["seuil"]}
    ]

    return nom_majuscule, resultat, details

def test_fonction():
    return [{"nom": "seuil", "valeur": 3.14}]

fonctions_appelables = {
    "incremente": incremente,
    "convertir_majuscule": convertir_majuscule,
    "traiter_donnees": traiter_donnees,
    "test_fonction": test_fonction,
}



if __name__ == "__main__":
    if "ipykernel" in sys.modules:
        # Exécution dans Jupyter ou un notebook interactif
        port = 5000
    else:
        # Exécution depuis un terminal
        if len(sys.argv) < 2:
            print("Erreur : le port doit être fourni en argument.")
            sys.exit(1)

        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Erreur : le port doit être un entier.")
            sys.exit(1)

    if not 1 <= port <= 65535:
        print("Erreur : le port doit être compris entre 1 et 65535.")
        sys.exit(1)

    demarrer_serveur(port, fonctions_appelables)

# %%
