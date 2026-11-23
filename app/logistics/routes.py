from flask import Blueprint, render_template, request, redirect, url_for
from app.models import db, Tanda, LogisticsLoad, HangarUnit, MSIPurchase
from app.utils import calcular_estado_tanda
from datetime import datetime


logistics_bp = Blueprint('logistics', __name__)

@logistics_bp.route('/')
def index():
    tandas_db = Tanda.query.all()
    tandas = []
    from app.utils import calcular_estado_tanda
    for t in tandas_db:
        estado = calcular_estado_tanda(t.fecha_inicio, t.total_quincenas)
        tandas.append({"db": t, "estado": estado})

    gastos = LogisticsLoad.query.all()
    unidades = HangarUnit.query.all()
    
    # ¡ESTA ERA LA LÍNEA QUE FALTABA!
    from app.models import MSIPurchase
    msi_list = MSIPurchase.query.all()
    
    return render_template('logistics.html', tandas=tandas, gastos=gastos, unidades=unidades, msi_list=msi_list)

@logistics_bp.route('/tanda/add', methods=['POST'])
def add_tanda():
    fecha_str = request.form.get('fecha_inicio')
    nueva_tanda = Tanda(
        nombre=request.form.get('nombre', '').upper(),
        monto_quincenal=float(request.form.get('monto')),
        total_quincenas=int(request.form.get('total')),
        fecha_inicio=datetime.strptime(fecha_str, '%Y-%m-%d').date(),
        mi_turno=int(request.form.get('turno') or 1)
    )
    db.session.add(nueva_tanda)
    db.session.commit()
    return redirect(url_for('logistics.index'))

# --- (Las rutas de expense/add y expense/delete quedan igual, pégalas abajo) ---
@logistics_bp.route('/expense/add', methods=['POST'])
def add_expense():
    tipo = request.form.get('tipo')
    hangar_id = request.form.get('hangar_unit_id')
    hangar_id = int(hangar_id) if hangar_id and tipo != 'EXTERNAL' else None
    dia_cobro = request.form.get('dia_cobro')
    dia_cobro = int(dia_cobro) if dia_cobro and tipo == 'SUBSCRIPTION' else None

    nuevo_gasto = LogisticsLoad(
        concepto=request.form.get('concepto', '').upper(),
        tipo=tipo,
        monto=float(request.form.get('monto', 0)),
        frecuencia=request.form.get('frecuencia', 'QUINCENAL'),
        destinatario=request.form.get('destinatario', '').upper(),
        dia_cobro=dia_cobro,
        hangar_unit_id=hangar_id
    )
    db.session.add(nuevo_gasto)
    db.session.commit()
    return redirect(url_for('logistics.index'))

@logistics_bp.route('/expense/delete/<int:id>', methods=['POST'])
def delete_expense(id):
    gasto = LogisticsLoad.query.get_or_404(id)
    db.session.delete(gasto)
    db.session.commit()
    return redirect(url_for('logistics.index'))

@logistics_bp.route('/expense/edit/<int:id>', methods=['POST'])
def edit_expense(id):
    gasto = LogisticsLoad.query.get_or_404(id)
    tipo = request.form.get('tipo')
    
    gasto.tipo = tipo
    gasto.concepto = request.form.get('concepto', '').upper()
    gasto.monto = float(request.form.get('monto', 0))
    gasto.frecuencia = request.form.get('frecuencia', 'QUINCENAL')
    
    if tipo == 'EXTERNAL':
        gasto.destinatario = request.form.get('destinatario', '').upper()
        gasto.hangar_unit_id = None
        gasto.dia_cobro = None
    else:
        gasto.destinatario = None
        gasto.hangar_unit_id = request.form.get('hangar_unit_id')
        dia = request.form.get('dia_cobro')
        gasto.dia_cobro = int(dia) if dia and tipo == 'SUBSCRIPTION' else None

    db.session.commit()
    return redirect(url_for('logistics.index'))

# --- RUTAS DE COMPRAS A MESES (MSI) ---
@logistics_bp.route('/msi/add', methods=['POST'])
def add_msi():
    monto_total = float(request.form.get('monto_total', 0))
    meses_totales = int(request.form.get('meses_totales', 1))
    
    nuevo_msi = MSIPurchase(
        concepto=request.form.get('concepto', '').upper(),
        monto_total=monto_total,
        mensualidad=monto_total / meses_totales,
        meses_totales=meses_totales,
        meses_pagados=int(request.form.get('meses_pagados') or 0),
        hangar_unit_id=int(request.form.get('hangar_unit_id'))
    )
    db.session.add(nuevo_msi)
    db.session.commit()
    return redirect(url_for('logistics.index'))

@logistics_bp.route('/msi/pagar/<int:id>')
def pagar_msi(id):
    msi = MSIPurchase.query.get_or_404(id)
    if msi.meses_pagados < msi.meses_totales:
        msi.meses_pagados += 1
        db.session.commit()
    return redirect(url_for('logistics.index'))

# --- EDICIÓN Y BORRADO DE TANDAS ---
@logistics_bp.route('/tanda/delete/<int:id>', methods=['POST'])
def delete_tanda(id):
    tanda = Tanda.query.get_or_404(id)
    db.session.delete(tanda)
    db.session.commit()
    return redirect(url_for('logistics.index'))

@logistics_bp.route('/tanda/edit/<int:id>', methods=['POST'])
def edit_tanda(id):
    tanda = Tanda.query.get_or_404(id)
    tanda.nombre = request.form.get('nombre', '').upper()
    tanda.monto_quincenal = float(request.form.get('monto', 0))
    tanda.total_quincenas = int(request.form.get('total', 1))
    
    fecha_str = request.form.get('fecha_inicio')
    if fecha_str:
        tanda.fecha_inicio = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
    tanda.mi_turno = int(request.form.get('turno') or 1)
    db.session.commit()
    return redirect(url_for('logistics.index'))

# --- EDICIÓN Y BORRADO DE MSI ---
@logistics_bp.route('/msi/delete/<int:id>', methods=['POST'])
def delete_msi(id):
    msi = MSIPurchase.query.get_or_404(id)
    db.session.delete(msi)
    db.session.commit()
    return redirect(url_for('logistics.index'))

@logistics_bp.route('/msi/edit/<int:id>', methods=['POST'])
def edit_msi(id):
    msi = MSIPurchase.query.get_or_404(id)
    msi.concepto = request.form.get('concepto', '').upper()
    msi.monto_total = float(request.form.get('monto_total', 0))
    msi.meses_totales = int(request.form.get('meses_totales', 1))
    msi.meses_pagados = int(request.form.get('meses_pagados', 0)) # NUEVO DATO
    msi.mensualidad = msi.monto_total / msi.meses_totales
    msi.hangar_unit_id = int(request.form.get('hangar_unit_id'))
    db.session.commit()
    return redirect(url_for('logistics.index'))