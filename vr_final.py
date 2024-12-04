import os
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pylsl import StreamInlet, resolve_stream
import numpy as np
import threading
import socket
import time
from datetime import datetime

# Variables globales
current_path = os.path.join(os.getcwd(), "Tests_Data_Acquisition")
event_counter = 0
collecting_data = False
paused = False
aura_inlet = None
aura_inlet2 = None
waiting_for_space = True
data_lock = threading.Lock()
baseline = None
data_accumulated = []
lower_gain = 0.9
upper_gain = 1.1
host = '192.168.10.110'
port = 5555
s = None  # Socket se inicializará más adelante

# Crear la carpeta predeterminada si no existe
os.makedirs(current_path, exist_ok=True)

# Funciones para la interfaz gráfica
def change_folder():
    global current_path
    selected_folder = filedialog.askdirectory(initialdir=current_path)
    if selected_folder:
        current_path = selected_folder
        folder_label.config(text=f"Carpeta actual: {current_path}")
        print("Ruta de carpeta actualizada")
    else:
        print("No se seleccionó ninguna carpeta.")

def generate_subject_folder():
    subject_id = subject_id_entry.get().strip()
    if subject_id:
        subject_folder = os.path.join(current_path, f"Subject_{subject_id}")
        os.makedirs(subject_folder, exist_ok=True)
        folder_label.config(text=f"Carpeta actual: {subject_folder}")
        print("Carpeta de sujeto creada:", subject_folder)
    else:
        messagebox.showwarning("Advertencia", "Por favor, introduce un ID de sujeto.")

def update_gains():
    global lower_gain, upper_gain
    try:
        lower_gain = float(entry_lower.get())
        upper_gain = float(entry_upper.get())
        print(f"Gains updated: lower_gain={lower_gain}, upper_gain={upper_gain}")
    except ValueError:
        print("Por favor, introduce valores numéricos válidos.")

def check_aura_communication():
    global aura_inlet, aura_inlet2
    try:
        print("Resolviendo streams de AURA...")
        streams = resolve_stream('name', 'AURA')
        streams2 = resolve_stream('name', 'AURA_Power')
        if streams and streams2:
            aura_inlet = StreamInlet(streams[0])
            aura_inlet2 = StreamInlet(streams2[0])
            # Verificar dimensiones de los datos del stream
            sample, _ = aura_inlet.pull_sample(timeout=1)
            sample2, _ = aura_inlet2.pull_sample(timeout=1)
            if sample and len(sample) == 8 and sample2 and len(sample2) == 40:
                print("Streams de AURA conectados.")
                aura_status_label.config(text="AURA Status: Conectado", foreground="green")
            else:
                raise ValueError("Los streams de AURA tienen dimensiones incorrectas")
        else:
            raise Exception("No se encontraron streams de AURA.")
    except Exception as e:
        aura_inlet = None
        aura_inlet2 = None
        aura_status_label.config(text="AURA Status: No Conectado", foreground="red")
        print("Fallo en la comunicación con AURA:", e)

def start_sampling():
    global collecting_data, paused, event_counter, waiting_for_space
    if aura_inlet and aura_inlet2:
        collecting_data = True
        paused = False
        event_counter = 0
        waiting_for_space = True
        update_event_label()
        threading.Thread(target=collect_aura_data, daemon=True).start()
        threading.Thread(target=process_data, daemon=True).start()
        print("Recolección de datos iniciada")
    else:
        messagebox.showwarning("Advertencia", "Asegúrate de que las conexiones AURA estén establecidas.")

def stop_sampling():
    global collecting_data
    collecting_data = False
    space_label.config(text="Muestreo detenido")
    print("Recolección de datos detenida")

