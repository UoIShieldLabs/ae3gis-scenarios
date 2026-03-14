"""
Modbus/TCP PLC simulator. Serves 10 holding registers with changing values.
"""
import os, time, random, threading
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

UNIT_ID = int(os.environ.get("PLC_ID", 1))

def update_registers(context):
    while True:
        values = [random.randint(100, 999) for _ in range(10)]
        context[0x00].setValues(3, 0, values)
        time.sleep(1)

def main():
    store = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 10),
        ir=ModbusSequentialDataBlock(0, [0] * 10),
    )
    context = ModbusServerContext(slaves=store, single=True)
    t = threading.Thread(target=update_registers, args=(context,), daemon=True)
    t.start()
    print(f"PLC {UNIT_ID} | Modbus/TCP on 0.0.0.0:502")
    StartTcpServer(context=context, address=("0.0.0.0", 502))

if __name__ == "__main__":
    main()
