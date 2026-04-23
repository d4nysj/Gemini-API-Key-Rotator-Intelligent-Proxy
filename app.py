import os
import random
import sqlite3
import requests
import re
import time
from flask import Flask, render_template, request, redirect, jsonify, Response

app = Flask(__name__)
DB_FILE = "keys.db"

# --- CONFIGURACIÓN BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY, key TEXT UNIQUE, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS models (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    # NUEVA: Tabla de Logs
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
        endpoint TEXT, 
        model TEXT, 
        key_desc TEXT, 
        status INTEGER)''')
    conn.commit()
    conn.close()

def get_keys():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key, description FROM api_keys")
    keys = c.fetchall()
    conn.close()
    return keys

def get_models():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM models")
    models = [row[0] for row in c.fetchall()]
    conn.close()
    return models if models else ["gemini-1.5-flash"]

def get_logs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Obtenemos los últimos 50 logs ordenados por tiempo
    c.execute("SELECT timestamp, endpoint, model, key_desc, status FROM logs ORDER BY id DESC LIMIT 50")
    logs = c.fetchall()
    conn.close()
    return logs

def save_log(endpoint, model, key_desc, status):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO logs (endpoint, model, key_desc, status) VALUES (?, ?, ?, ?)", 
                  (endpoint, model, key_desc, status))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error guardando log: {e}")

# --- RUTAS ---
@app.route('/')
def index():
    return render_template('index.html', keys=get_keys(), models=get_models(), logs=get_logs())

@app.route('/add', methods=['POST'])
def add_key():
    key = request.form.get('key').strip()
    desc = request.form.get('description').strip()
    if key:
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO api_keys (key, description) VALUES (?, ?)", (key, desc))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError: pass
    return redirect('/')

@app.route('/delete', methods=['POST'])
def delete_key():
    key = request.form.get('key')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM api_keys WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_model', methods=['POST'])
def add_model():
    name = request.form.get('name').strip()
    if name:
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO models (name) VALUES (?)", (name,))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError: pass
    return redirect('/')

@app.route('/delete_model', methods=['POST'])
def delete_model():
    name = request.form.get('name')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM models WHERE name=?", (name,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM logs")
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/export')
def export_keys():
    keys = get_keys()
    content = "\n".join([f"{k[0]}|{k[1]}" for k in keys])
    return Response(content, mimetype="text/plain", headers={"Content-disposition": "attachment; filename=gemini_keys.txt"})

@app.route('/import', methods=['POST'])
def import_keys():
    file = request.files['file']
    if file:
        lines = file.read().decode('utf-8').splitlines()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        for line in lines:
            if '|' in line:
                key, desc = line.split('|', 1)
                try:
                    c.execute("INSERT INTO api_keys (key, description) VALUES (?, ?)", (key.strip(), desc.strip()))
                except sqlite3.IntegrityError: pass
        conn.commit()
        conn.close()
    return redirect('/')

# --- PROXY INTELIGENTE ---
@app.route('/proxy/<path:endpoint>', methods=['GET', 'POST'])
def proxy(endpoint):
    keys_db = get_keys()
    if not keys_db:
        return jsonify({"error": "No hay API Keys disponibles."}), 500
    
    # Crear un diccionario para buscar la descripción por key
    desc_map = {k[0]: k[1] for k in keys_db}
    llaves_disponibles = [k[0] for k in keys_db]
    random.shuffle(llaves_disponibles)

    modelos_configurados = get_models()

    modelo_original = None
    match = re.search(r'models/([^:]+):', endpoint)
    if match:
        modelo_original = match.group(1)

    modelos_a_probar = modelos_configurados.copy()
    if modelo_original and modelo_original not in modelos_a_probar:
        modelos_a_probar.insert(0, modelo_original)

    google_resp = None
    intento_llave = 0

    for modelo_actual in modelos_a_probar:
        if modelo_actual and modelo_original:
            endpoint_modificado = endpoint.replace(f"models/{modelo_original}:", f"models/{modelo_actual}:")
        else:
            endpoint_modificado = endpoint

        for _ in range(2): 
            llave_elegida = llaves_disponibles[intento_llave % len(llaves_disponibles)]
            intento_llave += 1
            google_url = f"https://generativelanguage.googleapis.com/{endpoint_modificado}?key={llave_elegida}"
            
            try:
                google_resp = requests.request(
                    method=request.method,
                    url=google_url,
                    headers={'Content-Type': 'application/json'},
                    data=request.get_data(),
                    timeout=20
                )
                
                # GUARDAR LOG
                save_log(endpoint, modelo_actual, desc_map.get(llave_elegida, "Desconocida"), google_resp.status_code)

                if google_resp.status_code == 200:
                    return Response(google_resp.content, google_resp.status_code, content_type=google_resp.headers.get('Content-Type'))
                if google_resp.status_code == 400:
                    return Response(google_resp.content, google_resp.status_code, content_type=google_resp.headers.get('Content-Type'))
                if google_resp.status_code == 503:
                    break 
            except Exception as e:
                print(f"Error en proxy: {e}")
                time.sleep(1)

    if google_resp:
        return Response(google_resp.content, google_resp.status_code, content_type=google_resp.headers.get('Content-Type'))
    return jsonify({"error": "Fallo crítico en el Proxy."}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5005)
