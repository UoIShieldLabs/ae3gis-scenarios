FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    vsftpd \
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

# Create FTP upload directory
RUN mkdir -p /home/admin/uploads && \
    chown admin:admin /home/admin/uploads

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Configure vsftpd
COPY vsftpd.conf /etc/vsftpd.conf

# Seed some dummy files so FTP downloads have something to grab
RUN dd if=/dev/urandom of=/home/admin/uploads/report_q3.dat bs=1K count=25 2>/dev/null && \
    dd if=/dev/urandom of=/home/admin/uploads/data_export.csv bs=1K count=10 2>/dev/null && \
    dd if=/dev/urandom of=/home/admin/uploads/scada_v1_update.sh bs=1K count=5 2>/dev/null && \
    chown -R admin:admin /home/admin/uploads

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 20 21 22 40000-40010

CMD ["/entrypoint.sh"]
