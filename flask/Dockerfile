FROM python:3.11-slim

# Install CA certificates
# RUN apt-get update && apt-get install -y ca-certificates && apt-get clean

# Add Jenkins CA cert
# COPY jenkins.crt /usr/local/share/ca-certificates/jenkins.crt
# RUN update-ca-certificates


# ENV HTTP_PROXY=http://hpeproxy.its.hpecorp.net:80
# ENV HTTPS_PROXY=http://hpeproxy.its.hpecorp.net:443
# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y bson || true \
    && pip install --force-reinstall pymongo

# Copy application code
COPY . .

# Expose port
EXPOSE 5004

# Run the application
CMD ["python", "latest_chunk.py"]
