FROM alpine:3.19
RUN apk add --no-cache \
    bash vim curl wget iproute2 net-tools iputils \
    tcpdump bind-tools procps htop vsftpd

# Create FTP directory and generate sample files
RUN mkdir -p /srv/ftp/pub && \
    dd if=/dev/urandom of=/srv/ftp/pub/plc_config_backup.bin bs=1024 count=75 2>/dev/null && \
    dd if=/dev/urandom of=/srv/ftp/pub/quarterly_report.bin bs=1024 count=100 2>/dev/null && \
    dd if=/dev/urandom of=/srv/ftp/pub/firmware_v2.1.bin bs=1024 count=50 2>/dev/null && \
    dd if=/dev/urandom of=/srv/ftp/pub/network_diagram.bin bs=1024 count=30 2>/dev/null && \
    dd if=/dev/urandom of=/srv/ftp/pub/maintenance_log.bin bs=1024 count=60 2>/dev/null && \
    chown -R ftp:ftp /srv/ftp

# vsftpd config — anonymous read-only
COPY vsftpd.conf /etc/vsftpd/vsftpd.conf

CMD ["tail", "-f", "/dev/null"]
