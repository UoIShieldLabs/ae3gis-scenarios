FROM mariadb:10
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 iputils-ping net-tools tcpdump vim curl wget procps htop \
    && rm -rf /var/lib/apt/lists/*
ENV MARIADB_ROOT_PASSWORD=icslab
ENV MARIADB_DATABASE=ics_historian
ENV MARIADB_USER=scada
ENV MARIADB_PASSWORD=scada
COPY init.sql /docker-entrypoint-initdb.d/init.sql
# Use MariaDB default CMD — mysqld starts automatically
