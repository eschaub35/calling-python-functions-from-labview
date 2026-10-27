#%%
# Le VI **« Save Cluster.vi »** permet d’enregistrer
# dans un fichier une donnée LabVIEW,
# dont la structure peut être complexe.

# Ce fichier se compose de deux parties :
# - une première partie contenant une description
#   de la structure et des types de données
#   au format JSON ;
# - une seconde contenant les valeurs des données
#   sous forme binaire.

# Le présent script a pour objectif de tester
# la fonction **`deserialize_labview_binary`**
# de la bibliothèque `LV_Python_TCP_Lib.py`.

# Cette fonction permet de reconstruire une donnée
# Python à partir d’un fichier contenant une donnée
# LabVIEW préalablement sauvegardée à l’aide
# du VI **« Save Cluster.vi »**.

# Dans le cadre de la communication Labview-Python par TCP,
# La fonction **`deserialize_labview_binary`** sera utilisée
# par le serveur python pour décoder les commandes envoyées
# par Labview

import struct
import json
from LV_Python_TCP_Lib import deserialize_labview_binary

file_name = r"D:\Home\eschaub\Documents\INFORMATIQUE\LabVIEW-Python TCP\My_cluster.dat"
with open(file_name, "rb") as f:

    # 1. Lire les 8 octets du header
    header = f.read(8)

    if len(header) != 8:
        raise ValueError("Header incomplet")

    # 2. Récupérer les deux tailles
    taille_json, taille_binaire = struct.unpack(">II", header)

    # 3. Lire le JSON
    json_bytes = f.read(taille_json)

    if len(json_bytes) != taille_json:
        raise ValueError("Données JSON incomplètes")

    json_string = json_bytes.decode("cp1252")

    # 4. Convertir les bytes en dictionnaire Python
    description = json.loads(json_bytes.decode("utf-8"))

    # 5. Lire les données binaires
    donnees_binaires = f.read(taille_binaire)

    if len(donnees_binaires) != taille_binaire:
        raise ValueError("Données binaires incomplètes")

print("Taille JSON :", taille_json)
print("Taille binaire :", taille_binaire)
print("Description :", description)
print("Données binaires :", donnees_binaires)

# Convertit les octets de json_bytes en chaîne de caractères
# en utilisant l'encodage cp1252, compatible avec les caractères
# accentués couramment utilisés sous Windows.
json_string = json_bytes.decode("cp1252")
print(json_string)


python_data = deserialize_labview_binary(
    json_string,
    donnees_binaires
)

print(python_data)

# Importe la fonction pprint, qui permet d'afficher
# des données Python de manière lisible et structurée.
from pprint import pprint

# Affiche le contenu de python_data avec une mise en forme
# facilitant la lecture des structures complexes.
# sort_dicts=False conserve l'ordre d'insertion des clés
# dans les dictionnaires.
pprint(python_data, sort_dicts=False)
