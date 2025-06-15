from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import openai
import os
from datetime import datetime

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- DB SETUP ---
def init_db():
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (
                    id TEXT PRIMARY KEY,
                    points INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS evaluations (
                    utilisateur_id TEXT,
                    type TEXT,
                    nom TEXT,
                    date TEXT,
                    note INTEGER,
                    commentaire TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# --- UTILS ---
def ajouter_utilisateur(utilisateur_id):
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO utilisateurs (id) VALUES (?)", (utilisateur_id,))
    conn.commit()
    conn.close()

def ajouter_evaluation(utilisateur_id, type, nom, date, note, commentaire):
    ajouter_utilisateur(utilisateur_id)
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?)", (utilisateur_id, type, nom, date, note, commentaire))
    c.execute("UPDATE utilisateurs SET points = points + ? WHERE id = ?", (get_points_for_type(type), utilisateur_id))
    conn.commit()
    conn.close()

def get_points_for_type(type):
    return {"vol": 10, "hôtel": 7, "restaurant": 5, "fidélité": 10}.get(type, 0)

def get_profil(utilisateur_id):
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("SELECT points FROM utilisateurs WHERE id = ?", (utilisateur_id,))
    points = c.fetchone()
    points = points[0] if points else 0

    c.execute("SELECT type, nom, date, note FROM evaluations WHERE utilisateur_id = ? ORDER BY rowid DESC LIMIT 5",
(utilisateur_id,))
    evaluations = [{"type": row[0], "nom": row[1], "date": row[2], "note": row[3]} for row in c.fetchall()]
    conn.close()
    return points, evaluations

def format_etoiles(note):
    return "⭐️" * int(note)

def format_avis_communautaires():
    conn = sqlite3.connect("askely.db")
    c = conn.cursor()
    c.execute("SELECT type, nom, date, note FROM evaluations ORDER BY rowid DESC LIMIT 10")
    evaluations = c.fetchall()
    conn.close()
    if not evaluations:
        return "Aucun avis n’a encore été enregistré."
    rep = "🗣️ Derniers avis de la communauté Askely : "
    for e in evaluations:
        rep += f"{e[0].capitalize()} – {e[1]} – {e[2]} : {format_etoiles(e[3])} "
    return rep

def reponse_gpt(prompt):
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return "🤖 Erreur avec l’intelligence artificielle."

def menu_accueil():
    return (
        "👋 Bienvenue sur Askely ! "
        "Tu peux gagner des points à chaque avis déposé.  "
        "✈️ Pour évaluer un vol → tape 1 "
        "🛂 Pour évaluer un programme de fidélité → tape 2 "
        "🏨 Pour évaluer un hôtel → tape 3 "
        "🍽️ Pour évaluer un restaurant → tape 4 "
        "👤 Pour voir ton profil → tape 6 "
        "🗣️ Pour voir les avis → tape 7 "
        "📌 Réponds avec le numéro de ton choix ou envoie directement ton avis au bon format."
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    utilisateur_id = request.values.get("From", "")
    msg = MessagingResponse()
    response = msg.message()

    if incoming_msg.lower() in ["bonjour", "salut", "hello", "hi", "menu", "start"]:
        response.body(menu_accueil())
        return str(msg)

    if incoming_msg == "1":
        response.body("✈️
        response.body("✈️ Askely : Pour évaluer un vol, envoie les infos sous cette forme :\n\nNom de la compagnie\nDate du vol\nNote sur 5\nTon commentaire")
        return str(msg)
    elif incoming_msg == "2":
        response.body("🛂 Askely : Pour évaluer un programme de fidélité, envoie les infos sous cette forme :\n\nNom du programme\nDate\nNote sur 5\nTon commentaire")
        return str(msg)
    elif incoming_msg == "3":
        response.body("🏨 Askely : Pour évaluer un hôtel, envoie les infos sous cette forme :\n\nNom de l’hôtel\nDate du séjour\nNote sur 5\nTon commentaire")
        return str(msg)
    elif incoming_msg == "4":
        response.body("🍽️ Askely : Pour évaluer un restaurant, envoie les infos sous cette forme :\n\nNom du restaurant\nDate\nNote sur 5\nTon commentaire")
        return str(msg)
    elif incoming_msg == "6":
        points, evaluations = get_profil(utilisateur_id)
        if evaluations:
            texte = f"👤 Ton profil Askely\nPoints : {points} 🪙\n\n📝 Tes 5 dernières évaluations :\n"
            for e in evaluations:
                texte += f"- {e['type'].capitalize()} – {e['nom']} – {e['date']} : {format_etoiles(e['note'])}\n"
        else:
            texte = f"👤 Ton profil Askely\nPoints : {points} 🪙\nAucune évaluation enregistrée pour l’instant."
        response.body(texte)
        return str(msg)
    elif incoming_msg == "7":
        response.body(format_avis_communautaires())
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
                response.body(f"✅ Merci ! Ton avis a été enregistré pour *{eval_type}* avec {note}⭐️. +{get_points_for_type(eval_type)} points gagnés 🪙.")
                return str(msg)
            except:
                response.body("❌ Format invalide. Vérifie que tu envoies bien :\nNom\nDate\nNote (1-5)\nCommentaire")
                return str(msg)

    # Sinon, GPT
    rep = reponse_gpt(incoming_msg)
    response.body(rep)
    return str(msg)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
