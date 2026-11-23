import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sueldo_bruto_quincenal = db.Column(db.Float, default=0.0)
    imss_cfdi = db.Column(db.Float, default=0.0)
    isr_cfdi = db.Column(db.Float, default=0.0)
    aportacion_ahorro = db.Column(db.Float, default=0.0)
    otras_deducciones = db.Column(db.Float, default=0.0)
    fecha_inicio = db.Column(db.Date, nullable=True)
    dias_vacaciones = db.Column(db.Integer, default=12)
    meta_gasto_diario = db.Column(db.Float, default=0.0)
    meta_ahorro_mensual = db.Column(db.Float, default=0.0)

class HangarUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    institucion = db.Column(db.String(50), nullable=True) 
    nombre = db.Column(db.String(50), nullable=False)     
    tipo = db.Column(db.String(20))                       
    limite_saldo = db.Column(db.Float, default=0.0)       
    tasa_anual = db.Column(db.Float, default=0.0)         
    dia_corte = db.Column(db.Integer, nullable=True)      
    dia_pago = db.Column(db.Integer, nullable=True)
    deuda_corte = db.Column(db.Float, default=0.0) # Lo que debes del mes anterior
    ultimo_mes_conciliado = db.Column(db.Integer, default=0)
        
class LogisticsLoad(db.Model): # Cargas/Gastos Recurrentes
    id = db.Column(db.Integer, primary_key=True)
    concepto = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50)) # EXTERNAL, SAVINGS, CARD_PAYMENT, SUBSCRIPTION, BUDGET
    monto = db.Column(db.Float, nullable=False)
    frecuencia = db.Column(db.String(20), default='QUINCENAL') # QUINCENAL, MENSUAL, SEMANAL
    destinatario = db.Column(db.String(100), nullable=True)
    dia_cobro = db.Column(db.Integer, nullable=True)
    
    # Vínculo con la tarjeta de donde sale el dinero
    hangar_unit_id = db.Column(db.Integer, db.ForeignKey('hangar_unit.id'), nullable=True)
    hangar_unit = db.relationship('HangarUnit', backref='cargas_vinculadas')

class Tanda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    monto_quincenal = db.Column(db.Float, nullable=False)
    total_quincenas = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False) # <--- El sistema usará esto
    mi_turno = db.Column(db.Integer, nullable=True) # En qué quincena me pagan a mi

class MSIPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    concepto = db.Column(db.String(100), nullable=False)
    monto_total = db.Column(db.Float, nullable=False)
    mensualidad = db.Column(db.Float, nullable=False)
    meses_totales = db.Column(db.Integer, nullable=False)
    meses_pagados = db.Column(db.Integer, default=0)
    
    # Vinculado siempre a una tarjeta de crédito o departamental
    hangar_unit_id = db.Column(db.Integer, db.ForeignKey('hangar_unit.id'), nullable=False)
    hangar_unit = db.relationship('HangarUnit', backref='compras_msi_vinculadas')

class VariableBudget(db.Model): 
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    limite_maximo = db.Column(db.Float, nullable=False)
    monto_gastado = db.Column(db.Float, default=0.0)
    ultimo_mes_reseteo = db.Column(db.Integer, default=datetime.date.today().month) # NUEVO: Control de mes
    
    hangar_unit_id = db.Column(db.Integer, db.ForeignKey('hangar_unit.id'), nullable=True)
    hangar_unit = db.relationship('HangarUnit', backref='presupuestos_vinculados')
    
    # NUEVO: Relación para poder listar los gastos en el modal
    historial_gastos = db.relationship('BudgetTransaction', backref='presupuesto', lazy=True, cascade="all, delete-orphan")
    
class BudgetTransaction(db.Model): # El registro de cada vez que le das al [+]
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('variable_budget.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=datetime.date.today)
    nota = db.Column(db.String(100), nullable=True)

class CardTransaction(db.Model): # Gastos directos a tarjeta (One-off)
    id = db.Column(db.Integer, primary_key=True)
    hangar_unit_id = db.Column(db.Integer, db.ForeignKey('hangar_unit.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=datetime.date.today)
    nota = db.Column(db.String(100), nullable=True)
    categoria = db.Column(db.String(50), nullable=False)
    
    hangar_unit = db.relationship('HangarUnit', backref='transacciones_directas')

