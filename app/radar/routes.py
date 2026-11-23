from flask import Blueprint, render_template, request, redirect, url_for
from app.models import db, UserProfile, LogisticsLoad, Tanda, HangarUnit, MSIPurchase, VariableBudget, BudgetTransaction, CardTransaction
from app.utils import calcular_neto_real, calcular_liquidez, obtener_info_quincena_actual, calcular_estado_tanda, calcular_ahorro_acumulado
import datetime 
import calendar

radar_bp = Blueprint('radar', __name__)

CATEGORIAS_GASTO = ['SUPERMERCADO', 'RESTAURANTES/COMIDA', 'TRANSPORTE/GAS', 'SALUD/FARMACIA', 'ENTRETENIMIENTO', 'COMPRAS', 'SERVICIOS', 'OTROS']

def obtener_rango_corte_actual(u, hoy):
    dia_corte = u.dia_corte
    if not dia_corte:
        primer_dia = datetime.date(hoy.year, hoy.month, 1)
        ultimo_dia = datetime.date(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1])
        return primer_dia, ultimo_dia

    if u.ultimo_mes_conciliado == hoy.month:
        ultimo_dia_mes_actual = calendar.monthrange(hoy.year, hoy.month)[1]
        dia_ini = min(dia_corte + 1, ultimo_dia_mes_actual)
        fecha_inicio = datetime.date(hoy.year, hoy.month, dia_ini)
        
        mes_sig = hoy.month + 1
        anio_sig = hoy.year
        if mes_sig > 12:
            mes_sig = 1
            anio_sig += 1
            
        ultimo_dia_mes_sig = calendar.monthrange(anio_sig, mes_sig)[1]
        dia_fin = min(dia_corte, ultimo_dia_mes_sig)
        fecha_fin = datetime.date(anio_sig, mes_sig, dia_fin)
        return fecha_inicio, fecha_fin

    anio_corte = hoy.year
    mes_corte = hoy.month
        
    ultimo_dia_mes_corte = calendar.monthrange(anio_corte, mes_corte)[1]
    dia_fin = min(dia_corte, ultimo_dia_mes_corte)
    fecha_fin = datetime.date(anio_corte, mes_corte, dia_fin)
    
    mes_inicio = mes_corte - 1
    anio_inicio = anio_corte
    if mes_inicio < 1:
        mes_inicio = 12
        anio_inicio -= 1
        
    ultimo_dia_mes_inicio = calendar.monthrange(anio_inicio, mes_inicio)[1]
    dia_inicio = min(dia_corte + 1, ultimo_dia_mes_inicio)
    fecha_inicio = datetime.date(anio_inicio, mes_inicio, dia_inicio)
    return fecha_inicio, fecha_fin

def obtener_rango_corte_pasado(u, hoy):
    dia_corte = u.dia_corte
    if not dia_corte:
        return datetime.date(hoy.year, hoy.month, 1), datetime.date(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1])

    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    fecha_fin = datetime.date(hoy.year, hoy.month, min(dia_corte, ultimo_dia_mes))
    
    mes_ini = hoy.month - 1
    anio_ini = hoy.year
    if mes_ini < 1:
        mes_ini = 12
        anio_ini -= 1
    ultimo_dia_mes_ini = calendar.monthrange(anio_ini, mes_ini)[1]
    fecha_ini = datetime.date(anio_ini, mes_ini, min(dia_corte + 1, ultimo_dia_mes_ini))
    return fecha_ini, fecha_fin


