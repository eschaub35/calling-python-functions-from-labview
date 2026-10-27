# =============================================================================
# LIBRAIRIE DE COMMUNICATION TCP ENTRE PYTHON ET LABVIEW
# =============================================================================
#
# OBJECTIF
# --------
# Cette librairie permet à une application LabVIEW de communiquer avec un
# programme Python au moyen d'une connexion TCP. Elle fournit :
#
# - la sérialisation des données Python et NumPy en un format binaire défini ;
# - la désérialisation des données binaires reçues depuis LabVIEW ;
# - un protocole de transport permettant d'échanger des messages complets ;
# - un serveur TCP capable de traiter plusieurs connexions clientes ;
# - un dispatcher permettant à LabVIEW d'appeler des fonctions Python
#   explicitement autorisées et de récupérer leurs résultats.
#
# PROTOCOLE DE COMMUNICATION
# --------------------------
# Chaque paquet TCP respecte le format suivant :
#
#   [4 octets : taille du JSON, entier non signé big-endian]
#   [4 octets : taille des données binaires, entier non signé big-endian]
#   [JSON encodé en CP1252]
#   [Données binaires]
#
# Les deux tailles sont exprimées en octets. La réception reconstitue le paquet
# complet, car TCP ne garantit pas qu'un message soit reçu en un seul bloc.
# Une même connexion peut transporter plusieurs transactions successives.
#
# Le JSON fournit la description utilisée pour interpréter les données binaires.
# La structure attendue doit être cohérente avec celle définie dans LabVIEW.
# En cas de succès, le résultat de la fonction Python est retourné dans le champ
# binaire de la réponse. En cas d'erreur pendant le traitement d'une fonction,
# le serveur tente de retourner un message JSON contenant le statut et l'erreur.
#
# UTILISATION
# -----------
# 1. Importer cette librairie dans le programme Python.
# 2. Définir les fonctions que LabVIEW est autorisé à appeler.
# 3. Les enregistrer dans le dictionnaire `fonctions_appelables`, en associant
#    chaque nom de fonction à sa fonction Python.
# 4. Démarrer le serveur avec `demarrer_serveur(port, fonctions_appelables)`.
# 5. Configurer LabVIEW pour se connecter à l'adresse et au port du serveur,
#    puis construire et interpréter les paquets selon le protocole défini.
#
# La fonction `stop_server` est réservée par le serveur et ajoutée
# automatiquement au dictionnaire des fonctions accessibles. Son appel demande
# l'arrêt du serveur après l'envoi de la réponse.
#
# L'adresse d'écoute est définie par la constante `HOST`. Avec `localhost`,
# seules les connexions locales sont visées. Pour accepter des connexions depuis
# une autre machine, l'adresse d'écoute et la configuration réseau doivent être
# adaptées avec les précautions de sécurité nécessaires.
#
# TYPES ET CONVENTIONS DE SÉRIALISATION
# -------------------------------------
# Les types pris en charge comprennent notamment les booléens, les entiers,
# les flottants, les nombres complexes, les chaînes, les tableaux NumPy,
# les listes, les tuples et les dictionnaires représentant des clusters.
#
# Les données binaires ne sont pas auto-descriptives : LabVIEW doit connaître
# les types, les dimensions, l'ordre et la structure des champs attendus.
# Les règles exactes de sérialisation sont documentées dans les fonctions
# correspondantes de cette librairie.
#
# LIMITATIONS ET POINTS DE VIGILANCE
# ----------------------------------
# - Python et LabVIEW doivent appliquer exactement les mêmes conventions
#   de types, d'ordre des octets, de dimensions et d'organisation des clusters.
# - Les chaînes utilisent CP1252. Les caractères non représentables peuvent
#   provoquer une erreur lors de l'encodage ; le décodage du JSON reçu utilise
#   actuellement un remplacement des caractères invalides.
# - Les listes et tuples vides ne sont pas pris en charge dans la sérialisation,
#   car le type de leurs éléments ne peut pas être déduit.
# - Les listes numériques hétérogènes et certains tableaux NumPy, notamment
#   les tableaux structurés, ne sont pas pris en charge.
# - Les tableaux NumPy de type `object` ne sont acceptés que dans certains cas,
#   notamment pour des dictionnaires ou des nombres complexes.
# - Les clés des dictionnaires ne sont pas transmises dans le flux binaire :
#   l'ordre des champs doit correspondre au cluster LabVIEW attendu.
# - Les tableaux booléens utilisent un octet par élément. Cette convention doit
#   être compatible avec leur représentation côté LabVIEW.
# - Les tailles maximales sont définies par `TAILLE_JSON_MAX` et
#   `TAILLE_BINAIRE_MAX`. La limite binaire actuelle de 1 Gio peut autoriser
#   des allocations mémoire importantes et doit être adaptée aux besoins réels.
# - Le serveur traite les clients dans des threads distincts, mais ne fournit
#   pas encore de mécanisme complet de fermeture coordonnée de toutes les
#   connexions clientes à l'arrêt.
# - Le protocole ne prévoit pas, à lui seul, de chiffrement, d'authentification,
#   de contrôle d'intégrité applicatif ou de négociation de version.
# - Une erreur de réception ou de décodage peut entraîner la fermeture de la
#   connexion sans qu'une réponse d'erreur structurée soit envoyée à LabVIEW.
#
# PISTES D'AMÉLIORATION
# --------------------
# - Unifier et documenter précisément l'encodage des chaînes et du JSON.
# - Adapter les limites de taille et ajouter des contrôles sur les dimensions
#   et le nombre d'éléments afin de limiter les consommations excessives.
# - Ajouter des délais d'attente et une gestion plus explicite des erreurs
#   de réception, de décodage, d'exécution et d'envoi.
# - Garantir une réponse d'erreur cohérente lorsque le protocole le permet.
# - Mettre en place un arrêt propre : fermer le socket d'écoute, fermer ou
#   terminer les connexions actives et attendre la fin des threads.
# - Ajouter une version de protocole et des tests automatisés couvrant les
#   types pris en charge, les paquets incomplets et les cas d'erreur.
# - Si le serveur est accessible depuis un réseau, ajouter des protections
#   adaptées : authentification, chiffrement et restriction des accès.
#
# COMPATIBILITÉ
# -------------
# Toute modification du protocole ou de la sérialisation doit être répercutée
# dans le code LabVIEW correspondant et validée par des tests d'interopérabilité.
#
# =============================================================================