def handle_space_bar(event):
    global waiting_for_space, event_counter, port, s
    if collecting_data and waiting_for_space:
        with data_lock:
            event_counter += 1
            # Cambiar el puerto según el evento
            if event_counter == 2:
                port = 5556
                print("Cambiando puerto a 5556")
            elif event_counter == 3:
                port = 5557
                print("Cambiando puerto a 5557")
            elif event_counter == 4:
                port = 5558
                print("Cambiando puerto a 5558")
            
            # Reiniciar el socket con el nuevo puerto
            restart_socket()

        update_event_label()
        print(f"Evento {event_counter} activado")
        if event_counter == 5:  # Detener después del último evento
            stop_sampling()
            root.quit()

def restart_socket():
    """Reinicia el socket con el nuevo puerto."""
    global s
    if s is not None:
        s.close()
        s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        print(f"Reconectado al servidor en el puerto {port}")
    except Exception as e:
        print(f"Error al reconectar con el servidor en el puerto {port}: {e}")

def update_event_label():
    event_label.config(text=f"Evento actual: {event_counter}")

def calculate_baseline():
    global baseline, data_accumulated
    if data_accumulated:
        baseline = np.mean(data_accumulated)
        print("Baseline calculado:", baseline)
        data_accumulated = []

def connect_to_server():
    global s
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            print("Conectado a Unity")
            return
        except Exception as e:
            print(f"Error al conectar con Unity: {e}. Intentando reconectar en 15 segundos...")
            s = None
            time.sleep(15)

def monitor_socket():
    global s
    while True:
        if s is None:
            print("Esperando conexión al servidor...")
            time.sleep(5)
            continue
        try:
            data = s.recv(1024)
            if data:
                message = data.decode('utf-8').strip()
                print(f"Mensaje recibido: {message}")
                if message == "1":
                    calculate_baseline()
        except (socket.error, ConnectionResetError) as e:
            print(f"Error en la conexión del socket: {e}. Intentando reconectar...")
            s.close()
            s = None
            connect_to_server()

def collect_aura_data():
    global collecting_data, event_counter, aura_inlet, aura_inlet2, data_accumulated
    timestamp_actual = datetime.now().strftime("%Y%m%d_%H%M%S")
    subject_id = subject_id_entry.get().strip()
    subject_folder = os.path.join(current_path, f"Subject_{subject_id}")
    raw_file = os.path.join(subject_folder, f"datos_eeg_RAW_{timestamp_actual}.csv")
    fft_file = os.path.join(subject_folder, f"datos_eeg_FFT_{timestamp_actual}.csv")
    os.makedirs(subject_folder, exist_ok=True)
    with open(raw_file, mode='w', newline='') as raw_csv, open(fft_file, mode='w', newline='') as fft_csv:
        raw_writer = csv.writer(raw_csv)
        fft_writer = csv.writer(fft_csv)
        # Agregar la columna "Cognitive Engagement" al encabezado de ambos archivos
        raw_writer.writerow(['Event', 'Time', 'F3', 'Fz', 'F4', 'C3', 'C4', 'P3', 'Pz', 'P4', 'Cognitive Engagement'])
        fft_writer.writerow(['Event', 'Time'] + [f"{band}_{channel}" for band in ['Delta', 'Theta', 'Alpha', 'Beta', 'Gamma']
                                                for channel in ['F3', 'Fz', 'F4', 'C3', 'C4', 'P3', 'Pz', 'P4']] + ['Cognitive Engagement'])
        while collecting_data:
            if paused:
                time.sleep(0.1)
                continue
            try:
                if aura_inlet is None or aura_inlet2 is None:
                    print("Los streams de AURA no están inicializados. Deteniendo recolección de datos.")
                    collecting_data = False
                    break
                raw_sample, raw_timestamp = aura_inlet.pull_sample(timeout=0.1)
                fft_sample, fft_timestamp = aura_inlet2.pull_sample(timeout=0.1)

                # Calcular el Cognitive Engagement (CE)
                if fft_sample:
                    alpha = np.mean(fft_sample[16:24])  # Índices 16 a 23
                    beta = np.mean(fft_sample[24:32])   # Índices 24 a 31
                    ce = beta / alpha if alpha != 0 else 0
                else:
                    ce = 0  # Valor por defecto si no hay datos FFT

                # Escribir en el archivo RAW
                if raw_sample:
                    with data_lock:
                        raw_writer.writerow([event_counter, raw_timestamp] + raw_sample[:8] + [ce])

                # Escribir en el archivo FFT
                if fft_sample:
                    with data_lock:
                        fft_writer.writerow([event_counter, fft_timestamp] + fft_sample[:40] + [ce])
            except Exception as e:
                print(f"Error recolectando datos de AURA: {e}")
                break

