import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

import chatbot_config as cfg

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None

MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_TURNS = 20


def build_contents(history, message):
    """Convert the chat history sent by the browser into Gemini contents."""
    contents = []
    for item in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = str(item.get("text", "")).strip()
        if role in ("user", "model") and text:
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=text[:MAX_MESSAGE_CHARS])])
            )
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
    return contents


@app.route("/")
def index():
    return render_template(
        "index.html",
        title=cfg.CHATBOT_TITLE,
        tagline=cfg.CHATBOT_TAGLINE,
        emoji=cfg.CHATBOT_EMOJI,
        roles=cfg.ROLES,
        welcome=cfg.WELCOME_MESSAGE,
        suggestions=cfg.SUGGESTIONS,
    )


@app.route("/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify(error="GEMINI_API_KEY is missing. Add it to the .env file."), 500

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    history = data.get("history", [])

    if not message:
        return jsonify(error="Please type a question."), 400
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify(error=f"Message is too long (max {MAX_MESSAGE_CHARS} characters)."), 400
    if not isinstance(history, list):
        history = []

    try:
        response = client.models.generate_content(
            model=cfg.MODEL_NAME,
            contents=build_contents(history, message),
            config=types.GenerateContentConfig(
                system_instruction=cfg.SYSTEM_PROMPT,
                temperature=cfg.TEMPERATURE,
                max_output_tokens=cfg.MAX_OUTPUT_TOKENS,
            ),
        )
        reply = (response.text or "").strip()
        if not reply:
            reply = "I couldn't generate an answer for that. Please try rephrasing your question."
        return jsonify(reply=reply)
    except Exception:
        app.logger.exception("Gemini request failed")
        return jsonify(error="Something went wrong while contacting the AI. Please try again."), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
