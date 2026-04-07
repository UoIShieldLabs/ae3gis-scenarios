FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openssh-server \
    rsyslog \
    iproute2 \
    iputils-ping \
    net-tools \
    tcpdump \
    curl \
    wget \
    git \
    nano \
    vim \
    netcat-openbsd \
    nmap &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*

COPY start.sh /home/

RUN chmod +x /home/start.sh

RUN mkdir /var/run/sshd &&\
    echo 'root:mypassword' | chpasswd &&\
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

EXPOSE 22 23

CMD ["/bin/bash", "-c", "/home/start.sh"]