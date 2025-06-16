
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os
import openai

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Création des tables
def creer_tables():
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (
        id TEXT PRIMARY KEY,
        points INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utilisateur_id TEXT,
        type TEXT,
        nom TEXT,
        date TEXT,
        note INTEGER,
        commentaire TEXT
    )""")
    conn.commit()
    conn.close()

# Attribution de points
def ajouter_points(utilisateur_id, points):
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO utilisateurs (id, points) VALUES (?, 0)", (utilisateur_id,))
    c.execute("UPDATE utilisateurs SET points = points + ? WHERE id = ?", (points, utilisateur_id))
    conn.commit()
    conn.close()

# Enregistrement d'une évaluation
def ajouter_evaluation(utilisateur_id, eval_type, nom, date, note, commentaire):
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("INSERT INTO evaluations (utilisateur_id, type, nom, date, note, commentaire) VALUES (?, ?, ?, ?, ?, ?)",
              (utilisateur_id, eval_type, nom, date, note, commentaire))
    conn.commit()
    conn.close()
    ajouter_points(utilisateur_id, get_points_for_type(eval_type))

def get_points_for_type(eval_type):
    return {
        "vol": 10,
        "hôtel": 7,
        "restaurant": 5,
        "fidélité": 10
    }.get(eval_type, 0)

def format_etoiles(note):
    return "⭐️" * note + "☆" * (5 - note)

# Requête GPT pour les demandes libres
def reponse_gpt(texte):
    try:
        completion = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Tu es Askely, un assistant de voyage intelligent et sympathique."},
                {"role": "user", "content": texte}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("Erreur GPT :", e)
        return "❌ Erreur avec l'intelligence artificielle."

# Initialisation
creer_tables()

@app.route("/", methods=["GET"])
def accueil():
    return "✅ Askely est en ligne."

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    utilisateur_id = request.values.get("From", "")
    latitude = request.values.get("Latitude")
    longitude = request.values.get("Longitude")

    response = MessagingResponse()
    msg = response.message()

    if latitude and longitude:
        msg.body(f"📍 Merci ! Localisation reçue : {latitude}, {longitude}.")
        return str(response)

    if incoming_msg.lower() in ["bonjour", "salut", "hello", "menu", "start"]:
        msg.body(
            "👋 Bienvenue chez *Askely* !
"
            "Gagnez des *points* à chaque avis ✨

"
            "1️⃣ Évaluer un vol ✈️
"
            "2️⃣ Évaluer un programme de fidélité 🛫
"
            "3️⃣ Évaluer un hôtel 🏨
"
            "4️⃣ Évaluer un restaurant 🍽️
"
            "5️⃣ Voir tous les avis 🗂️
"
            "6️⃣ Mon profil 👤
"
            "7️⃣ Transport ou Taxi 🚖
"
            "8️⃣ Autre question ❓

"
            "📌 Répondez avec *le chiffre* de votre choix."
        )
        return str(response)

    if incoming_msg == "6":
        conn = sqlite3.connect("askely.db")
        c = conn.cursor()
        c.execute("SELECT points FROM utilisateurs WHERE id = ?", (utilisateur_id,))
        row = c.fetchone()
        points = row[0] if row else 0

        c.execute("SELECT type, nom, date, note FROM evaluations WHERE utilisateur_id = ? ORDER BY id DESC LIMIT 5", (utilisateur_id,))
        evaluations = c.fetchall()
        conn.close()

        profil = f"👤 *Ton profil Askely*

🪙 Points : {points}

📝 *Tes dernières évaluations :*
"
        for eval in evaluations:
            profil += f"
• {eval[0].capitalize()} – {eval[1]} – {eval[2]} – {format_etoiles(eval[3])}"
        msg.body(profil)
        return str(response)

    if incoming_msg == "5":
        conn = sqlite3.connect("askely.db")
        c = conn.cursor()
        c.execute("SELECT type, nom, date, note, commentaire FROM evaluations ORDER BY id DESC LIMIT 10")
        evaluations = c.fetchall()
        conn.close()

        avis = "🗂️ *Derniers avis de la communauté Askely :*
"
        for e in evaluations:
            avis += f"
• {e[0].capitalize()} – {e[1]} ({e[2]}) – {format_etoiles(e[3])}
"{e[4]}""
        msg.body(avis)
        return str(response)

    if incoming_msg == "1":
        msg.body("✈️ Pour évaluer un vol, envoie :

Nom de la compagnie
Date du vol
Note sur 5
Ton commentaire")
        return str(response)

    if incoming_msg == "2":
        msg.body("🎁 Pour évaluer un programme de fidélité, envoie :

Nom du programme
Date
Note sur 5
Ton commentaire")
        return str(response)

    if incoming_msg == "3":
        msg.body("🏨 Pour évaluer un hôtel, envoie :

Nom de l'hôtel
Date
Note sur 5
Ton commentaire")
        return str(response)

    if incoming_msg == "4":
        msg.body("🍽️ Pour évaluer un restaurant, envoie :

Nom du restaurant
Date
Note sur 5
Ton commentaire")
        return str(response)

    if incoming_msg == "7":
        msg.body("🚕 Pour réserver un taxi ou un transport, veuillez partager votre *localisation actuelle* ou tapez votre *ville de départ*.")
        return str(response)

    lignes = incoming_msg.split("
")
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
                commentaire = "
".join(lignes[3:])
                ajouter_evaluation(utilisateur_id, eval_type, nom, date, note, commentaire)
                msg.body(f"✅ Merci ! Ton avis a été enregistré pour *{eval_type}* avec {note}⭐️.
+{get_points_for_type(eval_type)} points gagnés 🪙.")
                return str(response)
            except:
                msg.body("❌ Format invalide. Vérifie que tu envoies bien :
Nom
Date
Note (1-5)
Commentaire")
                return str(response)

    # GPT pour demandes libres
    rep = reponse_gpt(incoming_msg)
    msg.body(rep)
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
