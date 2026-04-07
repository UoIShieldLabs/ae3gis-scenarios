FROM huntersquires/scadabr_gns3:latest


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
    nmap &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*

WORKDIR /ScadaBR_Installer

# COPY init_wind_hmi.sh /home/
COPY start.sh /home/
COPY WindTurbineHMI.json /home/

RUN chmod +x scadabr.sh &&\
    #echo "tail -f /dev/null" >> scadabr.sh &&\
    # chmod +x /home/init_wind_hmi.sh 
    chmod +x /home/start.sh


RUN mkdir /var/run/sshd &&\
    echo 'root:root' | chpasswd &&\
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config


EXPOSE 8080 22 23

CMD ["/bin/bash", "-c", "/home/start.sh"]