import json
import struct
import numpy as np
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import socket
import threading


class LabVIEWDecoder:

    def __init__(self, data):
        # data peut être bytes, bytearray ou tableau numpy de uint8
        self.data = bytes(data)
        self.pos = 0

    def read_bytes(self, n):
        """Lit n octets et avance dans le buffer."""
        if self.pos + n > len(self.data):
            raise ValueError(
                f"Données insuffisantes : "
                f"{n} octets demandés à la position {self.pos}, "
                f"{len(self.data) - self.pos} disponibles"
            )

        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def read_I32(self):
        """Lit un I32 big-endian."""
        return struct.unpack(">i", self.read_bytes(4))[0]

    def read_Boolean(self):
        """Lit un Boolean LabVIEW."""
        return self.read_bytes(1)[0] != 0

    def read_numeric(self, type_):

        dtype_map = {
            "I8": ">i1",
            "U8": ">u1",
            "I16": ">i2",
            "U16": ">u2",
            "I32": ">i4",
            "U32": ">u4",
            "I64": ">i8",
            "U64": ">u8",
            "Single Float": ">f4",
            "Double Float": ">f8",
        }

        # if type_ in ("Complex Single Float", "Complex Double Float"):
        #     component_dtype = (
        #         ">f4" if type_ == "Complex Single Float" else ">f8"
        #     )

        #     components = np.frombuffer(
        #         self.read_bytes(2 * np.dtype(component_dtype).itemsize),
        #         dtype=np.dtype(component_dtype),
        #         count=2
        #     )

        #     return complex(float(components[0]), float(components[1]))


        if type_ in ("Single Complex", "Double Complex"):
            component_dtype = (
                ">f4" if type_ == "Single Complex" else ">f8"
            )

            components = np.frombuffer(
                self.read_bytes(2 * np.dtype(component_dtype).itemsize),
                dtype=np.dtype(component_dtype),
                count=2
            )

            return complex(float(components[0]), float(components[1]))


        if type_ not in dtype_map:
            raise ValueError(f"Type numérique LabVIEW inconnu : {type_}")

        dtype = np.dtype(dtype_map[type_])

        return np.frombuffer(
            self.read_bytes(dtype.itemsize),
            dtype=dtype,
            count=1
        )[0].item()

    def read_String(self):
        """Lit une String LabVIEW."""
        length = self.read_I32()

        if length < 0:
            raise ValueError(
                f"Longueur de String invalide : {length}"
            )

        raw = self.read_bytes(length)

        return raw.decode("cp1252")

    def decode(self, description):

        type_ = description["type"]

        if type_ == "Cluster":
            return self.decode_cluster(description)

        elif type_ == "Array":
            return self.decode_array(description)

        elif type_ == "Boolean":
            return self.read_Boolean()


        elif type_ == "String":
            return self.read_String()

        else:
            return self.read_numeric(type_)

    def decode_cluster(self, description):
        """
        Décode un cluster.
        """
        result = {}

        for name, field_description in description["fields"].items():

            result[name] = self.decode(field_description)

        return result

    def decode_array(self, description):
        """
        Décode un tableau LabVIEW dont les dimensions
        sont préfixées dans le binaire.
        """

        dimensions = description["dimensions"]

        # Lecture des tailles des dimensions
        shape = tuple(
            self.read_I32()
            for _ in range(dimensions)
        )

        # Vérification
        if any(size < 0 for size in shape):
            raise ValueError(f"Taille de tableau invalide : {shape}")

        element_description = description["element"]

        # Tableau numérique / booléen
        if self.is_numpy_array_type(element_description):

            return self.decode_numpy_array(
                shape,
                element_description
            )

        # Tableau de clusters
        else:

            return self.decode_object_array(
                shape,
                element_description
            )

    def is_numpy_array_type(self, description):
        if "type" in description:
            return description["type"] in {
                "I8", "U8",
                "I16", "U16",
                "I32", "U32",
                "I64", "U64",
                "Single Float",
                "Double Float",
                "Single Complex",
                "Double Complex",
                "Boolean"
            }

        return False

    def decode_numpy_array(self, shape, description):

        type_ = description["type"]

        dtype_map = {
            "I8": ">i1",
            "U8": ">u1",
            "I16": ">i2",
            "U16": ">u2",
            "I32": ">i4",
            "U32": ">u4",
            "I64": ">i8",
            "U64": ">u8",
            "Single Float": ">f4",
            "Double Float": ">f8",
            "Boolean": "u1",
        }

        # Types complexes : composantes réelle et imaginaire successives
        complex_types = {
            "Single Complex": (">f4", np.complex64),
            "Double Complex": (">f8", np.complex128),
        }

        count = int(np.prod(shape))

        if type_ in complex_types:
            component_dtype, complex_dtype = complex_types[type_]
            component_dtype = np.dtype(component_dtype)

            raw = self.read_bytes(
                count * 2 * component_dtype.itemsize
            )

            components = np.frombuffer(
                raw,
                dtype=component_dtype,
                count=2 * count
            )

            # Les composantes sont entrelacées :
            # réel 0, imaginaire 0, réel 1, imaginaire 1, ...
            # array = (
            #     components[0::2].astype(np.float64)
            #     + 1j * components[1::2].astype(np.float64)
            # ).astype(complex_dtype)
            array = np.empty(count, dtype=complex_dtype)
            array.real = components[0::2]
            array.imag = components[1::2]

            return array.reshape(shape, order="C")

        if type_ not in dtype_map:
            raise ValueError(f"Type numérique inconnu : {type_}")

        dtype = np.dtype(dtype_map[type_])

        raw = self.read_bytes(count * dtype.itemsize)

        array = np.frombuffer(
            raw,
            dtype=dtype,
            count=count
        )

        if type_ == "Boolean":
            array = array.astype(bool)

        return array.reshape(shape, order="C")

    def decode_object_array(self, shape, description):

        count = int(np.prod(shape))

        values = []

        for _ in range(count):
            values.append(
                self.decode_array_element(description)
            )

        # Tableau numpy d'objets
        array = np.empty(count, dtype=object)

        for i, value in enumerate(values):
            array[i] = value

        return array.reshape(shape, order="C")

    def decode_array_element(self, description):
        return self.decode(description)