def process_data():
    global baseline, data_accumulated, aura_inlet2, s
    while collecting_data:
        try:
            if aura_inlet2 is None:
                print("El stream AURA_Power no está inicializado. No se puede procesar datos.")
                time.sleep(0.1)
                continue
            fft_sample, fft_timestamp = aura_inlet2.pull_sample(timeout=0.1)
            if fft_sample:
                # Calcular alpha y beta
                alpha = np.mean(fft_sample[16:24])  # Indices 16 a 23
                beta = np.mean(fft_sample[24:32])   # Indices 24 a 31
                ce = beta / alpha
                data_accumulated.append(ce)
                print(f"Ratio ce (beta/alpha): {ce}")
                # Si baseline está calculado, verificar si ce está fuera del rango ajustado por las ganancias
                if baseline is not None:
                    lower_bound = baseline * lower_gain
                    upper_bound = baseline * upper_gain
                    if ce < lower_bound:
                        # Enviar "a" por el socket y esperar 5 segundos antes de continuar
                        if s is not None:
                            data = "a"
                            try:
                                s.sendall(data.encode('utf-8'))
                                print("Trigger enviado: a")
                            except Exception as e:
                                print(f"Error enviando datos por el socket: {e}")
                            time.sleep(5)  # Espera de 5 segundos antes de permitir otro envío
                        else:
                            print("El socket no está conectado.")
        except Exception as e:
            print(f"Error procesando datos: {e}")
            time.sleep(0.1)

# Configuración de la interfaz gráfica
root = tk.Tk()
root.title("Interfaz Unificada de Adquisición de EEG")

# Estilos para ttk
style = ttk.Style()
style.configure("TFrame", background="#f0f0f0")
style.configure("TLabel", background="#f0f0f0")
style.configure("TButton", background="#d9d9d9")
style.configure("Header.TLabel", font=("Helvetica", 16, "bold"))
style.configure("Instructions.TLabel", background="#e0e0e0", font=("Helvetica", 10))

main_frame = ttk.Frame(root, padding="10")
main_frame.pack(fill="both", expand=True)

# Sección de instrucciones
instructions_frame = ttk.LabelFrame(main_frame, text="Instrucciones", padding="10")
instructions_frame.grid(row=0, column=0, sticky="ew", pady=5)

instructions = (
    "1. (Opcional) Cambiar carpeta: Presiona 'Cambiar Carpeta' para seleccionar dónde guardar los datos.\n"
    "2. Introduce el ID del Sujeto y presiona 'Generar Carpeta de Sujeto'.\n"
    "3. (Opcional) Ajusta las ganancias y presiona 'Actualizar Ganancias'.\n"
    "4. Verifica la comunicación con AURA presionando 'Verificar Comunicación con AURA'.\n"
    "5. Inicia el muestreo presionando 'Iniciar Muestreo'.\n"
    "6. Durante el muestreo, puedes presionar 'ESPACIO' para activar eventos.\n"
    "7. Para detener el muestreo, presiona 'Detener Muestreo'.\n"
)

instructions_label = ttk.Label(instructions_frame, text=instructions, style="Instructions.TLabel", padding="5", anchor="w", justify="left")
instructions_label.pack(fill="both", expand=True)

