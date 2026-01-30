"""
AI Query Interface - Flask app with Vertex AI integration
"""
import os
import re
import uuid
import hashlib
from datetime import datetime
from urllib.parse import urlparse
import tempfile

import requests
from flask import Flask, render_template, request, jsonify, send_file, Response
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import storage
from weasyprint import HTML, CSS

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


def convert_to_pdf(html_content, url):
    """Convert HTML content to PDF."""
    try:
        # Add base tag for relative URLs
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Wrap content with base URL if not present
        if '<base' not in html_content.lower():
            html_content = html_content.replace(
                '<head>',
                f'<head><base href="{base_url}">',
                1
            )

        # Create PDF
        html = HTML(string=html_content, base_url=base_url)
        pdf_bytes = html.write_pdf()
        return pdf_bytes
    except Exception as e:
        print(f"PDF conversion error for {url}: {e}")
        return None


def download_and_store(url, bucket_name, query_id):
    """Download a URL, convert to PDF, and store in GCS bucket."""
    try:
        # Fetch the document
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()

        # Determine filename from URL
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        if path:
            base_filename = path.split('/')[-1]
            base_filename = re.sub(r'[^\w\-.]', '_', base_filename)
        else:
            base_filename = parsed_url.netloc.replace('.', '_')

        # Remove existing extension
        if '.' in base_filename:
            base_filename = base_filename.rsplit('.', 1)[0]

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # Get bucket
        bucket = storage_client.bucket(bucket_name)

        result = {
            "url": url,
            "title": base_filename.replace('_', ' ').title(),
            "status": "success"
        }

        # If it's already a PDF, store directly
        if content_type == 'application/pdf':
            blob_path = f"{query_id}/{url_hash}_{base_filename}.pdf"
            blob = bucket.blob(blob_path)
            blob.upload_from_string(response.content, content_type='application/pdf')
            result["pdf_path"] = blob_path
            result["gcs_uri"] = f"gs://{bucket_name}/{blob_path}"
            result["size_bytes"] = len(response.content)
            result["filename"] = f"{base_filename}.pdf"

        # Convert HTML to PDF
        elif 'html' in content_type or 'text' in content_type:
            html_content = response.text
            pdf_bytes = convert_to_pdf(html_content, url)

            if pdf_bytes:
                blob_path = f"{query_id}/{url_hash}_{base_filename}.pdf"
                blob = bucket.blob(blob_path)
                blob.upload_from_string(pdf_bytes, content_type='application/pdf')
                result["pdf_path"] = blob_path
                result["gcs_uri"] = f"gs://{bucket_name}/{blob_path}"
                result["size_bytes"] = len(pdf_bytes)
                result["filename"] = f"{base_filename}.pdf"
            else:
                # Fallback: store as HTML if PDF conversion fails
                blob_path = f"{query_id}/{url_hash}_{base_filename}.html"
                blob = bucket.blob(blob_path)
                blob.upload_from_string(response.content, content_type='text/html')
                result["pdf_path"] = blob_path
                result["gcs_uri"] = f"gs://{bucket_name}/{blob_path}"
                result["size_bytes"] = len(response.content)
                result["filename"] = f"{base_filename}.html"
                result["note"] = "PDF conversion failed, stored as HTML"

        else:
            # Store other content types as-is
            ext = content_type.split('/')[-1] if '/' in content_type else 'bin'
            blob_path = f"{query_id}/{url_hash}_{base_filename}.{ext}"
            blob = bucket.blob(blob_path)
            blob.upload_from_string(response.content, content_type=content_type)
            result["pdf_path"] = blob_path
            result["gcs_uri"] = f"gs://{bucket_name}/{blob_path}"
            result["size_bytes"] = len(response.content)
            result["filename"] = f"{base_filename}.{ext}"

        return result

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


@app.route("/document/<path:blob_path>")
def get_document(blob_path):
    """Serve a document from GCS."""
    try:
        bucket = storage_client.bucket(STORAGE_BUCKET)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            return jsonify({"error": "Document not found"}), 404

        content = blob.download_as_bytes()
        content_type = blob.content_type or 'application/octet-stream'

        return Response(
            content,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'inline; filename="{blob_path.split("/")[-1]}"'
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<path:blob_path>")
def download_document(blob_path):
    """Download a document from GCS."""
    try:
        bucket = storage_client.bucket(STORAGE_BUCKET)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            return jsonify({"error": "Document not found"}), 404

        content = blob.download_as_bytes()
        content_type = blob.content_type or 'application/octet-stream'
        filename = blob_path.split("/")[-1]

        return Response(
            content,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
