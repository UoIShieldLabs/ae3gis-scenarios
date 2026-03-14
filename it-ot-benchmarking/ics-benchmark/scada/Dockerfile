FROM python:3.11-alpine
RUN apk add --no-cache \
    bash vim curl wget iproute2 net-tools iputils \
    tcpdump bind-tools iptables nmap busybox-extras procps htop
RUN pip install --no-cache-dir pymodbus==3.6.9 pymysql==1.1.1
COPY scada_v2.py /app/scada_v2.py
CMD ["tail", "-f", "/dev/null"]
