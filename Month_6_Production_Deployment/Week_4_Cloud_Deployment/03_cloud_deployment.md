# Cloud Deployment: AWS, GCP, Render & Railway

Take your agent from localhost to the world! This guide covers deploying to major cloud platforms.

---

## Deployment Options

```mermaid
flowchart TB
    A["Your Agent"] --> B{{"Platform Choice"}}
    B --> C["AWS<br/>Full control"]
    B --> D["GCP<br/>Google ecosystem"]
    B --> E["Render<br/>Simple & fast"]
    B --> F["Railway<br/>Developer friendly"]

    style E fill:#90EE90
    style F fill:#90EE90
```

| Platform | Complexity | Cost | Best For |
|----------|------------|------|----------|
| AWS | High | Variable | Enterprise, full control |
| GCP | High | Variable | ML workloads, BigQuery |
| Render | Low | Predictable | Startups, simple apps |
| Railway | Low | Predictable | Side projects, MVPs |

---

## Preparing for Deployment

### 1. Environment Variables

```python
# config.py
import os

class Config:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

    @classmethod
    def validate(cls):
        required = ["OPENAI_API_KEY"]
        missing = [v for v in required if not getattr(cls, v)]
        if missing:
            raise ValueError(f"Missing env vars: {missing}")
```

### 2. Requirements File

```txt
# requirements.txt
fastapi==0.104.1
uvicorn==0.24.0
openai==1.3.0
pydantic==2.5.0
python-dotenv==1.0.0
gunicorn==21.2.0
```

### 3. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Deploy to Render

The easiest option for most cases:

### 1. Create render.yaml

```yaml
# render.yaml
services:
  - type: web
    name: my-agent-api
    env: docker
    plan: starter  # or standard for more resources
    envVars:
      - key: OPENAI_API_KEY
        sync: false  # Set manually in dashboard
      - key: ENVIRONMENT
        value: production
    healthCheckPath: /health
    autoDeploy: true
```

### 2. Deploy

```bash
# Connect GitHub repo to Render
# Or use Render CLI
render deploy
```

### 3. FastAPI Health Check

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

---

## Deploy to Railway

Developer-friendly platform:

### 1. railway.json (Optional)

```json
{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### 2. Deploy via CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up

# Set environment variables
railway variables set OPENAI_API_KEY=sk-...
```

---

## Deploy to AWS

For production workloads:

### Option 1: AWS App Runner (Simplest)

```yaml
# apprunner.yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install -r requirements.txt
run:
  command: uvicorn main:app --host 0.0.0.0 --port 8080
  network:
    port: 8080
```

Deploy:
```bash
aws apprunner create-service \
  --service-name my-agent \
  --source-configuration file://apprunner.yaml
```

### Option 2: ECS with Fargate

```yaml
# task-definition.json
{
  "family": "agent-task",
  "containerDefinitions": [
    {
      "name": "agent-container",
      "image": "YOUR_ECR_IMAGE",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:..."
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agent",
          "awslogs-region": "us-east-1"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512"
}
```

### Option 3: Lambda (Serverless)

```python
# handler.py
from mangum import Mangum
from main import app

handler = Mangum(app)
```

```yaml
# serverless.yml
service: agent-api

provider:
  name: aws
  runtime: python3.11

functions:
  api:
    handler: handler.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
    environment:
      OPENAI_API_KEY: ${ssm:/agent/openai-key}
```

---

## Deploy to GCP

### Option 1: Cloud Run (Recommended)

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/agent

# Deploy to Cloud Run
gcloud run deploy agent \
  --image gcr.io/PROJECT_ID/agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production" \
  --set-secrets "OPENAI_API_KEY=openai-key:latest"
```

### Option 2: Kubernetes (GKE)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-deployment
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent
  template:
    metadata:
      labels:
        app: agent
    spec:
      containers:
      - name: agent
        image: gcr.io/PROJECT_ID/agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: openai-key
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: agent-service
spec:
  selector:
    app: agent
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest

      - name: Deploy to Render
        uses: johnbeynon/render-deploy-action@v0.0.8
        with:
          service-id: ${{ secrets.RENDER_SERVICE_ID }}
          api-key: ${{ secrets.RENDER_API_KEY }}
```

---

## Monitoring & Logging

### Structured Logging

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        return json.dumps(log_data)

# Setup
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage
logger.info("Agent started", extra={"agent_id": "123", "model": "gpt-4"})
```

### Health Checks

```python
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()
start_time = datetime.now()

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "uptime": (datetime.now() - start_time).total_seconds()
    }

@app.get("/ready")
def readiness():
    # Check dependencies
    checks = {
        "database": check_database(),
        "openai": check_openai_connection()
    }
    all_healthy = all(checks.values())
    return {
        "ready": all_healthy,
        "checks": checks
    }
```

---

## Cost Optimization

```python
# Caching to reduce API calls
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_embedding(text_hash: str):
    # Only called if not in cache
    return generate_embedding(text)

def get_embedding(text: str):
    text_hash = hashlib.md5(text.encode()).hexdigest()
    return cached_embedding(text_hash)
```

---

## Summary

```mermaid
mindmap
  root((Cloud Deployment))
    Platforms
      Render - Easy
      Railway - Developer friendly
      AWS - Enterprise
      GCP - ML focused
    Preparation
      Dockerfile
      Environment vars
      Health checks
    Operations
      CI/CD
      Logging
      Monitoring
      Cost optimization
```

---

## Quick Reference

```bash
# Render
render deploy

# Railway
railway up

# AWS App Runner
aws apprunner create-service ...

# GCP Cloud Run
gcloud run deploy ...

# Docker
docker build -t agent .
docker run -p 8000:8000 agent
```

---

## Congratulations!

You've completed the 6-month AI Agent curriculum! You now know how to:

- Build LLM-powered applications
- Create RAG systems with vector databases
- Design single and multi-agent architectures
- Evaluate and secure your agents
- Deploy to production

**Keep building amazing AI agents!** 🚀
