
from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("askely.db")
    conn.row_factory = sqlite3.Row
    return conn

def ask_gpt(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "❌ Erreur IA : " + str(e)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS utilisateurs (id TEXT PRIMARY KEY, pseudo TEXT, numero_hash TEXT, points INTEGER DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS evaluations_vol (id INTEGER PRIMARY KEY AUTOINCREMENT, compagnie TEXT, numero_vol TEXT, date_vol TEXT, note INTEGER, commentaire TEXT, user_id TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS evaluations_fidelite (id INTEGER PRIMARY KEY AUTOINCREMENT, programme TEXT, compagnie TEXT, note_accumulation INTEGER, note_utilisation INTEGER, note_avantages INTEGER, commentaire TEXT, user_id TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS evaluations_hotel (id INTEGER PRIMARY KEY AUTOINCREMENT, nom_hotel TEXT, ville TEXT, date TEXT, note INTEGER, commentaire TEXT, user_id TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS evaluations_restaurant (id INTEGER PRIMARY KEY AUTOINCREMENT, nom_restaurant TEXT, ville TEXT, date TEXT, note INTEGER, commentaire TEXT, user_id TEXT)")
    conn.commit()
    conn.close()

@app.route("/", methods=["GET"])
def home():
    return "✅ Askely agent est en ligne"

@app.route("/avis", methods=["GET"])
def afficher_avis():
    conn = get_db_connection()
    cur = conn.cursor()
    vols = cur.execute("SELECT * FROM evaluations_vol ORDER BY id DESC LIMIT 10").fetchall()
    hotels = cur.execute("SELECT * FROM evaluations_hotel ORDER BY id DESC LIMIT 10").fetchall()
    restos = cur.execute("SELECT * FROM evaluations_restaurant ORDER BY id DESC LIMIT 10").fetchall()
    fid = cur.execute("SELECT * FROM evaluations_fidelite ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    return jsonify({
        "vols": [dict(x) for x in vols],
        "hotels": [dict(x) for x in hotels],
        "restaurants": [dict(x) for x in restos],
        "fidelite": [dict(x) for x in fid],
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    msg_txt = request.values.get("Body", "").strip()
    user_number = request.values.get("From", "").replace("whatsapp:", "")
    response = MessagingResponse()
    msg = response.message()
    conn = get_db_connection()
    cur = conn.cursor()

    user = cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_number,)).fetchone()
    if not user:
        cur.execute("INSERT INTO utilisateurs (id, pseudo, numero_hash, points) VALUES (?, ?, ?, ?)", (user_number, f"user_{user_number[-4:]}", user_number, 0))
        conn.commit()
        msg.body(menu_principal())
        return str(response)

    if msg_txt == "1":
        msg.body("✈️ Pour évaluer un vol, envoie :
Compagnie, Numéro de vol, Date, Note (1-5), Commentaire")
    elif msg_txt.startswith("Compagnie"):
        parts = msg_txt.split(",")
        if len(parts) >= 5:
            compagnie, numero_vol, date, note, commentaire = [p.strip() for p in parts]
            cur.execute("INSERT INTO evaluations_vol (compagnie, numero_vol, date_vol, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (compagnie, numero_vol, date, int(note), commentaire, user_number))
            cur.execute("UPDATE utilisateurs SET points = points + 10 WHERE id = ?", (user_number,))
            conn.commit()
            msg.body("✅ Merci pour ton avis sur ce vol. Tu gagnes 10 points Askely 🪙")
    elif msg_txt == "2":
        msg.body("🛂 Pour évaluer un programme de fidélité, envoie :
Programme, Compagnie, Note accumulation, Note utilisation, Note avantages, Commentaire")
    elif msg_txt.startswith("Programme"):
        parts = msg_txt.split(",")
        if len(parts) >= 6:
            programme, compagnie, acc, util, adv, commentaire = [p.strip() for p in parts]
            cur.execute("INSERT INTO evaluations_fidelite (programme, compagnie, note_accumulation, note_utilisation, note_avantages, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (programme, compagnie, int(acc), int(util), int(adv), commentaire, user_number))
            cur.execute("UPDATE utilisateurs SET points = points + 6 WHERE id = ?", (user_number,))
            conn.commit()
            msg.body("🛂 Avis de programme enregistré. Tu gagnes 6 points Askely 🪙")
    elif msg_txt == "3":
        msg.body("🏨 Pour évaluer un hôtel, envoie :
Nom, Ville, Date, Note (1-5), Commentaire")
    elif msg_txt.startswith("Nom") and "Hôtel" in msg_txt:
        parts = msg_txt.split(",")
        if len(parts) >= 5:
            nom, ville, date, note, commentaire = [p.strip() for p in parts]
            cur.execute("INSERT INTO evaluations_hotel (nom_hotel, ville, date, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (nom, ville, date, int(note), commentaire, user_number))
            cur.execute("UPDATE utilisateurs SET points = points + 7 WHERE id = ?", (user_number,))
            conn.commit()
            msg.body("🏨 Merci pour ton retour hôtelier. Tu gagnes 7 points Askely 🪙")
    elif msg_txt == "4":
        msg.body("🍽️ Pour évaluer un restaurant, envoie :
Nom, Ville, Date, Note (1-5), Commentaire")
    elif msg_txt.startswith("Nom") and "Restau" in msg_txt:
        parts = msg_txt.split(",")
        if len(parts) >= 5:
            nom, ville, date, note, commentaire = [p.strip() for p in parts]
            cur.execute("INSERT INTO evaluations_restaurant (nom_restaurant, ville, date, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (nom, ville, date, int(note), commentaire, user_number))
            cur.execute("UPDATE utilisateurs SET points = points + 5 WHERE id = ?", (user_number,))
            conn.commit()
            msg.body("🍽️ Merci pour ton avis resto ! Tu gagnes 5 points Askely 🪙")
    elif msg_txt == "5":
        profil = cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_number,)).fetchone()
        msg.body(f"👤 Ton profil Askely :
Pseudo : {profil['pseudo']}
Points : {profil['points']} 🪙")
    else:
        gpt_response = ask_gpt(msg_txt)
        msg.body("🤖 Réponse IA :
" + gpt_response)

    conn.close()
    return str(response)

def menu_principal():
    return (
        "👋 Bienvenue sur Askely 🌍
"
        "Gagne des points en évaluant tes expériences ✈️🏨🍽️

"
        "1️⃣ Évaluer un vol
"
        "2️⃣ Évaluer un programme de fidélité
"
        "3️⃣ Évaluer un hôtel
"
        "4️⃣ Évaluer un restaurant
"
        "5️⃣ Mon profil

"
        "Ou pose ta question librement 🤖"
    )

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
