import os
import pandas as pd

# Cambia esta línea según tu sistema operativo
folder_path = os.path.expanduser("~/Desktop")  # Para macOS/Linux
# folder_path = "C:\\Users\\TuNombreDeUsuario\\Desktop"  # Para Windows

# Lista todos los archivos en la carpeta
files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

for file_name in files:
    try:
        # Cargar el archivo CSV original
        input_file = os.path.join(folder_path, file_name)
        df = pd.read_csv(input_file)

        # Convertir los timestamps
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')

        # Guardar el archivo CSV convertido
        output_file = os.path.join(folder_path, file_name.replace(".csv", "_converted.csv"))
        df.to_csv(output_file, index=False)

        print(f"Archivo convertido: {output_file}")

    except Exception as e:
        print(f"Error procesando {file_name}: {e}")

print("¡Conversión completa!")