def deserialize_labview_binary(json_string, reponse_binaire):
    cluster_type_dic = json.loads(json_string)
    decoder = LabVIEWDecoder(reponse_binaire)

    # Décodage direct du cluster racine
    result = decoder.decode(cluster_type_dic)

    # Vérification : tous les octets doivent avoir été consommés
    if decoder.pos != len(decoder.data):
        remaining = len(decoder.data) - decoder.pos
        raise ValueError(
            f"{remaining} octets restent après décodage "
            f"(position {decoder.pos}/{len(decoder.data)})"
        )

    return result

# ------------------------------------------------------------
# Types numériques LabVIEW -> représentation NumPy big-endian
# ------------------------------------------------------------

NUMPY_TO_LABVIEW = {
    np.dtype("int8"):    ("I8", ">i1"),
    np.dtype("int16"):   ("I16", ">i2"),
    np.dtype("int32"):   ("I32", ">i4"),
    np.dtype("int64"):   ("I64", ">i8"),

    np.dtype("uint8"):   ("U8", ">u1"),
    np.dtype("uint16"):  ("U16", ">u2"),
    np.dtype("uint32"):  ("U32", ">u4"),
    np.dtype("uint64"):  ("U64", ">u8"),

    np.dtype("float32"): ("Single Float", ">f4"),
    np.dtype("float64"): ("Double Float", ">f8"),

    np.dtype("complex64"):  ("Single Complex", ">c8"),
    np.dtype("complex128"): ("Double Complex", ">c16"),
}


# ------------------------------------------------------------
# Entiers signés 32 bits : dimensions et chaînes
# ------------------------------------------------------------

def pack_i32(value):
    """Encode un entier signé I32 en big-endian."""
    if not -(2**31) <= value < 2**31:
        raise OverflowError(f"{value} ne tient pas dans un I32")
    return struct.pack(">i", value)


