from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os
import openai
import json

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
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Tu es Askely, un assistant intelligent et sympathique."},
                {"role": "user", "content": texte}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Erreur OpenAI :", e)
        return "❌ Erreur avec l'intelligence artificielle."

creer_table()

@app.route("/", methods=["GET"])
def home():
    return "Askely Agent is running.", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    utilisateur_id = request.values.get("From", "")
    response = MessagingResponse()
    msg = response.message()

    # 🔍 Détection des coordonnées géographiques (WhatsApp envoie un JSON séparé)
    lat = request.values.get("Latitude")
    lng = request.values.get("Longitude")
    if lat and lng:
        msg.body(f"📍 Merci ! Localisation reçue : {lat}, {lng}. Nous recherchons les options de transport autour de vous.")
        return str(response)

    if incoming_msg.lower() in ["bonjour", "salut", "hello", "menu", "start"]:
        menu = (
            "👋 Bienvenue chez *Askely* !\n"
            "Gagnez des *points* à chaque avis ✨\n\n"
            "1️⃣ Évaluer un vol ✈️\n"
            "2️⃣ Évaluer un programme de fidélité 🛫\n"
            "3️⃣ Évaluer un hôtel 🏨\n"
            "4️⃣ Évaluer un restaurant 🍽️\n"
            "5️⃣ Voir tous les avis 🗂️\n"
            "6️⃣ Mon profil 👤\n"
            "7️⃣ Réserver un transport 🚕\n"
            "8️⃣ Autre question ❓\n\n"
            "📌 Répondez avec *le chiffre* de votre choix."
        )
        msg.body(menu)
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

        profil = f"👤 *Ton profil Askely*\n\n🪙 Points : {points}\n\n📝 *Tes dernières évaluations :*\n"
        for eval in evaluations:
            profil += f"\n• {eval[0].capitalize()} – {eval[1]} – {eval[2]} – {format_etoiles(eval[3])}"
        msg.body(profil)
        return str(response)

    if incoming_msg == "5":
        conn = sqlite3.connect("askely.db")
        c = conn.cursor()
        c.execute("SELECT type, nom, date, note, commentaire FROM evaluations ORDER BY id DESC LIMIT 10")
        evaluations = c.fetchall()
        conn.close()

        avis = "🗂️ *Derniers avis de la communauté Askely :*\n"
        for e in evaluations:
            avis += f"\n• {e[0].capitalize()} – {e[1]} ({e[2]}) – {format_etoiles(e[3])}\n\"{e[4]}\""
        msg.body(avis)
        return str(response)

    if incoming_msg == "1":
        msg.body("✈️ Pour évaluer un vol, envoie les infos sous cette forme :\n\nNom de la compagnie\nDate du vol\nNote sur 5\nTon commentaire")
        return str(response)

    if incoming_msg == "2":
        msg.body("🎁 Pour évaluer un programme de fidélité, envoie les infos sous cette forme :\n\nNom du programme\nDate de ton expérience\nNote sur 5\nTon commentaire")
        return str(response)

    if incoming_msg == "3":
        msg.body("🏨 Pour évaluer un hôtel, envoie les infos sous cette forme :\n\nNom de l'hôtel\nDate de ton séjour\nNote sur 5\nTon commentaire")
        return str(response)

    if incoming_msg == "4":
        msg.body("🍽️ Pour évaluer un restaurant, envoie les infos sous cette forme :\n\nNom du restaurant\nDate de ta visite\nNote sur 5\nTon commentaire")
        return str(response)

    if incoming_msg == "7":
        msg.body("🚕 Pour réserver un transport, partage ta position sur WhatsApp (icône 📎 ➤ Position) pour que nous puissions détecter ta ville de départ.")
        return str(response)

    # Traitement des évaluations
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
                return str(response)
            except:
                msg.body("❌ Format invalide. Vérifie que tu envoies bien :\nNom\nDate\nNote (1-5)\nCommentaire")
                return str(response)

    # Fallback IA
    rep = reponse_gpt(incoming_msg)
    msg.body(rep)
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
