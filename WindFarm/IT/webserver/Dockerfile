FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    nginx \
    openssh-server \
    openssh-client \
    mysql-client \
    curl \
    net-tools \
    iputils-ping \
    iproute2 \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create admin user
RUN useradd -m -s /bin/bash admin && \
    echo "admin:password" | chpasswd

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Configure Nginx
COPY nginx.conf /etc/nginx/sites-available/default
COPY html/ /var/www/html/

# Copy SQL traffic script
COPY traffic-gen/ /opt/traffic-gen/
RUN chmod +x /opt/traffic-gen/*.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 80

CMD ["/entrypoint.sh"]
