from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('askely.db')
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (
                    id TEXT PRIMARY KEY,
                    pseudo TEXT,
                    numero_hash TEXT,
                    points INTEGER DEFAULT 0
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS evaluations_fidelite (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER,
                    user_id TEXT,
                    note_accumulation INTEGER,
                    note_utilisation INTEGER,
                    note_avantages INTEGER,
                    commentaire TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS programmes_fidelite (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_programme TEXT,
                    compagnie TEXT
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS evaluations_restaurant (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_restaurant TEXT,
                    ville TEXT,
                    date TEXT,
                    note INTEGER,
                    commentaire TEXT,
                    user_id TEXT
                )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS evaluations_hotel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom_hotel TEXT,
                    ville TEXT,
                    date TEXT,
                    note INTEGER,
                    commentaire TEXT,
                    user_id TEXT
                )''')
    conn.commit()
    conn.close()

init_db()
@app.route("/", methods=["GET"])
def home():
    return "Askely est en ligne ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    user_number = request.values.get("From", "")
    user_id = user_number.replace("whatsapp:", "")
    response = MessagingResponse()
    msg = response.message()
    conn = get_db_connection()
    cur = conn.cursor()

    # Création du profil si nouveau user
    existing = cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_id,)).fetchone()
    if not existing:
        cur.execute("INSERT INTO utilisateurs (id, pseudo, numero_hash, points) VALUES (?, ?, ?, ?)",
                    (user_id, f"user_{user_number[-4:]}", user_number, 0))
        conn.commit()
        msg.body("👋 Bienvenue sur Askely, ton concierge de voyage intelligent 🌍\n"
                 "Tu peux évaluer :\n"
                 "1️⃣ Un vol ✈️\n"
                 "2️⃣ Un programme de fidélité 🛂\n"
                 "3️⃣ Un hôtel 🏨\n"
                 "4️⃣ Un restaurant 🍽️\n"
                 "5️⃣ Mon profil 👤")
        return str(response)
    if incoming_msg == "menu":
        msg.body("📋 Menu Askely :\n"
                 "1️⃣ Évaluer un vol ✈️\n"
                 "2️⃣ Évaluer un programme de fidélité 🛂\n"
                 "3️⃣ Évaluer un hôtel 🏨\n"
                 "4️⃣ Évaluer un restaurant 🍽️\n"
                 "5️⃣ Mon profil 👤")
    elif incoming_msg == "5":
        row = cur.execute("SELECT pseudo, points FROM utilisateurs WHERE id = ?", (user_id,)).fetchone()
        total_avis_fidelite = cur.execute("SELECT COUNT(*) FROM evaluations_fidelite WHERE user_id = ?", (user_id,)).fetchone()[0]
        total_avis_resto = cur.execute("SELECT COUNT(*) FROM evaluations_restaurant WHERE user_id = ?", (user_id,)).fetchone()[0]
        total_avis_hotel = cur.execute("SELECT COUNT(*) FROM evaluations_hotel WHERE user_id = ?", (user_id,)).fetchone()[0]
        total_avis = total_avis_fidelite + total_avis_resto + total_avis_hotel

        history_fidelite = cur.execute("""
            SELECT e.commentaire, e.date, p.nom_programme, p.compagnie
            FROM evaluations_fidelite e
            JOIN programmes_fidelite p ON p.id = e.programme_id
            WHERE e.user_id = ?
            ORDER BY e.date DESC LIMIT 2
        """, (user_id,)).fetchall()
        histo_f = "\n".join([f"🛂 {r['nom_programme']} ({r['compagnie']}) : {r['commentaire']} ({r['date'][:10]})" for r in history_fidelite])

        history_resto = cur.execute("""
            SELECT nom_restaurant, ville, commentaire, date
            FROM evaluations_restaurant
            WHERE user_id = ?
            ORDER BY date DESC LIMIT 2
        """, (user_id,)).fetchall()
        histo_r = "\n".join([f"🍽️ {r['nom_restaurant']} ({r['ville']}) : {r['commentaire']} ({r['date'][:10]})" for r in history_resto])

        history_hotel = cur.execute("""
            SELECT nom_hotel, ville, commentaire, date
            FROM evaluations_hotel
            WHERE user_id = ?
            ORDER BY date DESC LIMIT 2
        """, (user_id,)).fetchall()
        histo_h = "\n".join([f"🏨 {r['nom_hotel']} ({r['ville']}) : {r['commentaire']} ({r['date'][:10]})" for r in history_hotel])

        history = histo_f + "\n" + histo_r + "\n" + histo_h
        msg.body(f"👤 Ton profil Askely\n"
                 f"🧾 Nom : {row['pseudo']}\n"
                 f"🪙 Points : {row['points']} pts\n"
                 f"📝 Avis déposés : {total_avis}\n\n"
                 f"🗂️ Tes derniers avis :\n{history if history.strip() else 'Aucun avis encore.'}")
    elif incoming_msg.startswith("1"):
        parts = [x.strip() for x in incoming_msg.split(',')]
        if len(parts) >= 5:
            compagnie, vol_num, date, note, commentaire = parts[:5]
            note_int = int(note)
            feedback = "✈️ Merci pour ta super évaluation de vol !" if note_int >= 4 else "Merci pour ton retour, ton expérience aidera d'autres voyageurs."
            cur.execute("UPDATE utilisateurs SET points = points + 10 WHERE id = ?", (user_id,))
            conn.commit()
            msg.body(feedback + "\n🪙 Tu gagnes 10 points Askely.")
        else:
            msg.body("✈️ Pour évaluer un vol, envoie :\nCompagnie, Numéro de vol, Date, Note (1 à 5), Commentaire")

    elif incoming_msg.startswith("2"):
        msg.body("🛂 Merci ! Envoie :\nNom du programme, Compagnie, Note accumulation, Note utilisation, Note avantages, Commentaire")
        # Traitement à ajouter si nécessaire

    elif incoming_msg.startswith("3"):
        parts = [x.strip() for x in incoming_msg.split(',')]
        if len(parts) >= 5:
            hotel, ville, date, note, commentaire = parts[:5]
            note_int = int(note)
            feedback = "🏨 Merci ! On est content que l’hôtel t’ait plu 🙏" if note_int >= 4 else "Merci pour ton retour. Cela aidera la communauté à faire les bons choix."
            cur.execute("INSERT INTO evaluations_hotel (nom_hotel, ville, date, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (hotel, ville, date, note_int, commentaire, user_id))
            cur.execute("UPDATE utilisateurs SET points = points + 7 WHERE id = ?", (user_id,))
            conn.commit()
            msg.body(feedback + "\n🪙 Tu gagnes 7 points Askely.")
        else:
            msg.body("🏨 Pour évaluer un hôtel, envoie :\nNom, Ville, Date, Note (1 à 5), Commentaire")

    elif incoming_msg.startswith("4"):
        parts = [x.strip() for x in incoming_msg.split(',')]
        if len(parts) >= 5:
            resto, ville, date, note, commentaire = parts[:5]
            note_int = int(note)
            feedback = "😋 Merci pour ton avis ! On est ravi que ce restaurant t’ait plu 🎉" if note_int >= 4 else "Merci pour ton retour. Ton avis aidera les autres utilisateurs 🍽️"
            cur.execute("INSERT INTO evaluations_restaurant (nom_restaurant, ville, date, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (resto, ville, date, note_int, commentaire, user_id))
            cur.execute("UPDATE utilisateurs SET points = points + 5 WHERE id = ?", (user_id,))
            conn.commit()
            msg.body(feedback + "\n🪙 Tu gagnes 5 points Askely.")
        else:
            msg.body("🍽️ Pour évaluer un restaurant, envoie :\nNom, Ville, Date, Note (1 à 5), Commentaire")
    else:
        msg.body("❓ Je n’ai pas compris. Envoie 'menu' pour voir les options disponibles.")

    conn.close()
    return str(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