# ------------------------------------------------------------
# Sérialisation récursive
# ------------------------------------------------------------
# =============================================================================
# Sérialisation des données Python vers un flux binaire compatible LabVIEW
#
# OBJECTIF
# -------
# Convertir une valeur Python ou NumPy en une séquence d'octets (bytes)
# destinée à être interprétée par LabVIEW selon un protocole prédéfini.
#
# Le format produit dépend du type de la valeur :
# - certaines valeurs sont encodées directement sur un nombre fixe d'octets ;
# - les chaînes et les données binaires sont précédées de leur longueur ;
# - les tableaux NumPy sont précédés de leurs dimensions ;
# - les listes homogènes sont précédées de leur nombre d'éléments ou
#   utilisent les dimensions du tableau NumPy correspondant ;
# - les dictionnaires sont sérialisés comme des clusters de champs ;
# - les listes hétérogènes sont concaténées sans préfixe global de longueur.
#
# HYPOTHÈSES SUR LE PROTOCOLE
# ---------------------------
# 1. L'ordre des champs d'un dictionnaire correspond à l'ordre des champs
#    du cluster LabVIEW associé. Les clés ne sont pas transmises.
#
# 2. LabVIEW connaît à l'avance la structure attendue des clusters :
#    nombre de champs, types et ordre des champs.
#
# 3. Pour les listes hétérogènes, LabVIEW connaît le nombre d'éléments,
#    leur type et leur ordre. Aucun compteur global n'est ajouté.
#
# 4. Les listes homogènes nécessitent une information de longueur :
#    compteur explicite pour les chaînes et les dictionnaires, ou dimensions
#    pour les tableaux numériques.
#
# 5. Les entiers codés sur 32 bits utilisent le format défini par pack_i32.
#    Les flottants Python sont encodés en double précision IEEE 754,
#    avec l'ordre des octets défini explicitement par struct.pack.
#
# 6. Les chaînes Python sont encodées en Windows-1252 (CP1252), sans
#    remplacement des caractères non représentables.
#
# 7. Les types NumPy numériques sont convertis vers les types cibles définis
#    dans NUMPY_TO_LABVIEW avant l'écriture de leurs octets.
#
# 8. Les tableaux sont parcourus dans l'ordre C : le dernier indice varie
#    le plus rapidement.
#
# RÈGLES DE SÉRIALISATION
# -----------------------
# - bool et np.bool_ :
#   un octet, 0 pour False et 1 pour True.
#
# - str :
#   longueur des octets encodés sur 32 bits, suivie des octets CP1252.
#
# - bytes et bytearray :
#   longueur sur 32 bits, suivie des octets bruts.
#
# - int Python :
#   entier signé sur 32 bits, selon pack_i32.
#
# - float Python :
#   flottant IEEE 754 en double précision, encodé sur 8 octets.
#
# - complex Python :
#   partie réelle puis partie imaginaire, chacune en double précision.
#
# - np.generic :
#   scalaire NumPy converti vers un type cible pris en charge.
#
# - np.ndarray :
#   dimensions encodées sur 32 bits, suivies des données contiguës
#   dans l'ordre C. Les types numériques structurés sont refusés.
#
# - list et tuple homogènes de nombres :
#   conversion en tableau NumPy, puis sérialisation du tableau.
#
# - list et tuple de chaînes :
#   nombre d'éléments sur 32 bits, puis chaque chaîne sérialisée
#   avec son propre préfixe de longueur.
#
# - list et tuple de dictionnaires :
#   nombre d'éléments sur 32 bits, puis chaque dictionnaire sérialisé.
#   Les dictionnaires doivent avoir les mêmes clés dans le même ordre.
#
# - list et tuple hétérogènes :
#   concaténation des éléments sérialisés individuellement, sans compteur.
#
# LIMITES ET POINTS DE VIGILANCE
# ------------------------------
# - Le format binaire n'est pas auto-descriptif : le récepteur doit connaître
#   les types et la structure attendus pour interpréter correctement les
#   octets.
#
# - Les clés des dictionnaires ne sont pas transmises. Une clé non textuelle
#   est refusée, mais les noms des champs ne sont pas vérifiés par LabVIEW.
#
# - L'ordre des champs est significatif. Deux dictionnaires contenant les
#   mêmes clés dans un ordre différent ne représentent pas le même cluster.
#
# - Les listes hétérogènes ne contiennent aucun compteur global. Une erreur
#   dans le schéma connu de LabVIEW peut décaler l'interprétation du flux.
#
# - Les entiers Python doivent être représentables sur 32 bits signés.
#   Une vérification de bornes est nécessaire avant toute conversion
#   explicite vers np.int32.
#
# - L'ordre des octets des types NumPy doit être compatible avec LabVIEW.
#   Les types cibles de NUMPY_TO_LABVIEW doivent définir cette convention
#   de manière cohérente avec pack_i32 et les flottants Python.
#
# - Les tableaux NumPy de chaînes ne sont pas pris en charge explicitement.
#   Les tableaux de type object ne sont acceptés que pour les cas prévus
#   par l'implémentation, notamment certains dictionnaires et nombres
#   complexes.
#
# - Les tableaux vides et les listes ou tuples vides sont refusés selon
#   les règles de l'implémentation.
#
# - Les tableaux NumPy booléens sont encodés avec un octet par élément.
#   LabVIEW doit utiliser une représentation compatible.
#
# - Les dimensions des tableaux sont encodées sur 32 bits. Leur nombre
#   et leur ordre doivent correspondre à ceux attendus par LabVIEW.
#
# - Le format des complexes est supposé être deux doubles successifs :
#   réel puis imaginaire. Le cluster LabVIEW correspondant doit respecter
#   cette disposition.
#
# - Les caractères non représentables en CP1252 provoquent une erreur.
#   Aucun remplacement ni encodage UTF-8 de secours n'est effectué.
#
# - La fonction ne définit pas à elle seule le protocole de transport :
#   délimitation des messages, versionnement, contrôle d'intégrité et
#   gestion des erreurs doivent être traités séparément si nécessaire.
#
# COMPATIBILITÉ
# -------------
# Toute modification des règles de sérialisation doit être répercutée
# dans le code LabVIEW qui décode le flux binaire.
# =============================================================================
def serialize_python_data(value):
    """
    Sérialise une valeur Python en octets selon les conventions
    définies pour la conversion vers un cluster LabVIEW.

    Conventions :
      bool          -> Boolean (1 octet, convention à valider)
      int           -> I32
      float         -> Double Float
      str           -> String CP1252, longueur I32
      dict          -> Cluster, champs dans l'ordre d'insertion
      ndarray       -> Array, dimensions puis données
      list / tuple  -> Array 1D homogène
      np.generic    -> type déduit du dtype NumPy

    Les types non pris en charge provoquent une exception.
    """

    # 1. Booléen : impérativement avant int
    if isinstance(value, (bool, np.bool_)):
        return b"\x01" if value else b"\x00"

    # 2. Chaîne : CP1252
    if isinstance(value, str):
        encoded = value.encode("cp1252", errors="strict")
        return pack_i32(len(encoded)) + encoded

    # 3. Données binaires : tableau 1D de U8
    if isinstance(value, (bytes, bytearray)):
        return pack_i32(len(value)) + bytes(value)

    # 4. Dictionnaire : Cluster
    if isinstance(value, dict):
        parts = []

        for key, field_value in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Les clés d'un cluster doivent être des chaînes : {key!r}"
                )

            parts.append(serialize_python_data(field_value))

        return b"".join(parts)

    # 5. Tableau NumPy
    if isinstance(value, np.ndarray):

        # Tableau object : clusters ou nombres complexes
        if value.dtype == object:
            elements = value.ravel(order="C")

            # Tableau de clusters (dictionnaires)
            if elements.size > 0 and all( isinstance(item, dict) for item in elements ):
                data = b"".join(serialize_python_data(item) for item in elements)

            # Tableau de nombres complexes Python/NumPy
            elif elements.size > 0 and all( isinstance(item, (complex, np.complexfloating)) for item in elements ):
                data = b"".join(serialize_python_data(item) for item in elements)

            else:
                raise TypeError(
                    "Tableau object non pris en charge : "
                    "les éléments doivent être des dictionnaires "
                    "ou des nombres complexes."
                )

        else:
            # Refuser les tableaux structurés
            if value.dtype.fields is not None:
                raise TypeError(
                    "Les tableaux NumPy structurés ne sont pas pris "
                    "en charge directement."
                )

            # Tableau de booléens
            if value.dtype.kind == "b":
                data = value.astype(np.uint8).tobytes(order="C")

            # Types numériques pris en charge
            elif value.dtype.newbyteorder("=") in NUMPY_TO_LABVIEW:
                native_dtype = value.dtype.newbyteorder("=")
                _, target_dtype = NUMPY_TO_LABVIEW[native_dtype]
                data = value.astype(target_dtype).tobytes(order="C")

            else:
                raise TypeError(
                    f"dtype NumPy non pris en charge : {value.dtype}"
                )

        # Préfixe contenant la taille de chaque dimension
        dimensions = b"".join(
            pack_i32(int(size)) for size in value.shape
        )

        return dimensions + data


    # 6. Scalaire NumPy (np.int32, np.float32, etc.)
    if isinstance(value, np.generic):
        dtype = value.dtype

        if dtype.kind == "b":
            return b"\x01" if bool(value) else b"\x00"

        if dtype in NUMPY_TO_LABVIEW:
            _, target_dtype = NUMPY_TO_LABVIEW[dtype]
            return np.asarray(value).astype(target_dtype).tobytes(order="C")

        raise TypeError(f"Type scalaire NumPy non pris en charge : {dtype}")

    # 7. Entier Python natif -> I32
    if isinstance(value, int):
        return pack_i32(value)

    # 8. Flottant Python natif -> Double Float
    if isinstance(value, float):
        return struct.pack(">d", value)

    # 9. Nombre complexe Python natif -> Double Complex
    if isinstance(value, complex):
        return struct.pack(">dd", value.real, value.imag)    

    # 10. Liste ou tuple -> tableau 1D
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError(
                "Impossible de déduire le type d'un tableau vide."
            )

        # Liste/tuple de nombres complexes
        if all(
            isinstance(v, (complex, np.complexfloating))
            for v in value
        ):
            array = np.asarray(value, dtype=np.complex128)
            return serialize_python_data(array)

        # Les tableaux numériques homogènes sont convertis en ndarray.
        # On refuse les conversions implicites de types hétérogènes.
        if all(
            isinstance(v, (bool, int, float, np.generic))
            and not isinstance(v, (str, bytes))
            for v in value
        ):
            # Empêcher notamment la promotion silencieuse bool -> entier.
            if all(isinstance(v, (bool, np.bool_)) for v in value):
                array = np.asarray(value, dtype=np.bool_)
            elif all(
                isinstance(v, (int, np.integer))
                and not isinstance(v, (bool, np.bool_))
                for v in value
            ):
                # Les entiers Python natifs doivent rester I32.
                # On ne convertit pas automatiquement une liste d'entiers
                # en int64.
                if all(
                    isinstance(v, (int, np.integer))
                    and not isinstance(v, (bool, np.bool_))
                    for v in value
                ):
                    if any(
                        isinstance(v, (int, np.integer))
                        and not isinstance(v, np.generic)
                        for v in value
                    ):
                        array = np.asarray(value, dtype=np.int32)
                    else:
                        array = np.asarray(value)
            elif all(
                isinstance(v, (float, np.floating))
                and not isinstance(v, (bool, np.bool_))
                for v in value
            ):
                if any(type(v) is float for v in value):
                    array = np.asarray(value, dtype=np.float64)
                else:
                    array = np.asarray(value)
            else:
                return b"".join(serialize_python_data(v) for v in value)

            return serialize_python_data(array)

        # Tableau de chaînes : longueur puis contenu pour chaque élément.
        if all(isinstance(v, str) for v in value):
            return (
                pack_i32(len(value))
                + b"".join(serialize_python_data(v) for v in value)
            )

        # Tableau de clusters : tous les éléments doivent être des dict
        # de structure identique.
        if all(isinstance(v, dict) for v in value):
            expected_keys = list(value[0].keys())

            for item in value[1:]:
                if list(item.keys()) != expected_keys:
                    raise ValueError(
                        "Les dictionnaires d'un tableau de clusters "
                        "doivent avoir les mêmes clés dans le même ordre."
                    )

            return pack_i32(len(value)) + b"".join(serialize_python_data(item) for item in value)

        return b"".join(
            serialize_python_data(v) for v in value
        )

    raise TypeError(
        f"Type Python non pris en charge : {type(value).__name__}"
    )

