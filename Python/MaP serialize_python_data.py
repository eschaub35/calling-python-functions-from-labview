#%%

# Le but de ce VI est de tester la fonction
# **`serialize_python_data`** de la bibliothèque
# `LV_Python_TCP_Lib.py`.

# Le VI **« Save LV_data.vi »** permet de sauvegarder
# une donnée LabVIEW sous forme de fichier.
# Dans notre exemple, ce fichier est
# **« My_cluster.dat »**.

# Ce fichier est ensuite chargé et converti
# en une donnée Python.
# C’est à cette donnée Python qu’est appliquée
# la fonction **`serialize_python_data`**.

# La donnée binaire résultante est alors sauvegardée
# dans un fichier.
# Dans notre exemple, il s’agit de
# **« donnees.dat »**.

# L’intérêt est de pouvoir ensuite recharger
# cette donnée binaire dans LabVIEW
# et la reconvertir en donnée LabVIEW
# grâce à la fonction **« Unflatten From String »**.

# Cela permet de vérifier que la donnée LabVIEW
# reconstituée est strictement identique
# à la donnée LabVIEW d’origine.

import numpy as np
import os
import sys
import struct
import json
from pprint import pprint

# Répertoire contenant le script exécuté
script_dir = os.path.dirname(os.path.abspath(__file__))
# Ajouter ce répertoire aux chemins de recherche Python
sys.path.insert(0, script_dir)

import importlib
import LV_Python_TCP_Lib

importlib.reload(LV_Python_TCP_Lib)

from LV_Python_TCP_Lib import deserialize_labview_binary

file_name = r"My_cluster.dat"
file_name = r"D:\Home\eschaub\Documents\INFORMATIQUE\LabVIEW-Python TCP\MultiTauImSeriesV2\MaP\My_cluster.dat"
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

json_string = json_bytes.decode("cp1252")
print(json_string)


python_data = deserialize_labview_binary(
    json_string,
    donnees_binaires
)


pprint(f'Python data: {python_data}', sort_dicts=False)
#%%

# Nous disposons d’une donnée Python :
# `python_data`.

# Cette donnée est sérialisée sous forme
# d’une suite d’octets, grâce à la fonction
# **`serialize_python_data`**.

# Enfin, la suite d’octets résultante est
# sauvegardée dans un fichier binaire :
# **« python_data.dat »**.

from LV_Python_TCP_Lib import serialize_python_data

print("Type du python data :", type(python_data))

if isinstance(python_data, np.ndarray):
    print("Type du tableau :", python_data.dtype)
    print("Dimensions :", python_data.shape)

    for index, item in enumerate(python_data.flat):
        print(f"Élément {index} : {type(item)}")
        if isinstance(item, dict):
            for key, value in item.items():
                print(f"  {key}: {type(value)}, "
                      f"dtype={getattr(value, 'dtype', None)}, "
                      f"shape={getattr(value, 'shape', None)}")


binary = serialize_python_data(python_data)

binary_data_file = r"python_data.dat"

print(f"binary: {binary}")
with open(binary_data_file, "wb") as f:
    f.write(binary)


print(f'binaire OK:{donnees_binaires == binary}')