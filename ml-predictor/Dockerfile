FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (Required for statsmodels/scikit-learn on some architectures)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Run the Brain
CMD ["python", "src/main.py"]