"""
Production entry point for PyInstaller bundle.
Uses waitress (Windows-friendly WSGI server).

Run directly:   python server.py
PyInstaller:    pyinstaller --onedir server.py
"""
import os

from waitress import serve
from app import create_app

if __name__ == '__main__':
    port = int(os.environ.get('BACKEND_PORT', 5000))
    app = create_app()
    print(f'[backend] Listening on http://127.0.0.1:{port}', flush=True)
    serve(app, host='127.0.0.1', port=port, threads=4)