@radar_bp.route('/')
def sitrep():
    user = UserProfile.query.first()
    if not user:
        return "ERROR CRÍTICO: Perfil no inicializado."
    
    hoy = datetime.date.today()
    sueldo_neto_quincenal = calcular_neto_real(
        user.sueldo_bruto_quincenal, 
        user.isr_cfdi, 
        user.imss_cfdi, 
        user.aportacion_ahorro, 
        user.otras_deducciones
    )
    
    # Reseteo automático mensual de presupuestos variables
    presupuestos_totales = VariableBudget.query.all()
    for b in presupuestos_totales:
        if b.ultimo_mes_reseteo != hoy.month:
            b.monto_gastado = 0.0
            b.ultimo_mes_reseteo = hoy.month
    db.session.commit()

    # 1. CASCADA DE EFECTIVO (ENFOCADA 100% EN ESTE MES)
    ingreso_mensual = sueldo_neto_quincenal * 2
    
    tandas_db = Tanda.query.all()
    impacto_tandas = sum([t.monto_quincenal * 2 for t in tandas_db if not calcular_estado_tanda(t.fecha_inicio, t.total_quincenas)['completada']])
    gastos = LogisticsLoad.query.all()
    impacto_ahorros = sum([(g.monto*2 if g.frecuencia=='QUINCENAL' else g.monto) for g in gastos if g.tipo == 'SAVINGS'])

    impacto_externos = sum([(g.monto*2 if g.frecuencia=='QUINCENAL' else g.monto) for g in gastos if g.tipo == 'EXTERNAL'])
    
    # MSI y SUSCRIPCIONES (ACTIVOS PARA ESTE MES)
    compras_msi = MSIPurchase.query.filter(MSIPurchase.meses_pagados < MSIPurchase.meses_totales).all()
    impacto_msi = sum([msi.mensualidad for msi in compras_msi])
    impacto_subs = sum([(g.monto * 2 if g.frecuencia == 'QUINCENAL' else (g.monto * 4 if g.frecuencia == 'SEMANAL' else g.monto)) for g in gastos if g.tipo == 'SUBSCRIPTION'])

    msi_subs_activos = impacto_msi + impacto_subs

    # BALANCE OPERATIVO: Tu ingreso menos todo lo fijo/obligatorio de este mes.
    # ¡Ya NO restamos la deuda de tarjetas del mes pasado aquí!
    flujo_operativo = ingreso_mensual - impacto_ahorros - impacto_externos - impacto_tandas - msi_subs_activos

    # PRESUPUESTOS Y HORMIGA
    tarjetas = HangarUnit.query.all()
    presupuestos = VariableBudget.query.all()
    limite_presupuestos = sum([b.limite_maximo for b in presupuestos])
    presupuesto_gastado = sum([b.monto_gastado for b in presupuestos])
    presupuesto_no_consumido = sum([(b.limite_maximo - b.monto_gastado) for b in presupuestos if b.monto_gastado < b.limite_maximo])

    gastos_variables_fuera_presupuesto = 0.0
    tx_historicas = CardTransaction.query.all()
    for tx in tx_historicas:
        if tx.categoria != 'PRESUPUESTO VARIABLE':
            u_obj = next((t for t in tarjetas if t.id == tx.hangar_unit_id), None)
            if u_obj and u_obj.ultimo_mes_conciliado != hoy.month:
                f_ini, f_fin = obtener_rango_corte_actual(u_obj, hoy)
                if f_ini <= tx.fecha <= f_fin:
                    gastos_variables_fuera_presupuesto += tx.monto

    # CÁLCULO FINAL LÍQUIDO DEL MES
    efectivo_libre_mes = flujo_operativo - presupuesto_gastado - gastos_variables_fuera_presupuesto
    margen_error_mensual = flujo_operativo - limite_presupuestos - gastos_variables_fuera_presupuesto

    # 2. ESTADOS DE CUENTA Y TARJETAS
    resumen_tarjetas = {}
    for u in tarjetas:
        requiere_recon = False
        if u.tipo in ['CREDITO', 'DEPARTAMENTAL'] and u.dia_corte:
            if hoy.day >= u.dia_corte and u.ultimo_mes_conciliado != hoy.month:
                requiere_recon = True

        fecha_ini_ciclo, fecha_fin_ciclo = obtener_rango_corte_actual(u, hoy)
        f_ini_pasado, f_fin_pasado = obtener_rango_corte_pasado(u, hoy)

        resumen_tarjetas[u.id] = {
            'id': u.id, 
            'nombre': f"{u.institucion} {u.nombre}", 
            'institucion': u.institucion,
            'dia_corte': u.dia_corte, 
            'limite': u.limite_saldo, 
            'deuda_corte': u.deuda_corte if u.deuda_corte else 0.0, 
            'requiere_recon': requiere_recon, 
            'total_mensual': 0.0, 
            'cargos': [], 
            'cargos_sellados': [],
            'deuda_a_conciliar': 0.0, 
            'cargos_a_conciliar': [],
            'fecha_ini_ciclo': fecha_ini_ciclo, 
            'fecha_fin_ciclo': fecha_fin_ciclo,
            'f_ini_pasado': f_ini_pasado, 
            'f_fin_pasado': f_fin_pasado,
            'periodo_str': f"{fecha_ini_ciclo.strftime('%d/%m')} AL {fecha_fin_ciclo.strftime('%d/%m')}",
            'periodo_sellado_str': f"{f_ini_pasado.strftime('%d/%m')} AL {f_fin_pasado.strftime('%d/%m')}"
        }

    # Suscripciones a mostrar en Tarjetas
    for g in [g for g in gastos if g.hangar_unit_id in resumen_tarjetas]:
        card_info = resumen_tarjetas[g.hangar_unit_id]
        u_obj = next((t for t in tarjetas if t.id == g.hangar_unit_id), None)
        
        monto_sub = g.monto * 2 if g.frecuencia == 'QUINCENAL' else (g.monto * 4 if g.frecuencia == 'SEMANAL' else g.monto)
        dia_subs = g.dia_cobro or 1
        f_ini = card_info['fecha_ini_ciclo']
        f_sub = datetime.date(f_ini.year, f_ini.month, min(dia_subs, calendar.monthrange(f_ini.year, f_ini.month)[1]))

        cargo_obj = {'db_id': g.id, 'clase': 'sub', 'tipo': 'SUB', 'concepto': g.concepto, 'monto': monto_sub, 'pagado': False, 'dia': f"{dia_subs:02d}", 'is_budget': False, 'fecha_raw': f_sub}
        
        if not (u_obj and u_obj.ultimo_mes_conciliado == hoy.month):
            card_info['total_mensual'] += monto_sub
            card_info['cargos'].append(cargo_obj)
            card_info['deuda_a_conciliar'] += monto_sub
            card_info['cargos_a_conciliar'].append(cargo_obj)

    # MSI a mostrar en Tarjetas
    for msi in [m for m in compras_msi if m.hangar_unit_id in resumen_tarjetas]:
        card_info = resumen_tarjetas[msi.hangar_unit_id]
        u_obj = next((t for t in tarjetas if t.id == msi.hangar_unit_id), None)
        
        cargo_obj = {'db_id': msi.id, 'clase': 'msi', 'tipo': 'MSI', 'concepto': msi.concepto, 'monto': msi.mensualidad, 'pagado': False, 'dia': '--', 'is_budget': False, 'fecha_raw': datetime.date.max}
        
        if not (u_obj and u_obj.ultimo_mes_conciliado == hoy.month):
            card_info['total_mensual'] += msi.mensualidad
            card_info['cargos'].append(cargo_obj)
            card_info['deuda_a_conciliar'] += msi.mensualidad
            card_info['cargos_a_conciliar'].append(cargo_obj)

    # Transacciones
    for tx in tx_historicas:
        if tx.hangar_unit_id in resumen_tarjetas:
            card_info = resumen_tarjetas[tx.hangar_unit_id]
            f_ini = card_info['fecha_ini_ciclo']
            f_fin = card_info['fecha_fin_ciclo']
            p_ini = card_info['f_ini_pasado']
            p_fin = card_info['f_fin_pasado']
            
            nota_limpia = tx.nota.split("]")[-1].strip() if "]" in tx.nota else tx.nota
            cargo_obj = {'db_id': tx.id, 'clase': 'tx', 'tipo': 'TX', 'concepto': nota_limpia, 'monto': tx.monto, 'pagado': False, 'dia': f"{tx.fecha.day:02d}", 'is_budget': (tx.categoria == 'PRESUPUESTO VARIABLE'), 'fecha_raw': tx.fecha}

            if f_ini <= tx.fecha <= f_fin:
                card_info['total_mensual'] += tx.monto
                card_info['cargos'].append(cargo_obj)
                card_info['deuda_a_conciliar'] += tx.monto
                card_info['cargos_a_conciliar'].append(cargo_obj)
                
            if p_ini <= tx.fecha <= p_fin:
                card_info['cargos_sellados'].append(cargo_obj)

    def ordenar_por_fecha_real(c):
        return c.get('fecha_raw') or datetime.date.min

    for t_id in resumen_tarjetas:
        resumen_tarjetas[t_id]['cargos'] = sorted(resumen_tarjetas[t_id]['cargos'], key=ordenar_por_fecha_real, reverse=True)
        resumen_tarjetas[t_id]['cargos_sellados'] = sorted(resumen_tarjetas[t_id]['cargos_sellados'], key=ordenar_por_fecha_real, reverse=True)
        resumen_tarjetas[t_id]['cargos_a_conciliar'] = sorted(resumen_tarjetas[t_id]['cargos_a_conciliar'], key=ordenar_por_fecha_real, reverse=True)

    tarjetas_activas = {k: v for k, v in resumen_tarjetas.items() if v['total_mensual'] > 0 or len(v['cargos']) > 0 or len(v['cargos_sellados']) > 0 or v['deuda_corte'] > 0 or v['requiere_recon']}

    porcentaje_msi = (impacto_msi / ingreso_mensual) * 100 if ingreso_mensual > 0 else 0
    limite_hormiga = 1500.00 
    
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    dias_restantes_mes = (ultimo_dia - hoy.day) if (ultimo_dia - hoy.day) > 0 else 1

    # 3. METAS ANUALES Y BANCOS
    saldo_bancos_ahorro = sum([u.limite_saldo for u in tarjetas if u.tipo in ['AHORRO', 'DEBITO']])
    datos_ahorro = calcular_ahorro_acumulado(user.fecha_inicio, user.aportacion_ahorro)
    fondo_empresa = datos_ahorro['acumulado']
    ahorro_total_real = fondo_empresa + saldo_bancos_ahorro
    
    meta_anual = (user.meta_ahorro_mensual * 12) if user.meta_ahorro_mensual > 0 else 1
    progreso_anual = (ahorro_total_real / meta_anual) * 100

    return render_template('radar.html', 
                           ingreso_mensual=ingreso_mensual, ahorros=impacto_ahorros,
                           externos=impacto_externos, tandas=impacto_tandas, 
                           msi_subs_activos=msi_subs_activos, suscripciones=impacto_subs, pago_msi=impacto_msi,
                           flujo_operativo=flujo_operativo,
                           presupuestos_limite=limite_presupuestos, presupuesto_gastado=presupuesto_gastado, 
                           margen_error=margen_error_mensual, gastos_extra=gastos_variables_fuera_presupuesto, 
                           efectivo_libre=efectivo_libre_mes,
                           fechas=obtener_info_quincena_actual(), meta_gasto=user.meta_gasto_diario,
                           deuda_tarjetas=tarjetas_activas, presupuestos=presupuestos, 
                           unidades=tarjetas, categorias=CATEGORIAS_GASTO, hoy_str=hoy.strftime('%Y-%m-%d'),
                           porcentaje_msi=porcentaje_msi, limite_hormiga=limite_hormiga,
                           fondo_empresa=fondo_empresa, saldo_bancos_ahorro=saldo_bancos_ahorro,
                           ahorro_total_real=ahorro_total_real, meta_anual=meta_anual, progreso_anual=progreso_anual)

