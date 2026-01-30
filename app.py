"""
AI Query Interface - Flask app with Vertex AI integration
"""
import os
from flask import Flask, render_template, request, jsonify
import vertexai
from vertexai.generative_models import GenerativeModel

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.0-flash-001")
PROMPT_SUFFIX = os.environ.get("PROMPT_SUFFIX", "Use deep research to verify the sources. Don't use anything that is not verified.\n\nFlag if the archive exists and add links to the script of the sources so an archive producer can verify.")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel(MODEL_NAME)


@app.route("/")
def index():
    """Render the main interface."""
    return render_template("index.html", suffix_text=PROMPT_SUFFIX)


@app.route("/query", methods=["POST"])
def query():
    """Process user prompt and return AI response."""
    try:
        data = request.get_json()
        user_prompt = data.get("prompt", "").strip()

        if not user_prompt:
            return jsonify({"error": "Please enter a prompt"}), 400

        # Combine user prompt with suffix
        full_prompt = f"{user_prompt}\n\n{PROMPT_SUFFIX}"

        # Send to Vertex AI
        response = model.generate_content(full_prompt)

        return jsonify({
            "response": response.text,
            "full_prompt": full_prompt
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