###########################################################################################################
# MARK: TCP serveur
###########################################################################################################


# ============================================================
# CONFIGURATION
# ============================================================

HOST = 'localhost'
# PORT = 5000
# Événement permettant de demander l'arrêt du serveur
ARRET_SERVEUR = threading.Event()


# Taille maximale autorisée pour éviter des allocations
# accidentelles de plusieurs Go en cas de paquet corrompu.
TAILLE_JSON_MAX = 10 * 1024 * 1024          # 10 Mo
TAILLE_BINAIRE_MAX = 1024 * 1024 * 1024     # 1 Go


# ============================================================
# OUTILS TCP
# ============================================================

def recevoir_exactement(sock, taille, fermeture_autorisee=False):
    """
    Reçoit exactement 'taille' octets.

    Si fermeture_autorisee=True, une fermeture propre
    avant la réception du premier octet retourne None.

    Une fermeture au milieu des données reçues reste une erreur.
    """
    donnees = bytearray()

    while len(donnees) < taille:
        a_lire = min(taille - len(donnees), 65536)
        morceau = sock.recv(a_lire)

        if not morceau:
            if fermeture_autorisee and len(donnees) == 0:
                return None

            raise ConnectionError(
                "Déconnexion prématurée : paquet incomplet."
            )

        donnees.extend(morceau)

    return bytes(donnees)




