FROM python:3.11-alpine
RUN apk add --no-cache \
    bash vim curl wget iproute2 net-tools iputils \
    tcpdump bind-tools iptables nmap busybox-extras procps htop
RUN pip install --no-cache-dir pymysql==1.1.1
COPY traffic_gen.py /app/traffic_gen.py
CMD ["tail", "-f", "/dev/null"]
