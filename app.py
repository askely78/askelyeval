from flask import Flask, request
import sqlite3
from datetime import datetime
from twilio.twiml.messaging_response import MessagingResponse
import os

app = Flask(__name__)

ADMINS = [os.getenv('ADMIN_NUM')]  # Numéro admin à configurer dans Render

def get_db_connection():
    conn = sqlite3.connect('askely.db')
    conn.row_factory = sqlite3.Row
    return conn

# Créer automatiquement la base si elle n'existe pas
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

    # Vérifie si l'utilisateur existe
    user_id = user_number
    cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO utilisateurs (id, pseudo, numero_hash, points) VALUES (?, ?, ?, ?)",
                    (user_id, f"user_{user_number[-4:]}", user_number, 0))
        conn.commit()

    # Interface Admin
    if user_number in ADMINS:
        if incoming_msg == "admin stats":
            nb_users = cur.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0]
            nb_avis = cur.execute("SELECT COUNT(*) FROM evaluations_fidelite").fetchone()[0]
            reply = f"👨‍💼 Interface Admin Askely\n👥 Utilisateurs : {nb_users}\n📝 Évaluations fidélité : {nb_avis}"
        elif incoming_msg == "admin top programmes":
            rows = cur.execute("""
                SELECT p.nom_programme, p.compagnie,
                ROUND(AVG((e.note_accumulation + e.note_utilisation + e.note_avantages) / 3.0), 2) AS moyenne
                FROM evaluations_fidelite e
                JOIN programmes_fidelite p ON p.id = e.programme_id
                GROUP BY p.nom_programme, p.compagnie
                ORDER BY moyenne DESC LIMIT 5
            """).fetchall()
            reply = "🔝 Top programmes fidélité :\n" + "\n".join(
                [f"{row['nom_programme']} ({row['compagnie']}) - ⭐️ {row['moyenne']}/5" for row in rows])
        elif incoming_msg.startswith("admin avis "):
            nom_programme = incoming_msg.replace("admin avis ", "").strip()
            rows = cur.execute("""
                SELECT e.commentaire, u.pseudo, e.date FROM evaluations_fidelite e
                JOIN utilisateurs u ON u.id = e.user_id
                JOIN programmes_fidelite p ON p.id = e.programme_id
                WHERE LOWER(p.nom_programme) = ?
                ORDER BY e.date DESC LIMIT 3
            """, (nom_programme.lower(),)).fetchall()
            if rows:
                reply = f"📄 Avis récents pour {nom_programme} :\n" + "\n".join(
                    [f"- {row['commentaire']} ({row['pseudo']}, {row['date'][:10]})" for row in rows])
            else:
                reply = "Aucun avis trouvé pour ce programme."
        else:
            reply = (
                "👋 Interface Admin Askely activée\n"
                "Commandes disponibles :\n"
                "- admin stats\n"
                "- admin top programmes\n"
                "- admin avis [nom programme]"
            )
    else:
        # Utilisateur classique
        if incoming_msg.startswith("2"):
            reply = (
                "✈️ Évaluation d’un programme de fidélité\n"
                "Merci de me donner les infos suivantes séparées par des virgules :\n"
                "**Nom du programme, compagnie, note accumulation (1-5), note utilisation (1-5), note avantages (1-5), commentaire**\n"
                "Exemple : Safar Flyer, Royal Air Maroc, 4, 3, 5, Bons avantages mais peu de partenaires"
            )
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
            reply = (
                "👋 Bienvenue sur Askely !\n"
                "Tape `2` pour évaluer un programme de fidélité ✈️"
            )

    conn.close()
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

# Écoute dynamique pour Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