def recevoir_paquet(sock):
    """
    Reçoit un paquet :
        [4 octets taille JSON]
        [4 octets taille binaire]
        [JSON]
        [données binaires]

    Retourne (json_texte, donnees_binaires),
    ou None si le client ferme proprement la connexion
    avant le début d'une nouvelle requête.
    """

    # 1. En-tête
    header = recevoir_exactement(
        sock, 8, fermeture_autorisee=True
    )

    if header is None:
        return None

    taille_json, taille_binaire = struct.unpack(
        '>II', header
    )

    print(
        f"[RECEPTION] JSON = {taille_json} octets | "
        f"Binaire = {taille_binaire} octets"
    )

    # 2. Vérification des tailles
    if taille_json > TAILLE_JSON_MAX:
        raise ValueError(
            f"JSON trop volumineux : {taille_json} octets"
        )

    if taille_binaire > TAILLE_BINAIRE_MAX:
        raise ValueError(
            f"Données binaires trop volumineuses : "
            f"{taille_binaire} octets"
        )

    # 3. JSON
    json_brut = recevoir_exactement(sock, taille_json)

    json_texte = json_brut.decode(
        'cp1252', errors='replace'
    )

    # 4. Données binaires
    donnees_binaires = recevoir_exactement(
        sock, taille_binaire
    )

    return json_texte, donnees_binaires


