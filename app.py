from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import random
import string
import os
import pymysql
from werkzeug.middleware.proxy_fix import ProxyFix
import time  # Añade esta línea con los otros imports
from urllib.parse import urlparse

# Primero: Crear la aplicación Flask
app = Flask(__name__)

# Segundo: Configurar la clave secreta
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Tercero: Inicializar SQLAlchemy (sin configurar URL todavía)
db = SQLAlchemy()

# Cuarto: Definir tus modelos aquí
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Dispositivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False)
    # ... otros campos

# Quinto: Función para configurar la base de datos
def configure_database():
    # Obtener URL de conexión
    db_url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
    
    if db_url:
        if db_url.startswith('mysql://'):
            db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'
        print("⚠️ Usando SQLite local (MYSQL_URL no encontrada)")
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Inicializar la aplicación con la base de datos
    db.init_app(app)
    
    # Crear tablas si no existen
    with app.app_context():
        try:
            db.create_all()
            print("✅ Tablas creadas exitosamente")
        except Exception as e:
            print(f"❌ Error al crear tablas: {str(e)}")

# Sexto: Configurar e inicializar la base de datos
configure_database()

# El resto de tu aplicación (rutas, etc.) viene después
@app.route('/')
def home():
    return "¡Aplicación funcionando!"

# Inicializa SQLAlchemy
db = SQLAlchemy(app)

# Modelos
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Dispositivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False)
    alias = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    precision = db.Column(db.Float)

# Justo después de definir tus modelos
with app.app_context():
    try:
        print("Intentando crear tablas...")
        db.create_all()
        print("Tablas creadas exitosamente!")
    except Exception as e:
        print(f"Error al crear tablas: {str(e)}")

# Configura Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.route('/db-config')
def db_config():
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    return jsonify({
        "database": "MySQL" if "mysql" in db_url else "PostgreSQL" if "postgresql" in db_url else "SQLite",
        "url": db_url,
        "is_railway": "railway" in db_url,
        "variables": dict(os.environ)
    })

@app.route('/db-check')
def db_check():
    try:
        db.session.execute("SELECT 1")
        return jsonify({
            "status": "success",
            "database": "MySQL",
            "url": app.config['SQLALCHEMY_DATABASE_URI'],
            "tables": db.engine.table_names()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "current_url": app.config.get('SQLALCHEMY_DATABASE_URI'),
            "available_vars": {k: v for k, v in os.environ.items() if 'URL' in k or 'DB' in k}
        }), 500

# Configuración de timeout para Flask
@app.before_request
def handle_timeout():
    from flask import request
    request.start_time = time.time()  # Ahora time está importado

@app.after_request
def log_request_time(response):
    from flask import request
    try:
        duration = time.time() - getattr(request, 'start_time', time.time())
        if duration > 5:
            app.logger.warning(f'Request took {duration:.2f}s: {request.path}')
    except Exception as e:
        app.logger.error(f'Error logging request time: {str(e)}')
    return response

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Rutas públicas
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/ping')
def ping():
    try:
        # Verificar conexión a DB
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'pong',
            'database': 'connected',
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({
            'status': 'pong',
            'database': 'error',
            'error': str(e)
        }), 500

@app.route('/health-check')
def health_check():
    try:
        # Verificar conexión a DB
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'db_connection': 'ok',
            'app': 'running'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'db_error': str(e)
        }), 500

    
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
            
            login_user(nuevo_usuario)
            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            return f"Error al registrar: {str(e)}", 500

    return render_template('register.html')

@app.route('/routes')
def list_routes():
    import urllib.parse
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = urllib.parse.unquote(f"{rule.endpoint:50s} {methods:20s} {rule}")
        output.append(line)
    return '<pre>' + '\n'.join(sorted(output)) + '</pre>'

@app.route('/dashboard')
@login_required
def dashboard():  # Cambia el nombre de la función para ser más explícito
    return render_template('dashboard.html', usuario=current_user)

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