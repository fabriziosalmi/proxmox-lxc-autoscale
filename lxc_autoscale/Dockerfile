# Base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true

# Set the working directory
WORKDIR /app

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yq for YAML processing
RUN curl -L https://github.com/mikefarah/yq/releases/download/v4.44.1/yq_linux_amd64 -o /usr/bin/yq && \
    chmod +x /usr/bin/yq

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# #6: Create non-root user for API-only mode.
# When backend=api (no local pct commands needed), run as non-root
# to minimize attack surface. Set LXC_RUN_AS_ROOT=false to activate.
RUN groupadd -r autoscale && useradd -r -g autoscale -d /app -s /bin/false autoscale && \
    mkdir -p /var/log /var/lock /var/lib/lxc_autoscale/backups /root/.ssh && \
    chown -R autoscale:autoscale /app /var/log /var/lock /var/lib/lxc_autoscale

# Default: run as root (required for local pct commands).
# Override with: docker run -e LXC_RUN_AS_ROOT=false ...
# or in docker-compose: user: "autoscale"
USER root

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
