from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
import string
import os
from werkzeug.middleware.proxy_fix import ProxyFix
import time

# Inicializa Flask
app = Flask(__name__)
app.secret_key = 'clave_secreta_temporal'

# Configuración de la base de datos SQLite (solo para producción)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///geolocalizacion.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa SQLAlchemy
db = SQLAlchemy(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Modelo único: Dispositivo
class Dispositivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False)
    alias = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    precision = db.Column(db.Float)
    ultima_conexion = db.Column(db.Float, default=0.0)  # Asegúrate que este campo existe
    ultima_actualizacion = db.Column(db.Float, default=0.0)

# Crea tablas al iniciar
with app.app_context():
    db.create_all()

# Rutas principales

@app.route('/')
def home():
    return redirect(url_for('dashboard'))


@app.route('/generar-enlace', methods=['POST'])
def generar_enlace():
    alias = request.form.get('alias', '').strip()  # Asegura que alias es string y limpia espacios
    codigo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    nuevo = Dispositivo(codigo=codigo, alias=alias if alias else None)  # Guarda None si alias está vacío
    db.session.add(nuevo)
    db.session.commit()
    
    return jsonify({
        'codigo': codigo,
        'alias': alias or codigo,  # Muestra el alias o el código si alias está vacío
        'enlace': f'https://{request.host}/{codigo}'
    })
    
@app.route('/eliminar/<string:codigo>', methods=['DELETE'])
def eliminar_dispositivo(codigo):
    disp = Dispositivo.query.filter_by(codigo=codigo).first()
    if not disp:
        return jsonify({'status': 'error', 'mensaje': 'Código no encontrado'}), 404
    
    try:
        db.session.delete(disp)
        db.session.commit()
        return jsonify({'status': 'ok', 'mensaje': f'Código {codigo} eliminado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'mensaje': str(e)}), 500
    

@app.route('/registrar-dispositivo', methods=['POST'])
def registrar_dispositivo():
    alias = request.form.get('alias')
    codigo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    nuevo = Dispositivo(codigo=codigo, alias=alias)
    db.session.add(nuevo)
    db.session.commit()
    
    return jsonify({'codigo': codigo})


@app.route('/<string:codigo>')
def mostrar_pagina(codigo):
    # Evitar que favicon.ico sea tratado como código
    if codigo == 'favicon.ico':
        return "", 204
    
    dispositivo = Dispositivo.query.filter_by(codigo=codigo).first()
    if not dispositivo:
        return "Código inválido", 404
    
    return render_template('index.html', codigo=codigo)

@app.route('/favicon.ico')
def favicon():
    return "", 204

@app.route('/api/ubicaciones')
def api_ubicaciones():
    dispositivos = Dispositivo.query.all()
    data = {}
    for d in dispositivos:
        if d.codigo == 'favicon.ico':
            continue
        if d.lat and d.lon:
            data[d.codigo] = {
                'lat': d.lat,
                'lon': d.lon,
                'alias': d.alias or d.codigo
            }
    return jsonify(data)


@app.route('/api/links-generados')
def api_links_generados():
    dispositivos = Dispositivo.query.all()
    data = []
    for d in dispositivos:
        if d.codigo == 'favicon.ico':
            continue
        data.append({
            'codigo': d.codigo,
            'alias': d.alias or d.codigo
        })
    return jsonify(data)

ESTADO_ACTIVO_SEGUNDOS = 30  # Considera activo por 30 segundos sin latido

@app.route('/api/dispositivos')
def api_dispositivos():
    ahora = time.time()
    dispositivos = Dispositivo.query.all()
    data = []
    for d in dispositivos:
        estado = 'activo' if (ahora - (d.ultima_conexion or 0)) < ESTADO_ACTIVO_SEGUNDOS else 'inactivo'
        data.append({
            'codigo': d.codigo,
            'estado': estado,
            # ... otros campos
        })
    return jsonify(data)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')  # Asegúrate de tener este archivo en templates/

def limpiar_dispositivos_inactivos():
    with app.app_context():
        limite = time.time() - 3600  # 1 hora sin actividad
        inactivos = Dispositivo.query.filter(Dispositivo.ultima_conexion < limite).all()
        
        for disp in inactivos:
            db.session.delete(disp)
        
        db.session.commit()

# Añade al modelo Dispositivo:
ultima_conexion = db.Column(db.Float, default=0.0, nullable=False)  # No puede ser NULL

# Y en las rutas:
@app.route('/latido', methods=['POST'])
def latido():
    codigo = request.form.get('codigo')
    disp = Dispositivo.query.filter_by(codigo=codigo).first()
    if disp:
        disp.ultima_conexion = time.time()
        db.session.commit()
    return jsonify({'status': 'ok'})




@app.route('/actualizar', methods=['POST'])
def actualizar_ubicacion():
    try:
        codigo = request.form['codigo']
        lat = float(request.form['latitud'])
        lon = float(request.form['longitud'])
        
        print(f"Recibida ubicación de {codigo}: {lat}, {lon}")  # ← Log para depuración
        
        disp = Dispositivo.query.filter_by(codigo=codigo).first()
        if disp:
            disp.lat = lat
            disp.lon = lon
            disp.ultima_conexion = time.time()
            db.session.commit()
            return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Error al actualizar ubicación: {str(e)}")  # ← Log de errores
    return jsonify({'status': 'error'}), 400



@app.route('/dispositivo/<codigo>/estado')
def estado_dispositivo(codigo):
    disp = Dispositivo.query.filter_by(codigo=codigo).first()
    return jsonify({
        'activo': disp.ultima_conexion > time.time() - 60,
        'ubicacion': {
            'lat': disp.lat,
            'lon': disp.lon,
            'timestamp': disp.ultima_conexion
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)