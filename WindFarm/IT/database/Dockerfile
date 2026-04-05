FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    mysql-server \
    openssh-server \
    openssh-client \
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

# Configure MySQL to listen on all interfaces
RUN sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf

# Copy init script
COPY init.sql /opt/init.sql

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 3306

CMD ["/entrypoint.sh"]
