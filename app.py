from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3
import os
import openai

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET"])
def home():
    return "Askely est en ligne !", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").lower()
    response = MessagingResponse()
    msg = response.message()

    if "bonjour" in incoming_msg or "salut" in incoming_msg or "start" in incoming_msg:
        msg.body("""👋 Bienvenue chez *Askely* !
Gagnez des points à chaque évaluation ✨

1️⃣ Évaluer un vol
2️⃣ Évaluer un programme de fidélité
3️⃣ Évaluer un hôtel
4️⃣ Évaluer un restaurant
5️⃣ Voir les avis de la communauté
6️⃣ Mon profil
7️⃣ Transport (taxi, navette, transfert)
8️⃣ Autre question

Répondez avec *le chiffre* de votre choix.""")
        return str(response)

    msg.body("❌ Je n'ai pas compris votre demande. Merci d'envoyer 'start' pour voir le menu.")
    return str(response)

if __name__ == "__main__":
    app.run(debug=True, port=10000)
