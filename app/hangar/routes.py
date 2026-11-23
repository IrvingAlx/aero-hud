from flask import Blueprint, render_template, request, redirect, url_for
from app.models import db, HangarUnit, UserProfile
from app.utils import calcular_isr_2026_quincenal, calcular_neto_real, calcular_aguinaldo, calcular_prima_vacacional, calcular_ahorro_acumulado
from datetime import datetime

hangar_bp = Blueprint('hangar', __name__)

@hangar_bp.route('/', methods=['GET', 'POST'])
def index():
    unidades = HangarUnit.query.order_by(HangarUnit.tipo).all()
    user = UserProfile.query.first()
    
    show_modal = False
    
    # === DATOS BASE PARA LA SIMULACIÓN ===
    datos_ahorro = calcular_ahorro_acumulado(user.fecha_inicio, user.aportacion_ahorro)
    ahorro_acumulado = datos_ahorro['acumulado']
    salario_diario = user.sueldo_bruto_quincenal / 15
    isr_normal = calcular_isr_2026_quincenal(user.sueldo_bruto_quincenal)['isr_total']
    
    bono_bruto = salario_diario * 30
    modo_inverso = False
    deposito_target = 0

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_params':
            user.sueldo_bruto_quincenal = float(request.form.get('grossSalary', 0))
            user.imss_cfdi = float(request.form.get('imssCfdi', 0))
            user.isr_cfdi = float(request.form.get('isrCfdi', 0))
            user.aportacion_ahorro = float(request.form.get('savingsContribution', 0))
            user.dias_vacaciones = int(request.form.get('vacationDays', 12))
            fecha_str = request.form.get('startDate')
            if fecha_str:
                user.fecha_inicio = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            db.session.commit()
            return redirect(url_for('hangar.index'))
            
        elif action == 'reverse_calc':
            deposito_target = float(request.form.get('deposito_real', 0))
            # LEEMOS LO QUE DE VERDAD TE DEPOSITARON DE AHORRO (O usamos el calculado si lo dejas en blanco)
            fondo_real_str = request.form.get('fondo_real', '')
            fondo_real = float(fondo_real_str) if fondo_real_str else ahorro_acumulado
            
            modo_inverso = True
            show_modal = True
            
            limite_inferior = 0.0
            limite_superior = 200000.0
            for _ in range(100):
                mitad_bono_prueba = (limite_inferior + limite_superior) / 2
                bruto_prueba = user.sueldo_bruto_quincenal + mitad_bono_prueba
                isr_prueba = calcular_isr_2026_quincenal(bruto_prueba)['isr_total']
                
                # USAMOS EL FONDO REAL PARA LA PRUEBA
                neto_prueba = bruto_prueba - isr_prueba - user.imss_cfdi - user.otras_deducciones + fondo_real
                
                if neto_prueba < deposito_target: limite_inferior = mitad_bono_prueba
                else: limite_superior = mitad_bono_prueba
            bono_bruto = mitad_bono_prueba
            # Sobreescribimos el ahorro entregado para el resumen
            ahorro_acumulado = fondo_real

    # === MATEMÁTICA DEL BRIEFING ===
    bruto_gravable_total = user.sueldo_bruto_quincenal + bono_bruto
    isr_simulado = calcular_isr_2026_quincenal(bruto_gravable_total)
    neto_sin_ahorro = bruto_gravable_total - isr_simulado['isr_total'] - user.imss_cfdi - user.otras_deducciones
    
    simulacion = {
        'es_inverso': modo_inverso, 'deposito_ingresado': deposito_target, 'dias_bono': bono_bruto / salario_diario if salario_diario > 0 else 0,
        'bono_bruto': bono_bruto, 'bruto_total': bruto_gravable_total, 'isr_retenido': isr_simulado['isr_total'],
        'bracket': isr_simulado['porcentaje'], 'impacto_isr': isr_simulado['isr_total'] - isr_normal, 
        'ahorro_entregado': ahorro_acumulado, 'deposito_final': neto_sin_ahorro + ahorro_acumulado
    }

    neto_real = calcular_neto_real(user.sueldo_bruto_quincenal, user.isr_cfdi, user.imss_cfdi, user.aportacion_ahorro, user.otras_deducciones)

    return render_template('hangar.html', 
                           unidades=unidades, user=user, neto_real=neto_real,
                           isr_app=calcular_isr_2026_quincenal(user.sueldo_bruto_quincenal),
                           isr_diff=calcular_isr_2026_quincenal(user.sueldo_bruto_quincenal)['isr_total'] - user.isr_cfdi,
                           aguinaldo=calcular_aguinaldo(user.sueldo_bruto_quincenal),
                           prima=calcular_prima_vacacional(user.sueldo_bruto_quincenal, user.dias_vacaciones),
                           ahorro_acumulado=ahorro_acumulado, progreso_ahorro=datos_ahorro['porcentaje'],
                           simulacion=simulacion, show_modal=show_modal)

# === RUTAS DE TARJETAS ===
@hangar_bp.route('/add', methods=['POST'])
def add_unit():
    tipo = request.form.get('tipo')
    limite_saldo = float(request.form.get('limite_saldo') or 0)
    tasa_anual = float(request.form.get('tasa_anual') or 0) if tipo == 'AHORRO' else 0.0
    dia_corte = request.form.get('dia_corte')
    dia_pago = request.form.get('dia_pago')
    
    nueva_unidad = HangarUnit(
        institucion=request.form.get('institucion', '').upper(),
        nombre=request.form.get('nombre', '').upper(),
        tipo=tipo, limite_saldo=limite_saldo, tasa_anual=tasa_anual,
        dia_corte=int(dia_corte) if dia_corte and tipo in ['CREDITO', 'DEPARTAMENTAL'] else None,
        dia_pago=int(dia_pago) if dia_pago and tipo in ['CREDITO', 'DEPARTAMENTAL'] else None
    )
    db.session.add(nueva_unidad)
    db.session.commit()
    return redirect(url_for('hangar.index'))

@hangar_bp.route('/delete/<int:id>', methods=['POST'])
def delete_unit(id):
    db.session.delete(HangarUnit.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('hangar.index'))

@hangar_bp.route('/edit/<int:id>', methods=['POST'])
def edit_unit(id):
    unidad = HangarUnit.query.get_or_404(id)
    tipo = request.form.get('tipo')
    unidad.institucion = request.form.get('institucion', '').upper()
    unidad.nombre = request.form.get('nombre', '').upper()
    unidad.tipo = tipo
    unidad.limite_saldo = float(request.form.get('limite_saldo') or 0)
    
    if tipo == 'AHORRO':
        unidad.tasa_anual = float(request.form.get('tasa_anual') or 0)
        unidad.dia_corte, unidad.dia_pago = None, None
    elif tipo in ['CREDITO', 'DEPARTAMENTAL']:
        unidad.tasa_anual = 0.0
        dc = request.form.get('dia_corte')
        dp = request.form.get('dia_pago')
        unidad.dia_corte = int(dc) if dc and tipo == 'CREDITO' else None
        unidad.dia_pago = int(dp) if dp else None
    else:
        unidad.tasa_anual, unidad.dia_corte, unidad.dia_pago = 0.0, None, None

    db.session.commit()
    return redirect(url_for('hangar.index'))