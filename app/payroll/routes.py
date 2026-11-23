from flask import Blueprint, render_template, request, redirect, url_for
from app.models import db, UserProfile
from app.utils import (calcular_isr_2026_quincenal, calcular_neto_real, 
                       calcular_aguinaldo, calcular_prima_vacacional, 
                       calcular_ahorro_acumulado)
from datetime import datetime

payroll_bp = Blueprint('payroll', __name__)

@payroll_bp.route('/', methods=['GET', 'POST'])
def index():
    user = UserProfile.query.first()
    show_modal = False # Bandera para mantener el modal abierto si hacemos el cálculo inverso
    
    # === DATOS BASE PARA LA SIMULACIÓN ===
    datos_ahorro = calcular_ahorro_acumulado(user.fecha_inicio, user.aportacion_ahorro)
    ahorro_acumulado = datos_ahorro['acumulado']
    salario_diario = user.sueldo_bruto_quincenal / 15
    isr_normal = calcular_isr_2026_quincenal(user.sueldo_bruto_quincenal)['isr_total']
    
    # Valores por defecto (Caso Ideal 30 días)
    bono_bruto = salario_diario * 30
    modo_inverso = False
    deposito_target = 0

    if request.method == 'POST':
        action = request.form.get('action')
        
        # SI ESTAMOS ACTUALIZANDO PARÁMETROS NORMALES
        if action == 'update_params':
            user.sueldo_bruto_quincenal = float(request.form.get('grossSalary', 0))
            user.imss_cfdi = float(request.form.get('imssCfdi', 0))
            user.isr_cfdi = float(request.form.get('isrCfdi', 0))
            user.aportacion_ahorro = float(request.form.get('savingsContribution', 0))
            user.otras_deducciones = float(request.form.get('otherDeductions', 0))
            user.dias_vacaciones = int(request.form.get('vacationDays', 12))
            user.meta_gasto_diario = float(request.form.get('dailyGoal', 0))
            user.meta_ahorro_mensual = float(request.form.get('monthlyGoal', 0))
            
            fecha_str = request.form.get('startDate')
            if fecha_str:
                user.fecha_inicio = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            db.session.commit()
            return redirect(url_for('payroll.index'))
            
        # SI ESTAMOS USANDO LA CALCULADORA INVERSA (Descifrar recibo)
        elif action == 'reverse_calc':
            deposito_target = float(request.form.get('deposito_real', 0))
            modo_inverso = True
            show_modal = True
            
            # --- ALGORITMO DE BÚSQUEDA BINARIA (Descifrador SAT) ---
            # Intenta adivinar el bono bruto hasta que el neto coincida con lo que cayó en el banco
            limite_inferior = 0.0
            limite_superior = 200000.0 # Un bono bruto irrealmente alto para empezar
            
            # Iteramos hasta encontrar el centavo exacto
            for _ in range(100):
                mitad_bono_prueba = (limite_inferior + limite_superior) / 2
                bruto_prueba = user.sueldo_bruto_quincenal + mitad_bono_prueba
                isr_prueba = calcular_isr_2026_quincenal(bruto_prueba)['isr_total']
                
                # El neto que caería en el banco con este bono de prueba:
                neto_prueba = bruto_prueba - isr_prueba - user.imss_cfdi - user.otras_deducciones + ahorro_acumulado
                
                if neto_prueba < deposito_target:
                    limite_inferior = mitad_bono_prueba # Nos quedamos cortos, el bono debe ser mayor
                else:
                    limite_superior = mitad_bono_prueba # Nos pasamos, el bono debe ser menor
            
            # Una vez que el algoritmo termina, encontramos el bono exacto
            bono_bruto = mitad_bono_prueba

    # === EJECUTAR MATEMÁTICA CON EL BONO ENCONTRADO (o el de 30 días) ===
    bruto_gravable_total = user.sueldo_bruto_quincenal + bono_bruto
    isr_simulado = calcular_isr_2026_quincenal(bruto_gravable_total)
    neto_sin_ahorro = bruto_gravable_total - isr_simulado['isr_total'] - user.imss_cfdi - user.otras_deducciones
    deposito_total_estimado = neto_sin_ahorro + ahorro_acumulado
    dias_bono_calculados = bono_bruto / salario_diario if salario_diario > 0 else 0

    simulacion = {
        'es_inverso': modo_inverso,
        'deposito_ingresado': deposito_target,
        'dias_bono': dias_bono_calculados,
        'bono_bruto': bono_bruto,
        'bruto_total': bruto_gravable_total,
        'isr_retenido': isr_simulado['isr_total'],
        'bracket': isr_simulado['porcentaje'],
        'impacto_isr': isr_simulado['isr_total'] - isr_normal, 
        'ahorro_entregado': ahorro_acumulado,
        'deposito_final': deposito_total_estimado
    }

    # === CÁLCULOS TÁCTICOS NORMALES DE LA PANTALLA ===
    isr_calculado_app = calcular_isr_2026_quincenal(user.sueldo_bruto_quincenal)
    isr_diff = isr_calculado_app['isr_total'] - user.isr_cfdi
    neto_real = calcular_neto_real(user.sueldo_bruto_quincenal, user.isr_cfdi, user.imss_cfdi, user.aportacion_ahorro, user.otras_deducciones)
    aguinaldo = calcular_aguinaldo(user.sueldo_bruto_quincenal)
    prima = calcular_prima_vacacional(user.sueldo_bruto_quincenal, user.dias_vacaciones)

    return render_template('payroll.html', 
                           user=user, neto_real=neto_real, isr_app=isr_calculado_app,
                           isr_diff=isr_diff, aguinaldo=aguinaldo, prima=prima,
                           ahorro_acumulado=ahorro_acumulado, progreso_ahorro=datos_ahorro['porcentaje'],
                           simulacion=simulacion, show_modal=show_modal)