"""
AI Query Interface - Local test version with mocked responses
No GCP dependencies required for UI testing
"""
import os
import time
import random
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)

# Configuration
PROMPT_SUFFIX = os.environ.get("PROMPT_SUFFIX", "Use deep research to verify the sources. Don't use anything that is not verified.\n\nFlag if the archive exists and add links to the script of the sources so an archive producer can verify.")

# Mock responses for testing
MOCK_RESPONSES = [
    """# Research Results

Based on verified sources, here are the findings:

## Key Sources
- BBC Archive: https://www.bbc.co.uk/archive/collections
- National Archives UK: https://www.nationalarchives.gov.uk/
- Internet Archive: https://archive.org/

## Archive Status
- BBC Archive: **Exists** - Contains broadcast recordings from 1920s onwards
- National Archives: **Exists** - Official government records
- Internet Archive: **Exists** - Digital preservation of web pages

## Verification Notes
All sources have been verified as legitimate archival institutions.""",

    """# Document Analysis

## Verified Sources
The following sources have been confirmed:

1. **Reuters Archive** - https://www.reuters.com/
   - Status: Archive exists
   - Contains: News articles and photographs

2. **British Library** - https://www.bl.uk/
   - Status: Archive exists
   - Contains: Historical documents and manuscripts

3. **Wikipedia** - https://en.wikipedia.org/
   - Status: Archive exists (via Wayback Machine)
   - Note: Cross-reference with primary sources recommended

## Recommendations
Archive producers should verify content against original broadcasts.""",

    """# Source Verification Report

## Primary Sources
- https://www.gov.uk/government/publications - Official government publications
- https://www.parliament.uk/business/publications/ - Parliamentary records

## Archive Verification
| Source | Archive Status | Last Verified |
|--------|---------------|---------------|
| Gov.uk | Exists | Current |
| Parliament | Exists | Current |

## Notes for Archive Producers
All links have been tested and are accessible. Documents should be downloaded and preserved locally."""
]

# Store mock documents in memory for the test app
MOCK_DOCUMENTS_STORE = {}


@app.route("/")
def index():
    """Render the main interface."""
    return render_template("index.html", suffix_text=PROMPT_SUFFIX)


@app.route("/query", methods=["POST"])
def query():
    """Process user prompt and return mock AI response with documents."""
    try:
        data = request.get_json()
        user_prompt = data.get("prompt", "").strip()

        if not user_prompt:
            return jsonify({"error": "Please enter a prompt"}), 400

        # Combine user prompt with suffix
        full_prompt = f"{user_prompt}\n\n{PROMPT_SUFFIX}"

        # Simulate API delay
        time.sleep(random.uniform(0.5, 1.5))

        # Return mock response
        mock_response = random.choice(MOCK_RESPONSES)
        query_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]

        # Mock downloaded documents (as PDFs)
        mock_documents = [
            {
                "url": "https://www.bbc.co.uk/archive/collections",
                "title": "BBC Archive Collections",
                "pdf_path": f"{query_id}/abc123_collections.pdf",
                "gcs_uri": f"gs://test-bucket/{query_id}/abc123_collections.pdf",
                "filename": "collections.pdf",
                "size_bytes": 145678,
                "status": "success"
            },
            {
                "url": "https://www.nationalarchives.gov.uk/",
                "title": "National Archives",
                "pdf_path": f"{query_id}/def456_nationalarchives.pdf",
                "gcs_uri": f"gs://test-bucket/{query_id}/def456_nationalarchives.pdf",
                "filename": "nationalarchives.pdf",
                "size_bytes": 232145,
                "status": "success"
            },
            {
                "url": "https://archive.org/",
                "title": "Internet Archive",
                "pdf_path": f"{query_id}/ghi789_archive.pdf",
                "gcs_uri": f"gs://test-bucket/{query_id}/ghi789_archive.pdf",
                "filename": "archive.pdf",
                "size_bytes": 89432,
                "status": "success"
            },
            {
                "url": "https://example.com/broken-link",
                "status": "error",
                "error": "404 Not Found"
            }
        ]

        # Store mock PDF content for viewing
        for doc in mock_documents:
            if doc.get("status") == "success":
                MOCK_DOCUMENTS_STORE[doc["pdf_path"]] = create_mock_pdf(doc["title"], doc["url"])

        return jsonify({
            "response": mock_response,
            "full_prompt": full_prompt,
            "documents": mock_documents,
            "query_id": query_id,
            "bucket": "test-bucket",
            "mock": True
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def create_mock_pdf(title, url):
    """Create a simple mock PDF-like content for testing."""
    # In test mode, we'll just return HTML that looks like a document
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #333; border-bottom: 2px solid #2563eb; padding-bottom: 10px; }}
            .meta {{ color: #666; margin-bottom: 20px; }}
            .content {{ line-height: 1.8; }}
            .notice {{ background: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        <p class="meta">Source: <a href="{url}">{url}</a></p>
        <div class="content">
            <p>This is a mock PDF document generated for testing purposes.</p>
            <p>In production, this would be the actual PDF conversion of the webpage content from the source URL.</p>
            <p>The document has been archived and stored in the GCS bucket for verification by archive producers.</p>
        </div>
        <div class="notice">
            <strong>Test Mode Notice:</strong> This is a simulated document.
            Deploy to production to see actual PDF conversions of source documents.
        </div>
    </body>
    </html>
    """.encode()


@app.route("/document/<path:blob_path>")
def get_document(blob_path):
    """Serve a mock document."""
    if blob_path in MOCK_DOCUMENTS_STORE:
        return Response(
            MOCK_DOCUMENTS_STORE[blob_path],
            mimetype='text/html',
            headers={'Content-Disposition': f'inline; filename="{blob_path.split("/")[-1]}"'}
        )
    return jsonify({"error": "Document not found"}), 404


@app.route("/download/<path:blob_path>")
def download_document(blob_path):
    """Download a mock document."""
    if blob_path in MOCK_DOCUMENTS_STORE:
        filename = blob_path.split("/")[-1]
        return Response(
            MOCK_DOCUMENTS_STORE[blob_path],
            mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    return jsonify({"error": "Document not found"}), 404


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "mode": "test"})


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  AI Query Interface - LOCAL TEST MODE")
    print("  Responses are mocked (no GCP required)")
    print("=" * 50)
    print("\n  Open: http://localhost:5000\n")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
