FROM python:3.13-slim

# Set working directory to project root
WORKDIR /polymer_nlp_extractor

# Copy all project files
COPY . .

# Install Python deps
RUN pip install --upgrade pip
RUN pip install .

# Default command
CMD ["uvicorn", "polymer_extractor.main:app", "--host=0.0.0.0", "--port=8000"]
