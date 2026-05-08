#!/bin/bash

PROJECT_ARCHIVE="/home/init_scada_project.tar.gz"

cd /home/
tar -xf "$PROJECT_ARCHIVE"
chmod +x "install.sh"
./install.sh &