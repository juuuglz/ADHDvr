from pylsl import StreamInlet, resolve_stream
import numpy as np
import csv
import time
import threading
import os

print("Looking for an EEG stream...")
streams = resolve_stream('name', 'AURA_Power')

inlet = StreamInlet(streams[0])
data_accumulated = []
recording = False
stop_program = False


def input_listener():
    """Escucha continuamente entradas del usuario en un hilo separado."""
    global recording, stop_program
    while not stop_program:
        command = input("Press ENTER to toggle recording, or type 'q' to quit: ").strip().lower()
        if command == 'q':
            stop_program = True
        elif command == '':
            recording = not recording
            state = "started" if recording else "stopped"
            print(f"Recording {state}!")


listener_thread = threading.Thread(target=input_listener, daemon=True)
listener_thread.start()

while not stop_program:
    if recording:
        try:
            sample, timestamp = inlet.pull_sample()
            alpha = np.mean(sample[16:23])
            beta = np.mean(sample[24:31])
            ce = beta / alpha
            data_accumulated.append((timestamp, ce))  # Almacena tupla con timestamp y ce
            print(f"Timestamp: {timestamp} | Ratio ce (alpha/beta): {ce}")
        except KeyboardInterrupt:
            print("Recording interrupted.")
            recording = False

if data_accumulated:
    # Ruta personalizada: Documentos > EMFUTECH > ADHD_project
    path = os.path.join(os.path.expanduser("~"), "Documents", "EMFUTECH", "ADHD_project")
    
    # Asegúrate de que la carpeta exista, si no, la creamos
    if not os.path.exists(path):
        os.makedirs(path)

    # Crear el nombre del archivo con timestamp
    filename = os.path.join(path, f"output_{int(time.time())}.csv")
    
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'CE Ratio (Beta/Alpha)'])  # Agregar encabezados
        for timestamp, value in data_accumulated:
            writer.writerow([timestamp, value])  # Escribe cada par (timestamp, ce)
    print(f"Data saved to: {filename}")

print("Program terminated.")

