from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import random
import string
import os
import pymysql
from werkzeug.middleware.proxy_fix import ProxyFix
import time
from urllib.parse import urlparse

# Inicialización de la aplicación
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# =============================================
# CONFIGURACIÓN MANUAL DE LA BASE DE DATOS MYSQL
# =============================================

# Obtener credenciales de las variables de entorno
MYSQL_CREDENTIALS = {
    'user': os.environ.get('MYSQLUSER', 'root'),
    'password': os.environ.get('MYSQL_ROOT_PASSWORD', ''),  # Sin valor por defecto
    'host': os.environ.get('MYSQLHOST', 'containers.railway.app'),  # Dominio público
    'port': os.environ.get('MYSQLPORT', '3306'),
    'database': os.environ.get('MYSQLDATABASE', 'railway')
}

# Construir la URL de conexión manualmente
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{MYSQL_CREDENTIALS['user']}:{MYSQL_CREDENTIALS['password']}"
    f"@{MYSQL_CREDENTIALS['host']}:{MYSQL_CREDENTIALS['port']}"
    f"/{MYSQL_CREDENTIALS['database']}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 5,
    'max_overflow': 10
}

# =============================================
# INICIALIZACIÓN DE EXTENSIONES
# =============================================

db = SQLAlchemy(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# =============================================
# MODELOS DE BASE DE DATOS
# =============================================

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    dispositivos = db.relationship('Dispositivo', backref='usuario', lazy=True)

class Dispositivo(db.Model):
    __tablename__ = 'dispositivo'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(8), unique=True, nullable=False)
    alias = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    precision = db.Column(db.Float)
    ultima_actualizacion = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                                   onupdate=db.func.current_timestamp())

# =============================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# =============================================

def initialize_database():
    with app.app_context():
        try:
            # Verificar conexión
            db.engine.connect()
            print("✅ Conexión a MySQL establecida correctamente")
            
            # Crear tablas si no existen
            db.create_all()
            print("✅ Tablas creadas/verificadas correctamente")
            
            # Verificar tablas existentes
            inspector = db.inspect(db.engine)
            print("📊 Tablas existentes:", inspector.get_table_names())
            
        except Exception as e:
            print(f"❌ Error al inicializar la base de datos: {str(e)}")
            # Opcional: Puedes agregar aquí un fallback a SQLite si lo deseas
            raise RuntimeError("No se pudo conectar a la base de datos MySQL")

# Llamar a la inicialización al arrancar
initialize_database()

# =============================================
# RUTAS DE VERIFICACIÓN
# =============================================

@app.route('/db-info')
def db_info():
    """Endpoint para verificar la conexión a la base de datos"""
    try:
        # Obtener información de la conexión
        db.session.execute('SELECT 1')
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Obtener estadísticas de tablas
        usuarios = Usuario.query.count()
        dispositivos = Dispositivo.query.count()
        
        return jsonify({
            "status": "success",
            "database": "MySQL",
            "url": db_url,
            "tables": db.engine.table_names(),
            "stats": {
                "usuarios": usuarios,
                "dispositivos": dispositivos
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "config": {
                "db_url": app.config.get('SQLALCHEMY_DATABASE_URI'),
                "env_vars": {k: v for k, v in os.environ.items() if 'MYSQL' in k}
            }
        }), 500

# =============================================
# RUTAS PRINCIPALES (Mantén tus rutas existentes)
# =============================================

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        password = request.form.get('password')

        if not nombre or not password:
            return "Faltan credenciales", 400

        usuario = Usuario.query.filter_by(nombre=nombre).first()

        if usuario and usuario.password == password:
            login_user(usuario)
            return redirect(url_for('dashboard'))
        return "Credenciales incorrectas", 401

    return render_template('login.html')  # Se eliminó el paréntesis extra aquí

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)