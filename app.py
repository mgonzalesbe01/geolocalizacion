from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import random
import string
import os
import pymysql

# Para usar PyMySQL como motor
pymysql.install_as_MySQLdb()

# Inicializa Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tu_clave_secreta')

# Configuración de la base de datos
db_url = os.environ.get("DATABASE_URL", "sqlite:///fallback.db")
if db_url.startswith("mysql://") and not db_url.startswith("mysql+pymysql://"):
    db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa SQLAlchemy
db = SQLAlchemy(app)

# Modelos
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)

class Dispositivo(db.Model):
    __tablename__ = 'dispositivo'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False, index=True)
    alias = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='dispositivos')
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    precision = db.Column(db.Float)

# Configura Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Rutas públicas
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/ping')
def ping():
    return "pong"

@app.route('/test-db')
def test_db():
    try:
        db.session.execute('SELECT 1')
        return "Conexión exitosa a la base de datos"
    except Exception as e:
        return f"Error de conexión: {str(e)}"

@app.route('/crear-tablas')
def crear_tablas():
    try:
        db.create_all()
        return "Tablas creadas exitosamente"
    except Exception as e:
        return f"Error al crear tablas: {str(e)}"

# Ruta de inicio de sesión
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        password = request.form.get('password')

        if not nombre or not password:
            return "Faltan credenciales", 400

        usuario = Usuario.query.filter_by(nombre=nombre).first()

        if not usuario or usuario.password != password:
            return "Credenciales incorrectas", 401

        login_user(usuario)
        return redirect(url_for('dashboard'))

    return render_template('login.html')

# Ruta para generar dispositivos únicos
@app.route('/registrar-dispositivo', methods=['POST'])
@login_required
def registrar_dispositivo():
    alias = request.form.get('alias')
    codigo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    nuevo = Dispositivo(codigo=codigo, alias=alias, usuario_id=current_user.id)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'codigo': codigo})

# Página para obtener ubicación
@app.route('/<string:codigo>')
def mostrar_pagina(codigo):
    dispositivo = Dispositivo.query.filter_by(codigo=codigo).first()
    if not dispositivo:
        return "Código inválido", 404
    return render_template('index.html', codigo=codigo)

# Actualizar ubicación del dispositivo
@app.route('/actualizar', methods=['POST'])
def actualizar_ubicacion():
    codigo = request.form.get('codigo')
    lat = request.form.get('latitud')
    lon = request.form.get('longitud')
    precision = request.form.get('precision')

    dispositivo = Dispositivo.query.filter_by(codigo=codigo).first()

    if dispositivo and lat and lon:
        dispositivo.lat = float(lat)
        dispositivo.lon = float(lon)
        dispositivo.precision = float(precision) if precision else None
        db.session.commit()
        return jsonify({'status': 'ok'})

    return jsonify({'status': 'error'}), 400

# API REST para el dashboard
@app.route('/api/ubicaciones')
@login_required
def api_ubicaciones():
    dispositivos = Dispositivo.query.filter_by(usuario_id=current_user.id).all()
    data = {}
    for d in dispositivos:
        if d.lat and d.lon:
            data[d.codigo] = {
                'lat': d.lat,
                'lon': d.lon,
                'alias': d.alias,
                'precision': d.precision
            }
    return jsonify(data)

# Evitar error con favicon.ico
@app.route('/favicon.ico')
def favicon():
    return "", 204

# Iniciar en modo desarrollo local
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)