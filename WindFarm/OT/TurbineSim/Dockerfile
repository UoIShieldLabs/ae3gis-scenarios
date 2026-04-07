FROM alpine:latest

RUN apk update && apk add \
    net-tools \
    curl \
    wget \
    nano \
    python3 \
    py3-pip

RUN mkdir /opt/TurbineSim
WORKDIR /opt/TurbineSim

COPY wind_turbine.py /opt/TurbineSim/
COPY turbine_functions.py /opt/TurbineSim/
COPY precision_timer.py /opt/TurbineSim/
COPY Cp_Ct_Cq.NREL5MW.txt /opt/TurbineSim/
COPY flatirons_wind_2026_03_31.csv /opt/TurbineSim/
COPY requirements.txt /opt/TurbineSim/
COPY static/ /opt/TurbineSim/static/
COPY templates/ /opt/TurbineSim/templates
COPY start_sim.sh /opt/TurbineSim/
RUN chmod +x /opt/TurbineSim/start_sim.sh

RUN python3 -m venv .venv &&\
    chmod +x .venv/bin/activate &&\
    .venv/bin/python3 -m pip install -r requirements.txt

EXPOSE 5555 8080

# ENTRYPOINT ["/bin/bash", "/opt/OpenPLC_v3/start_openplc.sh"]
CMD ["sh", "-c", "/opt/TurbineSim/start_sim.sh"]