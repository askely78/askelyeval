from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import openai
import os

app = Flask(__name__)

# Configuration de l'API OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Connexion DB
def get_db_connection():
    conn = sqlite3.connect("askely.db")
    conn.row_factory = sqlite3.Row
    return conn

# Création des tables si elles n'existent pas
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilisateur_id TEXT,
            type TEXT,
            nom TEXT,
            date TEXT,
            note INTEGER,
            commentaire TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()
# Calcul des points selon le type
def get_points_for_type(eval_type):
    if eval_type == "fidélité":
        return 10
    return 5

# Ajout d'une évaluation
def ajouter_evaluation(utilisateur_id, eval_type, nom, date, note, commentaire):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO evaluations (utilisateur_id, type, nom, date, note, commentaire)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (utilisateur_id, eval_type, nom, date, note, commentaire))
    cur.execute('''
        INSERT OR IGNORE INTO utilisateurs (id, points) VALUES (?, 0)
    ''', (utilisateur_id,))
    cur.execute('''
        UPDATE utilisateurs SET points = points + ? WHERE id = ?
    ''', (get_points_for_type(eval_type), utilisateur_id))
    conn.commit()
    conn.close()

# Récupérer le profil utilisateur
def get_profil(utilisateur_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT points FROM utilisateurs WHERE id = ?", (utilisateur_id,))
    row = cur.fetchone()
    points = row["points"] if row else 0
    cur.execute("SELECT * FROM evaluations WHERE utilisateur_id = ? ORDER BY id DESC LIMIT 5", (utilisateur_id,))
    evaluations = cur.fetchall()
    conn.close()
    return points, evaluations
# Récupérer les derniers avis de la communauté
def get_dernier_avis_communautaire():
    conn = get_db_connection()
    cur = conn.cursor()
    types = ["vol", "hôtel", "restaurant", "fidélité"]
    avis = []
    for t in types:
        cur.execute("SELECT * FROM evaluations WHERE type = ? ORDER BY id DESC LIMIT 3", (t,))
        rows = cur.fetchall()
        avis.extend(rows)
    conn.close()
    return avis

# Formater les étoiles
def format_etoiles(note):
    return "⭐️" * int(note)

# Construire la réponse WhatsApp d’accueil
def menu_accueil():
    return (
        "👋 *Bienvenue chez Askely !*\n"
        "Gagnez des points en évaluant vos expériences de voyage.\n\n"
        "🗂️ *Menu d’évaluation :*\n"
        "1️⃣ Évaluer un vol\n"
        "2️⃣ Évaluer un programme de fidélité\n"
        "3️⃣ Évaluer un hôtel\n"
        "4️⃣ Évaluer un restaurant\n"
        "5️⃣ Autre question\n"
        "6️⃣ Mon profil\n"
        "7️⃣ Voir tous les avis\n\n"
        "📌 Tapez le *chiffre* correspondant à votre choix."
    )
# Construction de la réponse avis communauté
def format_avis_communautaires():
    avis = get_dernier_avis_communautaire()
    if not avis:
        return "Aucun avis trouvé pour le moment."
    msg = "📋 *Voici les derniers avis de la communauté Askely :*\n\n"
    for a in avis:
        emoji = "✈️" if a["type"] == "vol" else "🏨" if a["type"] == "hôtel" else "🍽️" if a["type"] == "restaurant" else "🛂"
        msg += f"{emoji} *{a['type'].capitalize()}* – {a['nom']} – {a['date']}\n{format_etoiles(a['note'])}\n\"{a['commentaire']}\"\n\n"
    msg += "🔄 Envoie *mon profil* pour voir ton historique et tes points."
    return msg

# Générer une réponse via GPT
def reponse_gpt(message):
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Tu es un assistant de voyage utile."},
                      {"role": "user", "content": message}],
            max_tokens=100
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return "❌ Erreur IA. Réessaye plus tard."
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    utilisateur_id = request.values.get("From", "")
    msg = MessagingResponse()
    msg_txt = incoming_msg.lower()

    if msg_txt in ["bonjour", "salut", "hello", "start", "menu"]:
        msg.body(menu_accueil())
        return str(msg)

    if msg_txt == "1":
        msg.body(
            "✈️ Askely : Pour évaluer un vol, envoie les infos sous cette forme :\n\n"
            "Nom de la compagnie\nDate du vol\nNuméro du vol\nNote sur 5\nCommentaire"
        )
        return str(msg)

    if msg_txt == "2":
        msg.body(
            "🛂 Askely : Pour évaluer un programme de fidélité, envoie :\n\n"
            "Nom du programme\nDate de l'expérience\nNote sur 5\nCommentaire"
        )
        return str(msg)

    if msg_txt == "3":
        msg.body(
            "🏨 Askely : Pour évaluer un hôtel, envoie :\n\n"
            "Nom de l'hôtel\nDate du séjour\nNote sur 5\nCommentaire"
        )
        return str(msg)

    if msg_txt == "4":
        msg.body(
            "🍽️ Askely : Pour évaluer un restaurant, envoie :\n\n"
            "Nom du restaurant\nDate de la visite\nNote sur 5\nCommentaire"
        )
        return str(msg)

    if msg_txt == "6" or msg_txt == "mon profil":
        points, evaluations = get_profil(utilisateur_id)
        rep = f"👤 *Ton profil Askely*\nPoints : {points}\n\n📌 *Tes 5 dernières évaluations :*\n"
        for e in evaluations:
            rep += f"{e['type'].capitalize()} – {e['nom']} – {e['date']} : {format_etoiles(e['note'])}\n"
        msg.body(rep)
        return str(msg)

    if msg_txt == "7" or "avis" in msg_txt:
        msg.body(format_avis_communautaires())
        return str(msg)
    # Tentative d'analyse automatique
    lignes = incoming_msg.split("\n")
    if len(lignes) >= 4:
        if "vol" in lignes[0].lower():
            eval_type = "vol"
        elif "hôtel" in lignes[0].lower() or "hotel" in lignes[0].lower():
            eval_type = "hôtel"
        elif "restaurant" in lignes[0].lower():
            eval_type = "restaurant"
        elif "skywards" in lignes[0].lower() or "fidélité" in lignes[0].lower() or "miles" in lignes[0].lower():
            eval_type = "fidélité"
        else:
            eval_type = None

        if eval_type:
            try:
                nom = lignes[0]
                date = lignes[1]
                note = int(lignes[2])
                commentaire = "\n".join(lignes[3:])
                ajouter_evaluation(utilisateur_id, eval_type, nom, date, note, commentaire)
                msg.body(f"✅ Merci ! Ton avis a été enregistré pour *{eval_type}* avec {note}⭐️.\n+{get_points_for_type(eval_type)} points gagnés 🪙.")
                return str(msg)
            except:
                msg.body("❌ Format invalide. Vérifie que tu envoies bien :\nNom\nDate\nNote (1-5)\nCommentaire")
                return str(msg)

    # Sinon → GPT
    rep = reponse_gpt(incoming_msg)
    msg.body(rep)
    return str(msg)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
