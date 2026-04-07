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
    nmap


RUN git clone https://github.com/HunterSquires/OpenPLC_v3_AE3GIS.git /opt/OpenPLC_v3

WORKDIR /opt/OpenPLC_v3

RUN ./install.sh docker

COPY WindTurbineCtrl.st /opt/OpenPLC_v3/webserver/st_files/
COPY turbine_psm.py /opt/OpenPLC_v3/webserver/core/psm/main.py
COPY SIM_NET_ADDR.txt /opt/OpenPLC_v3/webserver/core/psm/
COPY edit_plc_db.sh /home/
COPY start.sh /home/

WORKDIR /opt/OpenPLC_v3/webserver
RUN chmod +x /home/edit_plc_db.sh &&\
    chmod +x /home/start.sh &&\
    /home/edit_plc_db.sh "WindTurbine" "desc" "WindTurbineCtrl.st" && \
    /opt/OpenPLC_v3/webserver/scripts/change_hardware_layer.sh psm_linux &&\
    /opt/OpenPLC_v3/webserver/scripts/compile_program.sh "WindTurbineCtrl.st"

WORKDIR /opt/OpenPLC_v3

RUN mkdir /var/run/sshd &&\
    echo 'root:root' | chpasswd &&\
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

EXPOSE 8080 502 22 23

# ENTRYPOINT ["/bin/bash", "/opt/OpenPLC_v3/start_openplc.sh"]
CMD ["/bin/bash", "-c", "/home/start.sh"]