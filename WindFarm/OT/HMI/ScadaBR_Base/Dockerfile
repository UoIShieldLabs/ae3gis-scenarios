FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openssh-server \
    rsyslog \
    iproute2 \
    iputils-ping \
    net-tools \
    tcpdump \
    telnet \
    curl \
    wget \
    git \
    nano \
    vim \
    netcat-openbsd \
    openjdk-11-jdk \
    nmap &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ScadaBR/ScadaBR_Installer.git /opt/ScadaBR_Installer
WORKDIR /opt/ScadaBR_Installer

# RUN wget https://github.com/ScadaBR/ScadaBR/releases/download/v1.2/ScadaBR_Setup_Linux.zip
# RUN unzip ScadaBR_Setup_Linux.zip
RUN chmod +x install_scadabr.sh &&\
    chmod +x scadabr.sh &&\
    ./install_scadabr.sh silent


# Optional: Copy preconfigured ScadaBR data
# COPY preconf/ScadaBR/ $CATALINA_HOME/webapps/ScadaBR/

EXPOSE 8080 22 23

CMD ["/bin/bash"]