# Sección de carpeta y sujeto
folder_frame = ttk.LabelFrame(main_frame, text="Gestión de Carpeta y Sujeto", padding="10")
folder_frame.grid(row=1, column=0, sticky="ew", pady=5)

folder_label = ttk.Label(folder_frame, text=f"Carpeta actual: {current_path}")
folder_label.grid(row=0, column=0, columnspan=3, sticky="w")

change_folder_button = ttk.Button(folder_frame, text="Cambiar Carpeta", command=change_folder)
change_folder_button.grid(row=1, column=0, sticky="ew", pady=5)

subject_id_label = ttk.Label(folder_frame, text="ID del Sujeto:")
subject_id_label.grid(row=1, column=1, sticky="e")

subject_id_entry = ttk.Entry(folder_frame)
subject_id_entry.grid(row=1, column=2, sticky="ew")

generate_folder_button = ttk.Button(folder_frame, text="Generar Carpeta de Sujeto", command=generate_subject_folder)
generate_folder_button.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

# Sección de ganancias
gain_frame = ttk.LabelFrame(main_frame, text="Ajuste de Ganancias", padding="10")
gain_frame.grid(row=2, column=0, sticky="ew", pady=5)

ttk.Label(gain_frame, text="Ganancia Inferior:").grid(row=0, column=0, sticky="e")
entry_lower = ttk.Entry(gain_frame)
entry_lower.grid(row=0, column=1, sticky="ew")
entry_lower.insert(0, str(lower_gain))

ttk.Label(gain_frame, text="Ganancia Superior:").grid(row=1, column=0, sticky="e")
entry_upper = ttk.Entry(gain_frame)
entry_upper.grid(row=1, column=1, sticky="ew")
entry_upper.insert(0, str(upper_gain))

update_gains_button = ttk.Button(gain_frame, text="Actualizar Ganancias", command=update_gains)
update_gains_button.grid(row=2, column=0, columnspan=2, pady=5)

# Sección de estado y control
control_frame = ttk.LabelFrame(main_frame, text="Control de AURA y Muestreo", padding="10")
control_frame.grid(row=3, column=0, sticky="ew", pady=5)

aura_status_label = ttk.Label(control_frame, text="AURA Status: No Conectado", foreground="red")
aura_status_label.grid(row=0, column=0, columnspan=2, sticky="w")

aura_button = ttk.Button(control_frame, text="Verificar Comunicación con AURA", command=check_aura_communication)
aura_button.grid(row=1, column=0, columnspan=2, pady=5)

start_button = ttk.Button(control_frame, text="Iniciar Muestreo", command=start_sampling)
start_button.grid(row=2, column=0, sticky="ew", pady=5)

stop_button = ttk.Button(control_frame, text="Detener Muestreo", command=stop_sampling)
stop_button.grid(row=2, column=1, sticky="ew", pady=5)

# Sección de eventos
event_frame = ttk.LabelFrame(main_frame, text="Eventos", padding="10")
event_frame.grid(row=4, column=0, sticky="ew", pady=5)

event_label = ttk.Label(event_frame, text=f"Evento actual: {event_counter}")
event_label.grid(row=0, column=0, sticky="w")

space_label = ttk.Label(event_frame, text="Presiona ESPACIO para activar eventos", foreground="blue")
space_label.grid(row=1, column=0, sticky="w")

# Configurar el peso de las columnas para redimensionamiento
for i in range(3):
    folder_frame.columnconfigure(i, weight=1)
    gain_frame.columnconfigure(i, weight=1)
    control_frame.columnconfigure(i, weight=1)
    event_frame.columnconfigure(i, weight=1)

main_frame.columnconfigure(0, weight=1)

# Vincular la barra espaciadora
root.bind("<space>", handle_space_bar)

# Iniciar hilos para conexión y monitoreo de socket
threading.Thread(target=connect_to_server, daemon=True).start()
threading.Thread(target=monitor_socket, daemon=True).start()

# Iniciar el bucle principal de la interfaz gráfica
root.mainloop()
