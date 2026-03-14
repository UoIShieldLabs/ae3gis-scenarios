FROM python:3.11-alpine
RUN apk add --no-cache \
    bash vim curl wget iproute2 net-tools iputils \
    tcpdump bind-tools iptables nmap busybox-extras procps htop
RUN pip install --no-cache-dir pymodbus==3.6.9
COPY plc_simulator.py /app/plc_simulator.py
ENV PLC_ID=1
CMD ["tail", "-f", "/dev/null"]
