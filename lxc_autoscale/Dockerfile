# Base image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set environment variable to indicate Docker environment
ENV RUNNING_IN_DOCKER=true

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install required packages
RUN apt-get update && apt-get install -y \
    openssh-client \
    sshpass \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yq for YAML processing
RUN curl -L https://github.com/mikefarah/yq/releases/download/v4.6.3/yq_linux_amd64 -o /usr/bin/yq && \
    chmod +x /usr/bin/yq

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
