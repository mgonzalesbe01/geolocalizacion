from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import random
import string
import os

# Inicializa Flask
app = Flask(__name__)
app.secret_key = 'clave_secreta_temporal'

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///geolocalizacion.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa SQLAlchemy
db = SQLAlchemy(app)

# Modelo único: Dispositivo
class Dispositivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    precision = db.Column(db.Float)
    ultima_actualizacion = db.Column(db.Float, default=0.0)

# Crea tablas al iniciar
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return redirect(url_for('mapa'))

@app.route('/mapa')
def mapa():
    return render_template('mapa.html')

@app.route('/<string:codigo>')
def dispositivo(codigo):
    disp = Dispositivo.query.filter_by(codigo=codigo).first()
    if not disp:
        # Si no existe, crearlo
        disp = Dispositivo(codigo=codigo)
        db.session.add(disp)
        db.session.commit()

    return render_template('index.html', codigo=codigo)

@app.route('/actualizar', methods=['POST'])
def actualizar_ubicacion():
    codigo = request.form.get('codigo')
    lat = request.form.get('latitud')
    lon = request.form.get('longitud')
    precision = request.form.get('precision')

    disp = Dispositivo.query.filter_by(codigo=codigo).first()
    if disp and lat and lon:
        disp.lat = float(lat)
        disp.lon = float(lon)
        disp.precision = float(precision) if precision else None
        db.session.commit()
        return jsonify({'status': 'ok'})

    return jsonify({'status': 'error'}), 400

@app.route('/api/ubicaciones')
def api_ubicaciones():
    dispositivos = Dispositivo.query.all()
    data = {}
    for d in dispositivos:
        if d.lat and d.lon:
            data[d.codigo] = {
                'lat': d.lat,
                'lon': d.lon,
                'precision': d.precision
            }
    return jsonify(data)