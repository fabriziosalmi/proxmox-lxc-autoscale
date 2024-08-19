# Use Debian 12 (Bookworm) as a base image
FROM debian:12-slim

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils curl python3 python3-pip python3-dev \
    python3-apt python3-venv python3-wheel python3-setuptools \
    python3-cryptography python3-requests python3-paramiko python3-psutil \
    python3-yaml python3-simplejson python3-lxml && \
    rm -rf /var/lib/apt/lists/*

# Set up the working directory
WORKDIR /app

# Copy the application files into the container
COPY lxc_autoscale.py /usr/local/bin/lxc_autoscale.py
COPY lxc_autoscale.yaml /etc/lxc_autoscale/lxc_autoscale.yaml

# Ensure the Python script is executable
RUN chmod +x /usr/local/bin/lxc_autoscale.py
RUN chmod +r /etc/lxc_autoscale/lxc_autoscale.yaml

# Set the default command to run your Python application
CMD ["python3", "/usr/local/bin/lxc_autoscale.py"]
