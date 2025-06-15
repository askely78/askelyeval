from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os
import openai

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("askely.db")
    conn.row_factory = sqlite3.Row
    return conn

def ask_gpt(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Askely 🤖 : Erreur IA – " + str(e)

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
@app.route("/", methods=["GET", "POST"])
def webhook():
    response = MessagingResponse()
    msg = response.message()
    user_number = request.form.get("From", "").replace("whatsapp:", "")
    incoming_msg = request.form.get("Body", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    # Crée ou récupère l'utilisateur
    cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_number,))
    user = cur.fetchone()
    if not user:
        cur.execute("INSERT INTO utilisateurs (id, pseudo, points) VALUES (?, ?, ?)", (user_number, f"User-{user_number[-4:]}", 0))
        conn.commit()
        msg.body(menu_principal())
        conn.close()
        return str(response)

    # Menu d’accueil
    if incoming_msg.lower() in ["menu", "bonjour", "salut", "hi", "start", "askely"]:
        msg.body(menu_principal())
        conn.close()
        return str(response)

    msg_txt = incoming_msg.lower()

    if msg_txt == "1":
        msg.body("✈️ Askely : Pour évaluer un vol, envoie les infos sous cette forme :\n\nNom de la compagnie\nDate du vol\nNuméro de vol\nNote (1-5)\nCommentaire")
        return str(response)
    elif msg_txt == "2":
        msg.body("🛂 Askely : Pour évaluer un programme de fidélité, envoie :\n\nNom du programme\nCompagnie aérienne\nNote sur l'accumulation (1-5)\nNote sur l'utilisation (1-5)\nNote sur les avantages (1-5)\nCommentaire")
        return str(response)
    elif msg_txt == "3":
        msg.body("🏨 Askely : Pour évaluer un hôtel, envoie les infos :\n\nNom de l’hôtel\nVille\nDate du séjour\nNote (1-5)\nCommentaire")
        return str(response)
    elif msg_txt == "4":
        msg.body("🍽️ Askely : Pour évaluer un restaurant, envoie les infos :\n\nNom du restaurant\nVille\nDate de visite\nNote (1-5)\nCommentaire")
        return str(response)
    elif msg_txt == "5":
        profil = cur.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_number,)).fetchone()
        vols = cur.execute("SELECT * FROM evaluations_vol WHERE user_id = ? ORDER BY id DESC LIMIT 3", (user_number,)).fetchall()
        hotels = cur.execute("SELECT * FROM evaluations_hotel WHERE user_id = ? ORDER BY id DESC LIMIT 3", (user_number,)).fetchall()
        restos = cur.execute("SELECT * FROM evaluations_restaurant WHERE user_id = ? ORDER BY id DESC LIMIT 3", (user_number,)).fetchall()
        fid = cur.execute("SELECT * FROM evaluations_fidelite WHERE user_id = ? ORDER BY id DESC LIMIT 3", (user_number,)).fetchall()

        msg_txt = f"👤 Askely – Ton profil :\nPseudo : {profil['pseudo']}\nPoints : {profil['points']} 🪙\n\n🕓 Derniers avis :"
        for v in vols:
            msg_txt += f"\n✈️ {v['compagnie']} {v['numero_vol']} - Note {v['note']}/5"
        for h in hotels:
            msg_txt += f"\n🏨 {h['nom_hotel']} ({h['ville']}) - Note {h['note']}/5"
        for r in restos:
            msg_txt += f"\n🍽️ {r['nom_restaurant']} ({r['ville']}) - Note {r['note']}/5"
        for f in fid:
            moyenne = (f['note_accumulation'] + f['note_utilisation'] + f['note_avantages']) // 3
            msg_txt += f"\n🛂 {f['programme']} - Moyenne {moyenne}/5"

        msg.body(msg_txt)
        conn.close()
        return str(response)
    try:
        # Évaluation vol
        if incoming_msg.count("\n") >= 4 and "compagnie" not in incoming_msg.lower():
            lignes = incoming_msg.split("\n")
            if len(lignes) == 5:
                compagnie, date_vol, numero_vol, note, commentaire = lignes
                cur.execute("INSERT INTO evaluations_vol (compagnie, date_vol, numero_vol, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                            (compagnie.strip(), date_vol.strip(), numero_vol.strip(), int(note), commentaire.strip(), user_number))
                cur.execute("UPDATE utilisateurs SET points = points + 10 WHERE id = ?", (user_number,))
                conn.commit()
                msg.body("✈️ Askely : Merci pour ton avis sur ce vol. Tu gagnes 10 points 🪙")
                conn.close()
                return str(response)

        # Évaluation fidélité
        if incoming_msg.count("\n") >= 6 and "programme" in incoming_msg.lower():
            lignes = incoming_msg.split("\n")
            if len(lignes) >= 6:
                programme, compagnie, acc, uti, ava, commentaire = lignes[:6]
                cur.execute("INSERT INTO evaluations_fidelite (programme, compagnie, note_accumulation, note_utilisation, note_avantages, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (programme.strip(), compagnie.strip(), int(acc), int(uti), int(ava), commentaire.strip(), user_number))
                cur.execute("UPDATE utilisateurs SET points = points + 5 WHERE id = ?", (user_number,))
                conn.commit()
                msg.body("🛂 Askely : Merci pour ton évaluation du programme de fidélité. Tu gagnes 5 points 🪙")
                conn.close()
                return str(response)
        # Évaluation hôtel
        if incoming_msg.count("\n") >= 4 and ("hôtel" in incoming_msg.lower() or "hotel" in incoming_msg.lower()):
            lignes = incoming_msg.split("\n")
            if len(lignes) == 5:
                nom, ville, date, note, commentaire = lignes
                cur.execute("INSERT INTO evaluations_hotel (nom_hotel, ville, date, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                            (nom.strip(), ville.strip(), date.strip(), int(note), commentaire.strip(), user_number))
                cur.execute("UPDATE utilisateurs SET points = points + 7 WHERE id = ?", (user_number,))
                conn.commit()
                msg.body("🏨 Askely : Merci pour ton avis sur cet hôtel. Tu gagnes 7 points 🪙")
                conn.close()
                return str(response)

        # Évaluation restaurant
        if incoming_msg.count("\n") >= 4 and "restaurant" in incoming_msg.lower():
            lignes = incoming_msg.split("\n")
            if len(lignes) == 5:
                nom, ville, date, note, commentaire = lignes
                cur.execute("INSERT INTO evaluations_restaurant (nom_restaurant, ville, date, note, commentaire, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                            (nom.strip(), ville.strip(), date.strip(), int(note), commentaire.strip(), user_number))
                cur.execute("UPDATE utilisateurs SET points = points + 5 WHERE id = ?", (user_number,))
                conn.commit()
                msg.body("🍽️ Askely : Merci pour ton avis sur ce restaurant. Tu gagnes 5 points 🪙")
                conn.close()
                return str(response)
        # Question libre → GPT
        if incoming_msg:
            gpt_response = ask_gpt(incoming_msg)
            msg.body("🤖 Askely : " + gpt_response)
            conn.close()
            return str(response)

    except Exception as e:
        msg.body("❌ Askely : Une erreur est survenue : " + str(e))
        conn.close()
        return str(response)

    conn.close()
    msg.body("❓ Askely : Je n’ai pas compris. Tape un chiffre (1 à 5) ou pose ta question.")
    return str(response)

def menu_principal():
    return (
        "👋 Bienvenue sur Askely – Ton assistant de voyage intelligent 🌍\n"
        "Évalue tes expériences et gagne des points 🪙\n\n"
        "✏️ Tape le chiffre correspondant à ton choix :\n"
        "1️⃣ Évaluer un vol ✈️\n"
        "2️⃣ Évaluer un programme de fidélité 🛂\n"
        "3️⃣ Évaluer un hôtel 🏨\n"
        "4️⃣ Évaluer un restaurant 🍽️\n"
        "5️⃣ Voir mon profil 👤\n\n"
        "💬 Ou pose une question libre (ex : météo, réservation, info pays...)\n"
        "📌 Envoie simplement le chiffre de ton choix !"
    )

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
