
import os
import sqlite3
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

app = Flask(__name__)

ADMINS = ["+212600000000"]

def get_db_connection():
    conn = sqlite3.connect('askely.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialisation automatique de la base si elle n'existe pas
def init_sqlite_db():
    if not os.path.exists('askely.db'):
        with open('init_db.sql', 'r') as f:
            schema = f.read()
        conn = sqlite3.connect('askely.db')
        cursor = conn.cursor()
        cursor.executescript(schema)
        conn.commit()
        conn.close()
        print("✅ Base SQLite initialisée.")

init_sqlite_db()

@app.route('/webhook', methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip().lower()
    user_number = request.values.get('From', '').split(':')[-1]
    conn = get_db_connection()
    cur = conn.cursor()

    user_id = user_number
    cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO utilisateurs (id, pseudo, numero_hash, points) VALUES (?, ?, ?, ?)",
                    (user_id, f"user_{user_number[-4:]}", user_number, 0))
        conn.commit()

    if user_number in ADMINS:
        if incoming_msg == "admin stats":
            nb_users = cur.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0]
            nb_avis = cur.execute("SELECT COUNT(*) FROM evaluations_fidelite").fetchone()[0]
            reply = f"👨‍💼 Interface Admin Askely\n👥 Utilisateurs : {nb_users}\n📝 Évaluations fidélité : {nb_avis}"
        else:
            reply = "Interface admin disponible. Tape `admin stats`."
    else:
        if incoming_msg.startswith("2"):
            reply = ("✈️ Évaluation d’un programme de fidélité\n"
                     "Merci de me donner les infos suivantes séparées par des virgules :\n"
                     "**Nom du programme, compagnie, note accumulation (1-5), note utilisation (1-5), note avantages (1-5), commentaire**")
        elif "," in incoming_msg:
            parts = [x.strip() for x in incoming_msg.split(',')]
            if len(parts) >= 6:
                programme, compagnie, n1, n2, n3, commentaire = parts[:6]
                cur.execute("SELECT id FROM programmes_fidelite WHERE nom_programme = ?", (programme,))
                row = cur.fetchone()
                if row:
                    programme_id = row['id']
                else:
                    cur.execute("INSERT INTO programmes_fidelite (compagnie, nom_programme) VALUES (?, ?)", (compagnie, programme))
                    programme_id = cur.lastrowid
                cur.execute("""
                    INSERT INTO evaluations_fidelite (programme_id, user_id, note_accumulation, note_utilisation, note_avantages, commentaire)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (programme_id, user_id, int(n1), int(n2), int(n3), commentaire))
                cur.execute("UPDATE utilisateurs SET points = points + 15 WHERE id = ?", (user_id,))
                conn.commit()
                reply = f"🎉 Merci pour ton avis sur {programme} ! Tu gagnes 15 points Askely 🪙."
            else:
                reply = "⚠️ Format incorrect. Merci de suivre l'exemple."
        else:
            reply = "👋 Bienvenue sur Askely ! Tape `2` pour commencer."

    conn.close()
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

if __name__ == '__main__':
    app.run(debug=True)
