# Starting Components
## PLC
1. Start OpenPLC container.
2. Open console and run `./start_openplc.sh`.
3. **Using Engineering Workstation**, navigate into the directory containing the `deploy_motor_plc.sh` script.
4. Run `./deploy_motor_plc.sh "[OpenPLC IP ADDRESS]:8080"`, replacing `[OpenPLC IP ADDRESS]` with the IP address of the OpenPLC container.

## HMI
1. Start ScadaBR container.
2. Open console and run `./ScadaBR_Installer/scadabr.sh start`.
3. **Using Engineering Workstation**, navigate to directory containing the `deploy_hmi.sh` script.
4. Open the `motor_hmi.json` file and look for the `MODBUS_IP` Data Source.
5. Ensure the value for `host` matches the IP address of the OpenPLC container.
6. Save and close the `motor_hmi.json` configuration file.
7. Run `./deploy_hmi.sh "[ScadaBR IP ADDRESS]:8080/ScadaBR"`, replacing `[ScadaBR IP ADDRESS]` with the IP address of the ScadaBR container.

# Viewing Web Interfaces
## PLC
1. In a web browser navigate to `[OpenPLC IP ADDRESS]:8080"`, replacing `[OpenPLC IP ADDRESS]` with the IP address of the OpenPLC container.
2. Login using the following credentials:
    * **Username:** openplc
    * **Password:** openplc

## HMI
1. In a web browser navigate to `[ScadaBR IP ADDRESS]:8080/ScadaBR"`, replacing `[ScadaBR IP ADDRESS]` with the IP address of the ScadaBR container.
2. Login using the following credentials:
    * **Username:** admin
    * **Password:** admin

# Deploying Stuxnet
1. **Using Engineering Workstation**, navigate to the directory containing the `deploy_stuxnet.sh` script.
2. Run `./deploy_stuxnet.sh "[OpenPLC IP ADDRESS]:8080"`, replacing `[OpenPLC IP ADDRESS]` with the IP address of the OpenPLC container.
3. **On the OpenPLC Container**, open an auxillary console.
4. Run `su` to run commands as `root`.
5. Run `netstat -tulnp` and take note of the PID of the process listening to port `2605`.
6. Run `kill [PID]`, replacing `[PID]` with the PID neted in the previous step. 
7. **In A Web Browser**, navigate to the OpenPLC Web Interface and sign in.
8. Click the **Start PLC** button located at the bottom of the navigation bar on the left-hand side.