@radar_bp.route('/conciliacion', methods=['GET', 'POST'])
def conciliacion():
    hoy = datetime.date.today()
    user = UserProfile.query.first()
    unidades = HangarUnit.query.all()
    presupuestos = VariableBudget.query.all()
    gastos_ahorro = LogisticsLoad.query.filter_by(tipo='SAVINGS').all()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'seal_card':
            unidad_id = int(request.form.get('hangar_unit_id'))
            deuda_str = request.form.get('deuda_real', '0')
            abono_str = request.form.get('abono_realizado', '0')
            deuda_real = float(deuda_str) if deuda_str and deuda_str.strip() else 0.0
            abono_realizado = float(abono_str) if abono_str and abono_str.strip() else 0.0
            
            u = HangarUnit.query.get_or_404(unidad_id)
            p_ini, p_fin = obtener_rango_corte_pasado(u, hoy)
            
            subs = LogisticsLoad.query.filter_by(hangar_unit_id=u.id, tipo='SUBSCRIPTION').all()
            for s in subs:
                m_sub = s.monto * 2 if s.frecuencia == 'QUINCENAL' else (s.monto * 4 if s.frecuencia == 'SEMANAL' else s.monto)
                tx_sub = CardTransaction(hangar_unit_id=u.id, monto=m_sub, nota=f"[SUB] {s.concepto}", categoria='SUSCRIPCION', fecha=p_fin)
                db.session.add(tx_sub)
                
            compras_msi = MSIPurchase.query.filter_by(hangar_unit_id=u.id).all()
            for msi in compras_msi:
                if msi.meses_pagados < msi.meses_totales:
                    tx_msi = CardTransaction(hangar_unit_id=u.id, monto=msi.mensualidad, nota=f"[MSI] {msi.concepto} ({msi.meses_pagados+1}/{msi.meses_totales})", categoria='COMPRA A MESES', fecha=p_fin)
                    db.session.add(tx_msi)
                    msi.meses_pagados += 1
            
            u.deuda_corte = deuda_real - abono_realizado
            u.ultimo_mes_conciliado = hoy.month
            
            db.session.commit()
            return redirect(url_for('radar.conciliacion'))

        elif action == 'seal_budget':
            budget_id = int(request.form.get('budget_id'))
            b = VariableBudget.query.get_or_404(budget_id)
            b.monto_gastado = 0.0
            b.ultimo_mes_reseteo = hoy.month
            db.session.commit()
            return redirect(url_for('radar.conciliacion'))

        elif action == 'transfer_savings':
            target_unit_id = int(request.form.get('hangar_unit_id'))
            monto = float(request.form.get('monto', 0))
            u = HangarUnit.query.get_or_404(target_unit_id)
            u.limite_saldo += monto
            db.session.commit()
            return redirect(url_for('radar.conciliacion'))

        elif action == 'seal_month_global':
            for b in presupuestos:
                b.monto_gastado = 0.0
                b.ultimo_mes_reseteo = hoy.month
            db.session.commit()
            return redirect(url_for('radar.sitrep'))

    tarjetas_recon = {}
    for u in unidades:
        f_ini, f_fin = obtener_rango_corte_actual(u, hoy)
        p_ini, p_fin = obtener_rango_corte_pasado(u, hoy)
        
        cargos_view = []
        
        if u.ultimo_mes_conciliado == hoy.month:
            txs = CardTransaction.query.filter(
                CardTransaction.hangar_unit_id == u.id,
                CardTransaction.fecha >= p_ini,
                CardTransaction.fecha <= p_fin
            ).order_by(CardTransaction.fecha.desc()).all()
            
            periodo_str = f"{p_ini.strftime('%d/%m')} AL {p_fin.strftime('%d/%m')} [SELLADO]"
            deuda_sellada = u.deuda_corte
            
            for t in txs:
                tipo = 'MSI' if t.categoria == 'COMPRA A MESES' else ('SUB' if t.categoria == 'SUSCRIPCION' else 'TX')
                cargos_view.append({'db_id': t.id, 'fecha_raw': t.fecha, 'fecha': t.fecha.strftime('%d/%m'), 'nota': t.nota, 'monto': t.monto, 'tipo': tipo, 'editable': True})
                
            suma_calculada = sum(c['monto'] for c in cargos_view)
            total_input = deuda_sellada
            
        else:
            txs = CardTransaction.query.filter(
                CardTransaction.hangar_unit_id == u.id,
                CardTransaction.fecha >= f_ini,
                CardTransaction.fecha <= f_fin
            ).all()
            
            periodo_str = f"{f_ini.strftime('%d/%m')} AL {f_fin.strftime('%d/%m')}"
            
            for t in txs:
                cargos_view.append({'db_id': t.id, 'fecha_raw': t.fecha, 'fecha': t.fecha.strftime('%d/%m'), 'nota': t.nota, 'monto': t.monto, 'tipo': 'TX', 'editable': True})
                
            subs = LogisticsLoad.query.filter_by(hangar_unit_id=u.id, tipo='SUBSCRIPTION').all()
            for s in subs:
                m_sub = s.monto * 2 if s.frecuencia == 'QUINCENAL' else (s.monto * 4 if s.frecuencia == 'SEMANAL' else s.monto)
                cargos_view.append({'db_id': s.id, 'fecha_raw': f_fin, 'fecha': '--/--', 'nota': f"[SUB] {s.concepto}", 'monto': m_sub, 'tipo': 'SUB', 'editable': False})
                
            msis = MSIPurchase.query.filter(MSIPurchase.hangar_unit_id == u.id, MSIPurchase.meses_pagados < MSIPurchase.meses_totales).all()
            for m in msis:
                cargos_view.append({'db_id': m.id, 'fecha_raw': f_fin, 'fecha': '--/--', 'nota': f"[MSI] {m.concepto} ({m.meses_pagados+1}/{m.meses_totales})", 'monto': m.mensualidad, 'tipo': 'MSI', 'editable': False})
            
            cargos_view = sorted(cargos_view, key=lambda x: x['fecha_raw'], reverse=True)
            suma_calculada = sum(c['monto'] for c in cargos_view)
            deuda_sellada = 0.0
            total_input = suma_calculada

        tarjetas_recon[u.id] = {
            'unidad': u,
            'periodo_str': periodo_str,
            'txs': cargos_view,
            'total_input': round(total_input, 2),
            'suma_calculada': round(suma_calculada, 2),
            'deuda_sellada': round(deuda_sellada, 2),
            'conciliada': (u.ultimo_mes_conciliado == hoy.month)
        }

    # === ESTRATEGIA DE PAGO DEL MES ESTRICTA ===
    sueldo_neto_quincenal = calcular_neto_real(user.sueldo_bruto_quincenal, user.isr_cfdi, user.imss_cfdi, user.aportacion_ahorro, user.otras_deducciones)
    ingreso_mensual = sueldo_neto_quincenal * 2
    
    # YA NO SE SUMAN LOS AHORROS AL FLUJO, la fórmula es ESTRICTA para mostrar la realidad de la quincena vs obligaciones.
    
    tandas_db = Tanda.query.all()
    impacto_tandas = sum([t.monto_quincenal * 2 for t in tandas_db if not calcular_estado_tanda(t.fecha_inicio, t.total_quincenas)['completada']])
    gastos_fijos = LogisticsLoad.query.filter_by(tipo='EXTERNAL').all()
    impacto_fijos = sum([(g.monto * 2 if g.frecuencia == 'QUINCENAL' else (g.monto * 4 if g.frecuencia == 'SEMANAL' else g.monto)) for g in gastos_fijos])
    
    tarjetas_selladas = [u for u in unidades if u.tipo in ['CREDITO', 'DEPARTAMENTAL'] and u.ultimo_mes_conciliado == hoy.month]
    total_tarjetas = sum([u.deuda_corte for u in tarjetas_selladas])
    
    total_comprometido = impacto_tandas + impacto_fijos + total_tarjetas
    
    # Flujo Estricto: Ingreso Nuevo - Obligaciones
    flujo_mes = ingreso_mensual - total_comprometido
    
    meses_es = ['', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    
    estrategia = {
        'nombre_mes': meses_es[hoy.month],
        'ingreso': ingreso_mensual,
        'tandas': impacto_tandas,
        'fijos_list': gastos_fijos,
        'fijos_total': impacto_fijos,
        'tarjetas': tarjetas_selladas,
        'tarjetas_total': total_tarjetas,
        'total_comprometido': total_comprometido,
        'flujo': flujo_mes
    }

    return render_template('conciliacion.html', 
                           unidades=unidades, 
                           presupuestos=presupuestos,
                           gastos_ahorro=gastos_ahorro,
                           tarjetas_recon=tarjetas_recon,
                           estrategia=estrategia,
                           hoy=hoy)

# RUTAS INTACTAS DE CRUD
@radar_bp.route('/budget/add', methods=['POST'])
def add_budget():
    hangar_id = request.form.get('hangar_unit_id')
    nuevo_presupuesto = VariableBudget(nombre=request.form.get('nombre', '').upper(), limite_maximo=float(request.form.get('limite', 0)), hangar_unit_id=int(hangar_id) if hangar_id else None)
    db.session.add(nuevo_presupuesto)
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/budget/edit/<int:id>', methods=['POST'])
def edit_budget(id):
    budget = VariableBudget.query.get_or_404(id)
    budget.nombre = request.form.get('nombre', '').upper()
    budget.limite_maximo = float(request.form.get('limite', 0))
    hangar_id = request.form.get('hangar_unit_id')
    budget.hangar_unit_id = int(hangar_id) if hangar_id else None
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/budget/spend', methods=['POST'])
def spend_budget():
    budget_id = int(request.form.get('budget_id'))
    monto = float(request.form.get('monto', 0))
    fecha_str = request.form.get('fecha')
    nota = request.form.get('nota', '').upper()
    hangar_id = request.form.get('hangar_unit_id')
    
    fecha_gasto = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
    budget = VariableBudget.query.get(budget_id)
    
    tx = BudgetTransaction(budget_id=budget_id, monto=monto, nota=nota, fecha=fecha_gasto)
    db.session.add(tx)
    budget.monto_gastado += monto

    if hangar_id:
        card_tx = CardTransaction(
            hangar_unit_id=int(hangar_id),
            monto=monto,
            nota=f"[{budget.nombre}] {nota}",
            categoria='PRESUPUESTO VARIABLE',
            fecha=fecha_gasto
        )
        db.session.add(card_tx)
        
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/card/spend', methods=['POST'])
def spend_card():
    monto = float(request.form.get('monto', 0))
    nota = request.form.get('nota', '').upper()
    categoria = request.form.get('categoria', 'OTROS')
    
    if monto < 0:
        categoria = "ABONO/CASHBACK"
        
    tx = CardTransaction(
        hangar_unit_id=int(request.form.get('hangar_unit_id')),
        monto=monto,
        nota=nota,
        categoria=categoria,
        fecha=datetime.datetime.strptime(request.form.get('fecha'), '%Y-%m-%d').date()
    )
    db.session.add(tx)
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/card/deposit', methods=['POST'])
def deposit_card():
    unidad_id = int(request.form.get('hangar_unit_id'))
    monto = float(request.form.get('monto', 0))
    unidad = HangarUnit.query.get_or_404(unidad_id)
    unidad.limite_saldo += monto
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/update_goal', methods=['POST'])
def update_goal():
    user = UserProfile.query.first()
    nuevo_ahorro = float(request.form.get('meta_ahorro', 0))
    user.meta_ahorro_mensual = nuevo_ahorro
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/card/recon', methods=['POST'])
def recon_card():
    unidad_id = int(request.form.get('hangar_unit_id'))
    
    deuda_real_str = request.form.get('deuda_real', '')
    deuda_real_banco = float(deuda_real_str) if deuda_real_str and deuda_real_str.strip() else 0.0
    
    abono_str = request.form.get('abono_realizado', '')
    abono_realizado = float(abono_str) if abono_str and abono_str.strip() else 0.0
    
    hoy = datetime.date.today()
    u = HangarUnit.query.get_or_404(unidad_id)
    p_ini, p_fin = obtener_rango_corte_pasado(u, hoy)

    subs = LogisticsLoad.query.filter_by(hangar_unit_id=u.id, tipo='SUBSCRIPTION').all()
    for s in subs:
        m_sub = s.monto * 2 if s.frecuencia == 'QUINCENAL' else (s.monto * 4 if s.frecuencia == 'SEMANAL' else s.monto)
        tx_sub = CardTransaction(hangar_unit_id=u.id, monto=m_sub, nota=f"[SUB] {s.concepto}", categoria='SUSCRIPCION', fecha=p_fin)
        db.session.add(tx_sub)
        
    compras_msi = MSIPurchase.query.filter_by(hangar_unit_id=u.id).all()
    for msi in compras_msi:
        if msi.meses_pagados < msi.meses_totales:
            tx_msi = CardTransaction(hangar_unit_id=u.id, monto=msi.mensualidad, nota=f"[MSI] {msi.concepto} ({msi.meses_pagados+1}/{msi.meses_totales})", categoria='COMPRA A MESES', fecha=p_fin)
            db.session.add(tx_msi)
            msi.meses_pagados += 1
    
    u.deuda_corte = deuda_real_banco - abono_realizado
    u.ultimo_mes_conciliado = hoy.month
    
    db.session.commit()
    return redirect(url_for('radar.sitrep'))

@radar_bp.route('/card/delete_tx/<int:id>', methods=['POST'])
def delete_card_tx(id):
    tx = CardTransaction.query.get_or_404(id)
    db.session.delete(tx)
    db.session.commit()
    return redirect(request.referrer or url_for('radar.sitrep'))

@radar_bp.route('/card/edit_tx/<int:id>', methods=['POST'])
def edit_card_tx(id):
    tx = CardTransaction.query.get_or_404(id)
    tx.monto = float(request.form.get('monto', tx.monto))
    tx.nota = request.form.get('nota', tx.nota).upper()
    db.session.commit()
    return redirect(request.referrer or url_for('radar.sitrep'))

@radar_bp.route('/card/assign_budget', methods=['POST'])
def assign_tx_to_budget():
    tx_id = int(request.form.get('tx_id'))
    budget_id = int(request.form.get('budget_id'))
    
    tx = CardTransaction.query.get_or_404(tx_id)
    budget = VariableBudget.query.get_or_404(budget_id)
    
    tx.categoria = 'PRESUPUESTO VARIABLE'
    nota_limpia = tx.nota.split("]")[-1].strip() if "]" in tx.nota else tx.nota
    tx.nota = f"[{budget.nombre}] {nota_limpia}"
        
    existing_bt = BudgetTransaction.query.filter_by(
        budget_id=budget.id,
        monto=tx.monto,
        fecha=tx.fecha
    ).first()

    if not existing_bt:
        budget_tx = BudgetTransaction(
            budget_id=budget.id,
            monto=tx.monto,
            nota=nota_limpia,
            fecha=tx.fecha
        )
        db.session.add(budget_tx)
        budget.monto_gastado += tx.monto
    
    db.session.commit()
    return redirect(url_for('radar.sitrep'))