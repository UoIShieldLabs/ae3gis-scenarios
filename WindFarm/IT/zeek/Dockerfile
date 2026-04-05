FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Zeek from official repo
RUN apt-get update && apt-get install -y \
    gnupg \
    curl \
    ca-certificates \
    && echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_22.04/ /' \
       > /etc/apt/sources.list.d/zeek.list \
    && curl -fsSL 'https://download.opensuse.org/repositories/security:/zeek/xUbuntu_22.04/Release.key' \
       | gpg --dearmor -o /etc/apt/trusted.gpg.d/zeek.gpg \
    && apt-get update && apt-get install -y \
    zeek \
    openssh-server \
    openssh-client \
    net-tools \
    iputils-ping \
    iproute2 \
    tcpdump \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Add Zeek to PATH
ENV PATH="/opt/zeek/bin:${PATH}"

# Create admin user
RUN useradd -m -s /bin/bash admin && \
    echo "admin:password" | chpasswd

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Create log directory
RUN mkdir -p /opt/zeek/logs/current

# Copy Zeek config
COPY local.zeek /opt/zeek/share/zeek/site/local.zeek

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

CMD ["/entrypoint.sh"]
