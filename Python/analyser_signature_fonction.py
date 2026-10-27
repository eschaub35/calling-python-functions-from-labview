#%%

# Ce code analyse une fonction Python définie dans un fichier externe, identifié par son chemin et son nom.
# Il récupère sa signature et extrait les informations relatives à ses paramètres
# (noms, valeurs par défaut, annotations de type et catégories),
# ainsi que l'annotation éventuelle de son type de retour.
# Les informations sont regroupées dans un dictionnaire, puis affichées de manière lisible dans la console.
# Les éventuelles erreurs de chargement ou d'analyse sont interceptées et affichées.


import importlib.util
import inspect


def analyser_fonction(chemin_module, nom_fonction):
    """
    Analyse une fonction Python définie dans un fichier .py.

    Paramètres
    ----------
    chemin_module : str
        Chemin complet du fichier Python à charger.

    nom_fonction : str
        Nom de la fonction à analyser.

    Retour
    ------
    dict
        Dictionnaire contenant le nom de la fonction,
        ses paramètres, leurs valeurs par défaut,
        leurs annotations et l'annotation du retour.
    """

    # ---------------------------------------------------------
    # 1. Charger le module depuis son chemin
    # ---------------------------------------------------------

    # Crée une spécification décrivant comment charger le fichier.
    # "module_temp" est le nom attribué au module chargé.
    # chemin_module indique le chemin du fichier .py.
    spec = importlib.util.spec_from_file_location(
        "module_temp",
        chemin_module
    )

    # Vérifie que la spécification a été créée correctement
    # et qu'un chargeur est disponible pour exécuter le module.
    # Si ce n'est pas le cas, signale une erreur de chargement.
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Impossible de charger le module : {chemin_module}"
        )

    # Crée un objet module à partir de la spécification.
    # Le code du fichier n'est pas encore exécuté à cette étape.
    module = importlib.util.module_from_spec(spec)

    # Exécute le code du fichier Python dans l'objet module.
    # Les fonctions, classes et variables définies dans le fichier
    # deviennent alors accessibles via cet objet.
    spec.loader.exec_module(module)

    # ---------------------------------------------------------
    # 2. Vérifier que la fonction existe
    # ---------------------------------------------------------

    # Vérifie si le module possède un attribut portant le nom
    # demandé. Cet attribut peut être une fonction, une variable,
    # une classe ou un autre objet.
    if not hasattr(module, nom_fonction):
        raise AttributeError(
            f"La fonction '{nom_fonction}' "
            f"n'existe pas dans '{chemin_module}'"
        )

    # Récupère l'objet associé au nom fourni.
    # Par exemple, si nom_fonction vaut "traiter_images",
    # cela revient à récupérer module.traiter_images.
    fonction = getattr(module, nom_fonction)

    # Vérifie que l'objet peut être appelé avec des parenthèses.
    # Cette vérification ne garantit pas qu'il s'agit d'une
    # fonction ordinaire : une classe peut aussi être appelable.
    if not callable(fonction):
        raise TypeError(
            f"'{nom_fonction}' existe mais n'est pas appelable"
        )

    # ---------------------------------------------------------
    # 3. Récupérer la signature
    # ---------------------------------------------------------

    # Analyse la définition de la fonction sans l'exécuter.
    # La signature contient notamment :
    # - les noms des paramètres ;
    # - leurs valeurs par défaut éventuelles ;
    # - leurs annotations éventuelles ;
    # - l'annotation éventuelle du type de retour.
    signature = inspect.signature(fonction)

    # ---------------------------------------------------------
    # 4. Analyser les paramètres
    # ---------------------------------------------------------

    # Initialise une liste vide qui contiendra un dictionnaire
    # par paramètre de la fonction.
    parametres = []

    # Parcourt les paramètres dans leur ordre de déclaration.
    # Chaque élément "param" est un objet inspect.Parameter.
    for param in signature.parameters.values():

        # -----------------------------------------------------
        # 4.1. Déterminer la valeur par défaut
        # -----------------------------------------------------

        # inspect.Parameter.empty indique qu'aucune valeur
        # par défaut n'a été définie dans la signature.
        # On stocke alors None et on précise que le paramètre
        # ne possède pas de valeur par défaut.
        if param.default is inspect.Parameter.empty:
            valeur_defaut = None
            a_une_valeur_par_defaut = False

        else:
            # Une valeur par défaut existe.
            # On la conserve sous sa forme Python native :
            # par exemple 0.5 reste un float et "test" une str.
            valeur_defaut = param.default
            a_une_valeur_par_defaut = True

        # -----------------------------------------------------
        # 4.2. Récupérer l'annotation du paramètre
        # -----------------------------------------------------

        # Une annotation est une indication de type facultative,
        # écrite dans la définition de la fonction.
        # Exemple : def calculer(x: float).
        #
        # Si aucune annotation n'existe, on utilise None.
        if param.annotation is inspect.Parameter.empty:
            annotation = None

        else:
            # Convertit l'objet annotation en chaîne de caractères.
            # Exemple : float devient "<class 'float'>".
            # Cette conversion facilite l'affichage et le transport
            # des informations, mais ne garantit pas un type simple.
            annotation = str(param.annotation)

        # -----------------------------------------------------
        # 4.3. Enregistrer les informations du paramètre
        # -----------------------------------------------------

        # Ajoute un dictionnaire à la liste "parametres".
        # Chaque clé identifie une propriété du paramètre.
        parametres.append({

            # Nom du paramètre dans la définition de la fonction.
            "nom": param.name,

            # Valeur par défaut, ou None si elle est absente.
            "defaut": valeur_defaut,

            # Booléen permettant de distinguer :
            # - un paramètre sans valeur par défaut ;
            # - un paramètre dont la valeur par défaut est None.
            "a_une_valeur_par_defaut": a_une_valeur_par_defaut,

            # Annotation du paramètre sous forme de texte,
            # ou None si aucune annotation n'est déclarée.
            "annotation": annotation,

            # Catégorie du paramètre :
            # positionnel, mot-clé, *args, **kwargs, etc.
            "kind": str(param.kind)
        })

    # ---------------------------------------------------------
    # 5. Analyser le type de retour
    # ---------------------------------------------------------

    # Vérifie si la fonction déclare une annotation de retour.
    # Exemple : def calculer(x: float) -> float.
    if signature.return_annotation is inspect.Signature.empty:

        # Aucune annotation de retour n'a été déclarée.
        # None représente ici l'absence d'annotation.
        type_retour = None
        retour_annote = False

    else:
        # Une annotation de retour existe.
        # On la convertit en chaîne de caractères.
        type_retour = str(signature.return_annotation)
        retour_annote = True

    # ---------------------------------------------------------
    # 6. Construire le résultat final
    # ---------------------------------------------------------

    # Regroupe toutes les informations dans un dictionnaire.
    # Ce dictionnaire peut ensuite être consulté par le programme
    # appelant ou converti en JSON si ses valeurs sont compatibles.
    resultat = {

        # Nom de la fonction analysée.
        "fonction": nom_fonction,

        # Chemin du fichier Python qui a été chargé.
        "module": chemin_module,

        # Liste des dictionnaires décrivant chaque paramètre.
        "parametres": parametres,

        # Annotation de retour sous forme de texte,
        # ou None si aucune annotation n'est déclarée.
        "type_retour": type_retour,

        # Indique si une annotation de retour est présente.
        "retour_annote": retour_annote
    }

    # Renvoie le dictionnaire au programme appelant.
    # Contrairement à print(), return permet de récupérer
    # et de réutiliser les données dans la suite du programme.
    return resultat



# =============================================================
# Exemple d'utilisation
# =============================================================
chemin = r"D:\Home\eschaub\Documents\DYNAMIC MICROSCOPY\DM Image Analysis\DCM\Corr_lib.py"

nom_fonction = "calc_mean_cACF_rejOtl"


try:

    resultat = analyser_fonction(
        chemin,
        nom_fonction
    )

    print()
    print("========================================")
    print("Analyse de la fonction")
    print("========================================")

    print(f"Fonction : {resultat['fonction']}")
    print(f"Module   : {resultat['module']}")

    print()
    print("Paramètres :")

    for param in resultat["parametres"]:

        print(f"  - {param['nom']}")

        if param["a_une_valeur_par_defaut"]:
            print(f"      défaut     : {param['defaut']!r}")
        else:
            print("      défaut     : aucune")

        print(f"      annotation : {param['annotation']}")
        print(f"      kind       : {param['kind']}")

    print()

    if resultat["retour_annote"]:
        print(
            f"Type de retour : {resultat['type_retour']}"
        )
    else:
        print(
            "Type de retour : non indiqué"
        )

except Exception as e:

    print()
    print("ERREUR :")
    print(e)
