FROM python:3.13-slim

# Set working directory to project root
WORKDIR /polymer_nlp_extractor

# Copy all project files
COPY . .

# Install Python deps
RUN pip install --upgrade pip
RUN pip install .

# Default command - uses environment variables for host and port
CMD ["sh", "-c", "uvicorn polymer_extractor.main:app --host=${API_HOST:-0.0.0.0} --port=${API_PORT:-8000}"]
