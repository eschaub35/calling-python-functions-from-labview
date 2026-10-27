import socket
import struct
import json
import threading


# ============================================================
# CONFIGURATION
# ============================================================

HOST = 'localhost'
PORT = 5000
# Événement permettant de demander l'arrêt du serveur
ARRET_SERVEUR = threading.Event()


# Taille maximale autorisée pour éviter des allocations
# accidentelles de plusieurs Go en cas de paquet corrompu.
TAILLE_JSON_MAX = 10 * 1024 * 1024          # 10 Mo
TAILLE_BINAIRE_MAX = 1024 * 1024 * 1024     # 1 Go


# ============================================================
# OUTILS TCP
# ============================================================

def recevoir_exactement(sock, taille):
    """
    Reçoit exactement 'taille' octets.

    TCP est un flux : un seul recv() ne garantit pas de recevoir
    toutes les données demandées.
    """

    donnees = bytearray()

    while len(donnees) < taille:

        a_lire = min(taille - len(donnees), 65536)

        morceau = sock.recv(a_lire)

        if not morceau:
            raise ConnectionError(
                "Le client s'est déconnecté prématurément."
            )

        donnees.extend(morceau)

    return bytes(donnees)


def recevoir_paquet(sock):
    """
    Reçoit un paquet suivant le protocole :

        [4 octets taille JSON]
        [4 octets taille binaire]
        [JSON]
        [données binaires]

    Retourne :

        metadonnees
        donnees_binaires
    """

    # --------------------------------------------------------
    # 1. En-tête
    # --------------------------------------------------------

    header = recevoir_exactement(sock, 8)

    taille_json, taille_binaire = struct.unpack(
        '>II',
        header
    )

    print(
        f"[RECEPTION] "
        f"JSON = {taille_json} octets | "
        f"Binaire = {taille_binaire} octets"
    )

    # --------------------------------------------------------
    # 2. Vérification des tailles
    # --------------------------------------------------------

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
    # 3. JSON
    # --------------------------------------------------------

    json_brut = recevoir_exactement(
        sock,
        taille_json
    )

    # LabVIEW / Windows :
    # on conserve cp1252 comme dans ton serveur actuel.
    json_texte = json_brut.decode(
        'utf-8',
        errors='replace'
    )

    metadonnees = json.loads(json_texte)

    # --------------------------------------------------------
    # 4. Données binaires
    # --------------------------------------------------------

    donnees_binaires = recevoir_exactement(
        sock,
        taille_binaire
    )

    return metadonnees, donnees_binaires


def envoyer_paquet(sock, metadonnees, donnees_binaires=b''):
    """
    Envoie un paquet suivant le protocole :

        [4 octets taille JSON]
        [4 octets taille binaire]
        [JSON]
        [données binaires]
    """

    # --------------------------------------------------------
    # 1. Conversion du JSON en bytes
    # --------------------------------------------------------

    json_texte = json.dumps(
        metadonnees,
        ensure_ascii=False,
        separators=(',', ':')
    )

    json_brut = json_texte.encode('utf-8')

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
# FONCTIONS APPELABLES PAR LABVIEW
# ============================================================

def fonction_test(metadonnees, donnees_binaires):
    """
    Exemple de fonction.

    Reçoit le JSON et les données binaires.
    Renvoie un JSON et éventuellement des données binaires.
    """

    print("[FONCTION] test")

    print(
        f"    JSON reçu : {metadonnees}"
    )

    print(
        f"    Données binaires reçues : "
        f"{len(donnees_binaires)} octets"
    )

    # Exemple de réponse
    # reponse_json = {
    #     "fonction": "test",
    #     "statut": "OK",
    #     "message": "Fonction exécutée avec succès",
    #     "taille_binaire_recue": len(donnees_binaires)
    # }
    reponse_json = metadonnees
    # Pour l'exemple, on renvoie exactement les mêmes
    # données binaires que celles reçues.
    reponse_binaire = donnees_binaires

    return reponse_json, reponse_binaire


def fonction_traiter_images(metadonnees, donnees_binaires):
    """
    Exemple d'une deuxième fonction.

    IMPORTANT :
    le serveur ne suppose pas ici que les données binaires
    sont nécessairement des images.

    C'est cette fonction qui déciderait éventuellement
    comment les interpréter.
    """

    print("[FONCTION] traiter_images")

    print(
        f"    Métadonnées : {metadonnees}"
    )

    print(
        f"    Données binaires : "
        f"{len(donnees_binaires)} octets"
    )

    # --------------------------------------------------------
    # Ici viendra ton traitement réel
    # --------------------------------------------------------

    reponse_json = {
        "fonction": "traiter_images",
        "statut": "OK",
        "taille_binaire_recue": len(donnees_binaires)
    }

    # Exemple : retourner les données telles quelles
    reponse_binaire = donnees_binaires

    return reponse_json, reponse_binaire

