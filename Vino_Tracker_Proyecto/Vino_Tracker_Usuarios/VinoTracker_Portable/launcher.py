import os
import sys
import time
import threading
import webbrowser
import subprocess

def open_browser():
    """Abre el navegador después de un breve retraso."""
    time.sleep(3)
    webbrowser.open("http://localhost:8501")

def main():
    # Obtener la ruta del directorio actual
    if getattr(sys, 'frozen', False):
        # Si se ejecuta como ejecutable
        application_path = os.path.dirname(sys.executable)
    else:
        # Si se ejecuta como script
        application_path = os.path.dirname(os.path.abspath(__file__))

    # Cambiar al directorio de la aplicación
    os.chdir(application_path)

    # Iniciar el navegador en un hilo separado
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    # Iniciar Streamlit
    try:
        subprocess.run([
            sys.executable,
            "-m", "streamlit", "run", "app.py",
            "--server.headless", "true",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\nVino Tracker detenido.")
        sys.exit(0)

if __name__ == "__main__":
    main()
