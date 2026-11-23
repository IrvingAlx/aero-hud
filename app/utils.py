import datetime
import calendar

# Tu TaxCalculator traducido a Python
def calcular_isr_2026_quincenal(sueldo_bruto):
    if sueldo_bruto <= 0:
        return {"cuota": 0.0, "porcentaje": 0.0, "isr_total": 0.0}

    # Tu tabla exacta de Kotlin
    tablas_isr = [
        (0.01, 416.70, 0.00, 0.0192),
        (416.71, 3537.15, 7.95, 0.0640),
        (3537.16, 6216.15, 207.75, 0.1088),
        (6216.16, 7225.95, 499.20, 0.1600),
        (7225.96, 8651.40, 660.75, 0.1792),
        (8651.41, 17448.75, 916.20, 0.2136),
        (17448.76, 27501.60, 2795.25, 0.2352),
        (27501.61, 52505.25, 5159.60, 0.3000),
        (52505.26, 70007.10, 12660.75, 0.3200),
        (70007.11, 200020.20, 18261.30, 0.3400),
        (200020.21, float('inf'), 62465.70, 0.3500)
    ]

    for inf, sup, cuota, porcentaje in tablas_isr:
        if inf <= sueldo_bruto <= sup:
            excedente = sueldo_bruto - inf
            impuesto_marginal = excedente * porcentaje
            return {
                "cuota": cuota,
                "porcentaje": porcentaje * 100, # Para mostrar ej: 21.36%
                "isr_total": round(cuota + impuesto_marginal, 2)
            }
    return {"cuota": 0.0, "porcentaje": 0.0, "isr_total": 0.0}

def calcular_neto_real(bruto, isr_cfdi, imss, ahorro, otros):
    return round(bruto - isr_cfdi - imss - ahorro - otros, 2)

def calcular_aguinaldo(bruto):
    salario_diario = bruto / 15
    return round(salario_diario * 15, 2)

def calcular_prima_vacacional(bruto, dias_vacaciones):
    salario_diario = bruto / 15
    return round((salario_diario * dias_vacaciones) * 0.25, 2)

def calcular_ahorro_acumulado(fecha_inicio, aportacion):
    if not fecha_inicio:
        return {"acumulado": 0.0, "porcentaje": 0}

    hoy = datetime.date.today()

    # Lógica de ciclo de Julio: El ciclo empieza el 16 de Julio y termina el 15 de Julio del otro año
    # Determinamos cuándo empezó el ciclo ACTUAL.
    if hoy.month > 7 or (hoy.month == 7 and hoy.day >= 16):
        inicio_ciclo = datetime.date(hoy.year, 7, 16)
    else:
        inicio_ciclo = datetime.date(hoy.year - 1, 7, 16)

    # Si entraste a la empresa DESPUÉS de que empezó el ciclo actual, 
    # tu ahorro cuenta desde tu fecha de ingreso.
    fecha_calculo = max(inicio_ciclo, fecha_inicio)

    # Calculamos quincenas transcurridas
    dias = (hoy - fecha_calculo).days
    quincenas_transcurridas = max(0, int(dias / 15))

    # El ciclo completo es de 24 quincenas (1 año)
    quincenas_totales_ciclo = 24
    
    porcentaje = (quincenas_transcurridas / quincenas_totales_ciclo) * 100
    
    # Limitamos al 100% (por si hay desfases de días)
    porcentaje_real = min(porcentaje, 100.0)
    acumulado = quincenas_transcurridas * (aportacion * 2)

    return {
        "acumulado": float(round(acumulado, 2)), 
        "porcentaje": float(round(porcentaje_real, 2))
    }
    
def calcular_liquidez(neto, gastos_quincenales):
    return round(neto - gastos_quincenales, 2)
    
def obtener_info_quincena_actual():
    hoy = datetime.date.today()
    
    # Función interna para calcular el día exacto de pago (1 día antes, solo días hábiles)
    def calcular_dia_pago_real(year, month, es_primera_quincena):
        if es_primera_quincena:
            dia_objetivo = 14 # Un día antes del 15
        else:
            ultimo_dia_mes = calendar.monthrange(year, month)[1]
            dia_objetivo = ultimo_dia_mes - 1 # Un día antes de fin de mes
            
        fecha_objetivo = datetime.date(year, month, dia_objetivo)
        
        # Ajuste por fines de semana (weekday: 0=Lunes, 5=Sábado, 6=Domingo)
        if fecha_objetivo.weekday() == 5: # Es Sábado, se paga el Viernes
            fecha_objetivo -= datetime.timedelta(days=1)
        elif fecha_objetivo.weekday() == 6: # Es Domingo, se paga el Viernes
            fecha_objetivo -= datetime.timedelta(days=2)
            
        return fecha_objetivo

    # Calculamos los dos posibles pagos de este mes
    pago_q1 = calcular_dia_pago_real(hoy.year, hoy.month, True)
    pago_q2 = calcular_dia_pago_real(hoy.year, hoy.month, False)

    # Determinamos cuál es el próximo depósito
    if hoy <= pago_q1:
        proximo_pago = pago_q1
        num_quincena = 1
    elif hoy <= pago_q2:
        proximo_pago = pago_q2
        num_quincena = 2
    else:
        # Ya pasaron los dos pagos de este mes, el próximo es el Q1 del siguiente mes
        mes_sig = hoy.month + 1
        anio_sig = hoy.year
        if mes_sig > 12:
            mes_sig = 1
            anio_sig += 1
        proximo_pago = calcular_dia_pago_real(anio_sig, mes_sig, True)
        num_quincena = 1

    dias_restantes = (proximo_pago - hoy).days

    return {
        "quincena_numero": num_quincena,
        "dias_restantes_pago": dias_restantes,
        "fecha_exacta": proximo_pago.strftime('%d/%m/%Y')
    }
    
def calcular_estado_tanda(fecha_inicio, total_quincenas):
    hoy = datetime.date.today()
    
    # Si la tanda no ha empezado
    if hoy < fecha_inicio:
        return {
            "pagadas": 0, 
            "siguiente_fecha": fecha_inicio.strftime('%d/%m/%Y'),
            "dias_restantes": (fecha_inicio - hoy).days,
            "completada": False
        }
        
    pagos = 0
    fecha_iteracion = fecha_inicio

    # Simulamos el avance del tiempo quincena por quincena
    while fecha_iteracion <= hoy and pagos < total_quincenas:
        pagos += 1
        
        # Calcular cuál es la SIGUIENTE fecha de pago
        if fecha_iteracion.day <= 15:
            # Si estábamos en el 15, la siguiente es fin de mes
            ultimo_dia = calendar.monthrange(fecha_iteracion.year, fecha_iteracion.month)[1]
            fecha_iteracion = datetime.date(fecha_iteracion.year, fecha_iteracion.month, ultimo_dia)
        else:
            # Si estábamos a fin de mes, la siguiente es el 15 del próximo mes
            mes_sig = fecha_iteracion.month + 1
            anio_sig = fecha_iteracion.year
            if mes_sig > 12:
                mes_sig = 1
                anio_sig += 1
            fecha_iteracion = datetime.date(anio_sig, mes_sig, 15)

    completada = pagos >= total_quincenas
    
    return {
        "pagadas": pagos,
        "siguiente_fecha": fecha_iteracion.strftime('%d/%m/%Y') if not completada else "FINALIZADA",
        "dias_restantes": (fecha_iteracion - hoy).days if not completada else 0,
        "completada": completada
    }