def stop_server(metadonnees, donnees_binaires):
    """
    Demande l'arrêt du serveur TCP.

    Cette fonction est appelée par LabVIEW comme les autres fonctions.
    Le serveur envoie d'abord la réponse à LabVIEW, puis s'arrête.
    """

    print("[FONCTION] stop_server")
    print("    Demande d'arrêt du serveur reçue.")

    # Demande l'arrêt du serveur
    ARRET_SERVEUR.set()
    

    reponse_json = {
        "fonction": "stop_server",
        "statut": "OK",
        "message": "Arrêt du serveur demandé."
    }

    reponse_binaire = b''

    return reponse_json, reponse_binaire

# ============================================================
# DISPATCHER
# ============================================================

def executer_fonction(metadonnees, donnees_binaires):
    """
    Détermine quelle fonction exécuter à partir du JSON.

    Le nom de la fonction doit être contenu dans :

        metadonnees["fonction"]
    """

    # --------------------------------------------------------
    # Vérification
    # --------------------------------------------------------

    if "fonction" not in metadonnees:

        raise ValueError(
            "Le JSON ne contient pas le champ 'fonction'."
        )

    nom_fonction = metadonnees["fonction"]

    print(
        f"[FONCTION DEMANDEE] {nom_fonction}"
    )

    # --------------------------------------------------------
    # Table des fonctions disponibles
    # --------------------------------------------------------

    fonctions = {
        "test":
            fonction_test,

        "traiter_images":
            fonction_traiter_images,

        "stop_server":
            stop_server,
    }

    # --------------------------------------------------------
    # Recherche de la fonction
    # --------------------------------------------------------

    if nom_fonction not in fonctions:

        raise ValueError(
            f"Fonction inconnue : '{nom_fonction}'"
        )

    fonction = fonctions[nom_fonction]

    # --------------------------------------------------------
    # Exécution
    # --------------------------------------------------------

    return fonction(
        metadonnees,
        donnees_binaires
    )


# ============================================================
# GESTION D'UN CLIENT
# ============================================================

def gerer_client(socket_client, adresse_client):

    print(
        f"[CONNEXION] Nouveau client : "
        f"{adresse_client}"
    )

    try:

        while True:

            # =================================================
            # RÉCEPTION DE LA REQUÊTE
            # =================================================

            metadonnees, donnees_binaires = recevoir_paquet(
                socket_client
            )

            print(
                f"[JSON] {metadonnees}"
            )

            print(
                f"[BINAIRE] "
                f"{len(donnees_binaires)} octets"
            )

            # =================================================
            # EXÉCUTION DE LA FONCTION DEMANDÉE
            # =================================================

            try:

                reponse_json, reponse_binaire = \
                    executer_fonction(
                        metadonnees,
                        donnees_binaires
                    )

            except Exception as e:

                # ---------------------------------------------
                # Erreur dans la fonction appelée
                # ---------------------------------------------

                print(
                    f"[ERREUR FONCTION] {e}"
                )

                reponse_json = {
                    "statut": "ERREUR",
                    "message": str(e)
                }

                reponse_binaire = b''

            # =================================================
            # ENVOI DE LA RÉPONSE
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


    except ConnectionError as e:

        print(
            f"[DECONNEXION] "
            f"{adresse_client} : {e}"
        )

    except json.JSONDecodeError as e:

        print(
            f"[ERREUR JSON] "
            f"JSON invalide : {e}"
        )

    except Exception as e:

        print(
            f"[ERREUR GENERALE] "
            f"{adresse_client} : {e}"
        )

    finally:

        socket_client.close()

        print(
            f"[DISCONNECT] "
            f"Fin de session : {adresse_client}"
        )

# ============================================================
# DÉMARRAGE DU SERVEUR
# ============================================================

def demarrer_serveur():

    serveur = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    # Permet de réutiliser le port immédiatement
    # après un redémarrage.
    serveur.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    serveur.bind(
        (HOST, PORT)
    )

    serveur.listen()

    print(
        "=================================================="
    )

    print(
        "[DEMARRAGE] Serveur TCP"
    )

    print(
        f"[ECOUTE] {HOST}:{PORT}"
    )

    print(
        "=================================================="
    )


    
    try:
        # On utilise un timeout pour pouvoir vérifier régulièrement
        # si une demande d'arrêt a été reçue.
        serveur.settimeout(0.5)

        while not ARRET_SERVEUR.is_set():

            try:
                socket_client, adresse_client = serveur.accept()

            except socket.timeout:
                # Permet de revenir tester ARRET_SERVEUR
                continue

            thread = threading.Thread(
                target=gerer_client,
                args=(
                    socket_client,
                    adresse_client
                ),
                daemon=True
            )

            thread.start()

    except KeyboardInterrupt:
        print(
            "\n[ARRET] "
            "Arrêt demandé par l'opérateur."
        )

    finally:
        serveur.close()

        print(
            "[ARRET] Serveur fermé."
        )

#%%
# MARK: Start server
# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================
ARRET_SERVEUR.clear()
if __name__ == "__main__":

    demarrer_serveur()


# %%