def envoyer_paquet(sock, json_text, donnees_binaires=b''):
    """
    Envoie un paquet suivant le protocole :

        [4 octets taille JSON]
        [4 octets taille binaire]
        [JSON]
        [données binaires]
    """

    json_brut = json_text.encode('cp1252')

    # --------------------------------------------------------
    # 2. Vérification
    # --------------------------------------------------------

    taille_json = len(json_brut)
    taille_binaire = len(donnees_binaires)

    if taille_json > TAILLE_JSON_MAX:
        raise ValueError(
            f"JSON trop volumineux : {taille_json} octets"
        )

    if taille_binaire > TAILLE_BINAIRE_MAX:
        raise ValueError(
            f"Données binaires trop volumineuses : "
            f"{taille_binaire} octets"
        )

    # --------------------------------------------------------
    # 3. Construction de l'en-tête
    # --------------------------------------------------------

    header = struct.pack(
        '>II',
        taille_json,
        taille_binaire
    )

    # --------------------------------------------------------
    # 4. Envoi
    # --------------------------------------------------------

    sock.sendall(header)
    sock.sendall(json_brut)

    if taille_binaire > 0:
        sock.sendall(donnees_binaires)

    print(
        f"[ENVOI] "
        f"JSON = {taille_json} octets | "
        f"Binaire = {taille_binaire} octets"
    )


# ============================================================
# FONCTION DE DEMANDE D'ARRÊT DU SERVEUR
# ============================================================

def stop_server():
    """
    Prépare la réponse à une demande d'arrêt du serveur TCP.

    Cette fonction est appelée par LabVIEW comme les autres
    fonctions accessibles via le dispatcher.

    L'arrêt effectif doit être déclenché par le gestionnaire
    de la connexion après l'envoi de la réponse à LabVIEW.
    """

    print("[FONCTION] stop_server")
    print("    Demande d'arrêt du serveur reçue.")

    return 'fonction: stop_server.\nArrêt du serveur demandé.'


# ============================================================
# DISPATCHER : EXÉCUTION D'UNE FONCTION APPELÉE PAR LABVIEW
# ============================================================

def executer_fonction(cluster_dic, fonctions_appelables):
    """
    Identifie et exécute la fonction demandée par LabVIEW.

    cluster_dic :
        Dictionnaire Python issu de la désérialisation
        de la requête reçue.

    fonctions_appelables :
        Dictionnaire associant les noms autorisés aux fonctions.

    Retourne :
        Le résultat de la fonction exécutée.

    Lève :
        ValueError si la requête est invalide ou si la fonction
        demandée n'est pas autorisée.
        TypeError si les paramètres ne sont pas un dictionnaire
        ou ne correspondent pas à la signature de la fonction.
    """

    # 1. Vérification de la structure de la requête
    if not isinstance(cluster_dic, dict):
        raise ValueError(
            "La requête doit être un dictionnaire."
        )

    if "fonction" not in cluster_dic:
        raise ValueError(
            "Le JSON ne contient pas le champ 'fonction'."
        )

    nom_fonction = cluster_dic["fonction"]

    # 2. Vérification du nom de la fonction
    if not isinstance(nom_fonction, str):
        raise ValueError(
            "Le champ 'fonction' doit être une chaîne de caractères."
        )

    print(f"[FONCTION DEMANDEE] {nom_fonction}")

    if nom_fonction not in fonctions_appelables:
        raise ValueError(
            f"Fonction inconnue : '{nom_fonction}'"
        )

    # 3. Récupération et validation des paramètres
    parameters_dic = cluster_dic.get("parameters", {})

    if not isinstance(parameters_dic, dict):
        raise ValueError(
            "Le champ 'parameters' doit être un dictionnaire."
        )

    # 4. Exécution de la fonction autorisée
    fonction = fonctions_appelables[nom_fonction]

    return fonction(**parameters_dic)


# ============================================================
# GESTION D'UN CLIENT
# ============================================================

