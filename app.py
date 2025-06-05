from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import random
import string
import os
from datetime import datetime

# Inicializa Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-123')  # Cambia esto en producción

# Configuración de la base de datos
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Mejora la estabilidad de la conexión
    'pool_recycle': 300,    # Recicla conexiones cada 5 minutos
}

# Inicializa SQLAlchemy
db = SQLAlchemy(app)

# Modelos (ahora definidos en el mismo archivo para evitar importaciones circulares)
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    dispositivos = db.relationship('Dispositivo', backref='usuario', lazy=True)

class Dispositivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False)
    alias = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    precision = db.Column(db.Float)
    ultima_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Configura Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Crear tablas al iniciar (solo en desarrollo)
with app.app_context():
    db.create_all()

# Rutas
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/crear-tablas')
def crear_tablas():
    try:
        db.create_all()
        return "Tablas creadas exitosamente"
    except Exception as e:
        app.logger.error(f"Error al crear tablas: {e}")
        return f"Error al crear tablas: {str(e)}", 500

@app.route('/test-db')
def test_db():
    try:
        db.session.execute('SELECT 1')
        return "Conexión exitosa a la base de datos"
    except Exception as e:
        return f"Error de conexión: {str(e)}", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            password = request.form['password']

            if Usuario.query.filter_by(nombre=nombre).first():
                return "Nombre de usuario ya existe", 409

            nuevo_usuario = Usuario(nombre=nombre, password=password)
            db.session.add(nuevo_usuario)
            db.session.commit()
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error en registro: {e}")
            return f"Error: {str(e)}", 500

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            usuario = Usuario.query.filter_by(nombre=request.form['nombre']).first()
            if usuario and usuario.password == request.form['password']:
                login_user(usuario)
                return redirect(url_for('dashboard'))
            return "Credenciales incorrectas", 401
        except Exception as e:
            app.logger.error(f"Error en login: {e}")
            return "Error en el servidor", 500

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', usuario=current_user)

@app.route('/registrar-dispositivo', methods=['POST'])
@login_required
def registrar_dispositivo():
    try:
        alias = request.form['alias']
        codigo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        dispositivo = Dispositivo(codigo=codigo, alias=alias, usuario_id=current_user.id)
        db.session.add(dispositivo)
        db.session.commit()
        return jsonify({'codigo': codigo, 'alias': alias})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/<string:codigo>')
def mostrar_pagina(codigo):
    dispositivo = Dispositivo.query.filter_by(codigo=codigo).first_or_404()
    return render_template('index.html', codigo=codigo)

@app.route('/actualizar', methods=['POST'])
def actualizar_ubicacion():
    try:
        dispositivo = Dispositivo.query.filter_by(codigo=request.form['codigo']).first_or_404()
        dispositivo.lat = float(request.form['latitud'])
        dispositivo.lon = float(request.form['longitud'])
        dispositivo.precision = float(request.form.get('precision', 0))
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/ubicaciones')
@login_required
def api_ubicaciones():
    dispositivos = Dispositivo.query.filter_by(usuario_id=current_user.id).all()
    data = {
        d.codigo: {
            'lat': d.lat,
            'lon': d.lon,
            'precision': d.precision,
            'alias': d.alias,
            'ultima_actualizacion': d.ultima_actualizacion.isoformat() if d.ultima_actualizacion else None
        }
        for d in dispositivos if d.lat is not None and d.lon is not None
    }
    return jsonify(data)

@app.route('/favicon.ico')
def favicon():
    return "", 204

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)