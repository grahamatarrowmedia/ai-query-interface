"""
AI Query Interface - Flask app with Vertex AI integration
"""
import os
import re
import uuid
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Flask, render_template, request, jsonify
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import storage

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.0-flash-001")
PROMPT_SUFFIX = os.environ.get("PROMPT_SUFFIX", "Use deep research to verify the sources. Don't use anything that is not verified.\n\nFlag if the archive exists and add links to the script of the sources so an archive producer can verify.")
STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", f"{PROJECT_ID}-ai-query-docs")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel(MODEL_NAME)

# Initialize Cloud Storage
storage_client = storage.Client()


def extract_urls(text):
    """Extract URLs from text."""
    url_pattern = r'https?://[^\s<>\[\]()"\']+'
    urls = re.findall(url_pattern, text)
    # Clean up trailing punctuation
    cleaned_urls = []
    for url in urls:
        url = url.rstrip('.,;:!?)')
        if url and len(url) > 10:
            cleaned_urls.append(url)
    return list(set(cleaned_urls))


def download_and_store(url, bucket_name, query_id):
    """Download a URL and store it in GCS bucket."""
    try:
        # Fetch the document
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; AIQueryInterface/1.0)'
        }
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        # Determine filename
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        if path:
            filename = path.split('/')[-1]
        else:
            filename = parsed_url.netloc.replace('.', '_')

        # Add extension based on content type if missing
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        if '.' not in filename:
            ext_map = {
                'text/html': '.html',
                'application/pdf': '.pdf',
                'text/plain': '.txt',
                'application/json': '.json',
            }
            filename += ext_map.get(content_type, '.html')

        # Create unique path in bucket
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        blob_path = f"{query_id}/{url_hash}_{filename}"

        # Upload to GCS
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(
            response.content,
            content_type=content_type or 'application/octet-stream'
        )

        return {
            "url": url,
            "stored_path": blob_path,
            "gcs_uri": f"gs://{bucket_name}/{blob_path}",
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(response.content),
            "status": "success"
        }

    except requests.RequestException as e:
        return {
            "url": url,
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        return {
            "url": url,
            "status": "error",
            "error": str(e)
        }


def ensure_bucket_exists(bucket_name):
    """Create bucket if it doesn't exist."""
    try:
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():
            bucket = storage_client.create_bucket(bucket_name, location=LOCATION)
        return True
    except Exception as e:
        print(f"Bucket error: {e}")
        return False


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
        download_sources = data.get("download_sources", True)

        if not user_prompt:
            return jsonify({"error": "Please enter a prompt"}), 400

        # Combine user prompt with suffix
        full_prompt = f"{user_prompt}\n\n{PROMPT_SUFFIX}"

        # Send to Vertex AI
        response = model.generate_content(full_prompt)
        response_text = response.text

        result = {
            "response": response_text,
            "full_prompt": full_prompt,
            "documents": []
        }

        # Extract and download source documents
        if download_sources:
            urls = extract_urls(response_text)
            if urls:
                query_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
                ensure_bucket_exists(STORAGE_BUCKET)

                for url in urls:
                    doc_result = download_and_store(url, STORAGE_BUCKET, query_id)
                    result["documents"].append(doc_result)

                result["query_id"] = query_id
                result["bucket"] = STORAGE_BUCKET

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
