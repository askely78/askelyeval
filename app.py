from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os
import openai

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

def creer_table():
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

def ajouter_points(utilisateur_id, points):
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO utilisateurs (id, points) VALUES (?, 0)", (utilisateur_id,))
    c.execute("UPDATE utilisateurs SET points = points + ? WHERE id = ?", (points, utilisateur_id))
    conn.commit()
    conn.close()

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

def reponse_gpt(texte):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Tu es Askely, un assistant intelligent et sympathique."},
                {"role": "user", "content": texte}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Erreur OpenAI :", e)
        return f"❌ Une erreur est survenue : {e}"

creer_table()

@app.route("/", methods=["GET"])
def home():
    return "Askely Agent is running.", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    utilisateur_id = request.values.get("From", "")
    latitude = request.values.get("Latitude", "")
    longitude = request.values.get("Longitude", "")
    response = MessagingResponse()
    msg = response.message()

    if latitude and longitude:
        msg.body(f"📍 Merci ! Localisation reçue : {latitude}, {longitude}.")
        return str(response)

    if incoming_msg.lower() in ["bonjour", "salut", "hello", "menu", "start"]:
        menu = (
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
            "7️⃣ Autre question ❓

"
            "📌 Répondez avec *le chiffre* de votre choix."
        )
        msg.body(menu)
        return str(response)

    # autres fonctions (profil, avis, évaluation etc.) non répétées ici pour clarté
    msg.body("🧠 Je n’ai pas compris. Réponds par un chiffre du menu ou pose ta question.")
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)