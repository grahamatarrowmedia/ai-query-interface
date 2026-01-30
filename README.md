# AI Query Interface

A Flask web application that takes user prompts, appends configurable suffix text, sends them to Vertex AI (Gemini 2.5 Pro), and displays the AI response.

## Features

- Text input for user prompts
- Configurable suffix text appended to all prompts
- Gemini 2.5 Pro integration via Vertex AI
- Markdown rendering for responses
- Professional, responsive UI
- Local development mode with mocked responses

## Project Structure

```
ai-query-interface/
├── app.py              # Main Flask app with Vertex AI
├── test_app.py         # Local dev version (mocked responses)
├── templates/
│   └── index.html      # Main interface
├── static/
│   └── css/
│       └── style.css   # Styling
├── requirements.txt    # Dependencies
├── Dockerfile          # Cloud Run deployment
├── cloudbuild.yaml     # GCP build config
└── README.md           # This file
```

## Local Development

### Test Mode (No GCP Required)

Run the test version with mocked AI responses:

```bash
python test_app.py
```

Open http://localhost:5000 in your browser.

### Full Mode (Requires GCP)

1. Set up GCP credentials:
   ```bash
   gcloud auth application-default login
   ```

2. Set environment variables:
   ```bash
   export GCP_PROJECT_ID=your-project-id
   export GCP_LOCATION=us-central1
   export PROMPT_SUFFIX="Your custom suffix text here"
   ```

3. Install dependencies and run:
   ```bash
   pip install -r requirements.txt
   python app.py
   ```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud project ID | `your-project-id` |
| `GCP_LOCATION` | Vertex AI region | `us-central1` |
| `MODEL_NAME` | Gemini model to use | `gemini-2.5-pro-preview-05-06` |
| `PROMPT_SUFFIX` | Text appended to all prompts | `Please provide a clear and concise response.` |
| `PORT` | Server port | `5000` |

## Deployment to Cloud Run

### Using Cloud Build

```bash
gcloud builds submit --config cloudbuild.yaml
```

### Manual Deployment

```bash
# Build
docker build -t gcr.io/PROJECT_ID/ai-query-interface .

# Push
docker push gcr.io/PROJECT_ID/ai-query-interface

# Deploy
gcloud run deploy ai-query-interface \
  --image gcr.io/PROJECT_ID/ai-query-interface \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=PROJECT_ID,PROMPT_SUFFIX=Your suffix here"
```

## Usage

1. Enter your prompt in the textarea
2. Click "Send Query" or press Ctrl+Enter
3. View the AI response with markdown rendering
4. Expand "View suffix text" to see what gets appended
5. Expand "View full prompt sent" to see the complete prompt

## License

MIT
