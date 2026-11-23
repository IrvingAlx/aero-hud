import os
from flask import Flask
from .models import db

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-solo-para-demo')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///aerospace.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # Importar Blueprints
    from .radar.routes import radar_bp
    from .payroll.routes import payroll_bp
    from .hangar.routes import hangar_bp
    from .logistics.routes import logistics_bp

    
    # Registrar Blueprints
    app.register_blueprint(radar_bp)
    app.register_blueprint(payroll_bp, url_prefix='/payroll')
    app.register_blueprint(hangar_bp, url_prefix='/hangar')
    app.register_blueprint(logistics_bp, url_prefix='/logistics')

    with app.app_context():
        db.create_all()

    return app