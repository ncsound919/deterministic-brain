FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.environ.get('API_PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1
CMD ["python", "main.py", "--serve"]