def gerer_client(socket_client, adresse_client, fonctions_appelables):
    """
    Gère une connexion TCP avec un client LabVIEW.

    Une connexion peut transporter plusieurs transactions.
    Une fermeture au début d'une nouvelle requête est normale.
    Une fermeture au milieu d'un paquet est une erreur.
    """

    print(f"[CONNEXION] Nouveau client : {adresse_client}")

    try:
        while True:

            # =================================================
            # 1. RÉCEPTION DE LA REQUÊTE
            # =================================================

            paquet = recevoir_paquet(socket_client)

            # None signifie que le client a fermé la connexion
            # avant le début d'une nouvelle requête.
            if paquet is None:
                print(
                    f"[DECONNEXION NORMALE] Client {adresse_client}"
                )
                break

            json_text, donnees_binaires = paquet

            print(f"[JSON text] {json_text}")
            print(f"[BINAIRE] {len(donnees_binaires)} octets")

            # Conversion du JSON et des données binaires
            # en objets Python.
            python_data = deserialize_labview_binary(
                json_text, donnees_binaires
            )

            # =================================================
            # 2. EXÉCUTION DE LA FONCTION DEMANDÉE
            # =================================================

            nom_fonction = (
                python_data.get("fonction")
                if isinstance(python_data, dict)
                else None
            )

            try:
                resultat = executer_fonction(
                    python_data, fonctions_appelables
                )

                # Le résultat est placé dans le champ binaire
                # du protocole de réponse.
                reponse_json = ''
                reponse_binaire = serialize_python_data(resultat)

            except Exception as e:
                # Erreur survenue pendant l'exécution
                # de la fonction ou la sérialisation du résultat.
                print(f"[ERREUR FONCTION] {e}")

                reponse_json = {
                    "statut": "ERREUR",
                    "message": str(e)
                }
                reponse_binaire = b''

            # =================================================
            # 3. ENVOI DE LA RÉPONSE
            # =================================================

            envoyer_paquet(
                socket_client,
                reponse_json,
                reponse_binaire
            )

            print(
                "[TRANSACTION] "
                "Requête traitée et réponse envoyée."
            )

            # =================================================
            # 4. DEMANDE D'ARRÊT DU SERVEUR
            # =================================================

            # La réponse à stop_server a été envoyée.
            # On peut maintenant signaler la demande d'arrêt.
            if nom_fonction == "stop_server":
                print(
                    "[SERVEUR] Réponse envoyée, arrêt demandé."
                )
                ARRET_SERVEUR.set()
                break

    except ConnectionError as e:
        print(
            f"[DECONNEXION / ERREUR TCP] "
            f"{adresse_client} : {e}"
        )

    except json.JSONDecodeError as e:
        print(
            f"[ERREUR JSON] JSON invalide : {e}"
        )

    except Exception as e:
        print(
            f"[ERREUR GENERALE] {adresse_client} : {e}"
        )

    finally:
        socket_client.close()

        print(
            f"[DISCONNECT] "
            f"Fin de session : {adresse_client}"
        )


# ============================================================
# DÉMARRAGE DU SERVEUR TCP
# ============================================================

def demarrer_serveur(port, fonctions_appelables):

    # 1. Vérification des fonctions accessibles aux clients
    if not isinstance(fonctions_appelables, dict):
        raise TypeError(
            "fonctions_appelables doit être un dictionnaire."
        )

    # Copie du dictionnaire pour préserver celui de l'appelant.
    fonctions = dict(fonctions_appelables)

    # La fonction d'arrêt est réservée au serveur.
    fonctions["stop_server"] = stop_server

    # Réinitialisation de l'événement d'arrêt pour cette session.
    ARRET_SERVEUR.clear()

    # 2. Création du socket d'écoute TCP
    serveur = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    serveur.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    try:
        # Association du socket à l'adresse et au port choisis.
        serveur.bind((HOST, port))

        # Mise en écoute des connexions entrantes.
        serveur.listen()

        # Délai d'attente permettant de vérifier périodiquement
        # si une demande d'arrêt a été signalée.
        serveur.settimeout(0.5)

        print("==================================================")
        print("[DEMARRAGE] Serveur TCP")
        print(f"[ECOUTE] {HOST}:{port}")
        print("==================================================")

        # 3. Boucle principale d'acceptation des connexions
        while not ARRET_SERVEUR.is_set():

            try:
                socket_client, adresse_client = serveur.accept()

            except socket.timeout:
                # Aucun client en attente : vérifier l'arrêt.
                continue

            # Chaque client est traité dans son propre thread.
            thread = threading.Thread(
                target=gerer_client,
                args=(
                    socket_client,
                    adresse_client,
                    fonctions
                ),
                daemon=True
            )

            thread.start()

        print("[ARRET] Demande d'arrêt du serveur reçue.")

    except KeyboardInterrupt:
        print("\n[ARRET] Arrêt demandé par l'opérateur.")

    finally:
        # Fermeture du socket d'écoute.
        serveur.close()
        print("[ARRET] Socket d'écoute fermé.")


