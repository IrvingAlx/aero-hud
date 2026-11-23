"""Carga datos de demostracion inventados (nada real) para probar AERO HUD.

Uso: python seed_demo.py   (borra y recrea la base local)
"""
from datetime import date, timedelta

from app import create_app
from app.models import (db, UserProfile, HangarUnit, Tanda, LogisticsLoad, MSIPurchase,
                        VariableBudget, BudgetTransaction, CardTransaction)

app = create_app()
hoy = date.today()


def hace(dias):
    return hoy - timedelta(days=dias)


with app.app_context():
    db.drop_all()
    db.create_all()

    # 1. Nomina
    db.session.add(UserProfile(
        sueldo_bruto_quincenal=15000.00, isr_cfdi=2100.00, imss_cfdi=450.00, aportacion_ahorro=500.00,
        fecha_inicio=date(2024, 1, 16), dias_vacaciones=12, otras_deducciones=0.0,
        meta_gasto_diario=400.0, meta_ahorro_mensual=2000.0))

    # 2. Flota de cuentas y tarjetas (instituciones ficticias)
    flota = [
        HangarUnit(institucion='BANCO AZUL', nombre='CAJITA AHORRO', tipo='AHORRO', limite_saldo=1500.00, tasa_anual=6.5),
        HangarUnit(institucion='BANCO NORTE', nombre='TARJETA ORO', tipo='CREDITO', limite_saldo=60000.00, dia_corte=9, dia_pago=29),
        HangarUnit(institucion='BANCO NORTE', nombre='TARJETA VIAJES', tipo='CREDITO', limite_saldo=30000.00, dia_corte=8, dia_pago=28),
        HangarUnit(institucion='BANCO SUR', nombre='TARJETA DIARIA', tipo='CREDITO', limite_saldo=18000.00, dia_corte=3, dia_pago=26),
        HangarUnit(institucion='TIENDA CENTRO', nombre='TARJETA TIENDA', tipo='DEPARTAMENTAL', limite_saldo=25000.00, dia_pago=20),
    ]
    db.session.add_all(flota)
    db.session.commit()

    # 3. Tanda
    db.session.add(Tanda(nombre='TANDA DE LA OFICINA', monto_quincenal=1500.0, total_quincenas=12,
                         fecha_inicio=hace(60), mi_turno=4))

    # 4. Cargas recurrentes y suscripciones
    db.session.add_all([
        LogisticsLoad(concepto='SEGURO AUTO', tipo='EXTERNAL', monto=1100.0, frecuencia='MENSUAL', destinatario='ASEGURADORA'),
        LogisticsLoad(concepto='CLASES DE IDIOMA', tipo='EXTERNAL', monto=600.0, frecuencia='QUINCENAL', destinatario='ESCUELA'),
        LogisticsLoad(concepto='AHORRO', tipo='SAVINGS', monto=3000.0, frecuencia='QUINCENAL', hangar_unit_id=1),
        LogisticsLoad(concepto='STREAMING VIDEO', tipo='SUBSCRIPTION', monto=219.0, frecuencia='MENSUAL', dia_cobro=15, hangar_unit_id=3),
        LogisticsLoad(concepto='MUSICA', tipo='SUBSCRIPTION', monto=129.0, frecuencia='MENSUAL', dia_cobro=18, hangar_unit_id=4),
        LogisticsLoad(concepto='ALMACENAMIENTO NUBE', tipo='SUBSCRIPTION', monto=99.0, frecuencia='MENSUAL', dia_cobro=20, hangar_unit_id=4),
        LogisticsLoad(concepto='GIMNASIO', tipo='SUBSCRIPTION', monto=899.0, frecuencia='MENSUAL', dia_cobro=5, hangar_unit_id=4),
    ])

    # 5. Compras a meses sin intereses
    db.session.add_all([
        MSIPurchase(concepto='LAPTOP', monto_total=1200.0 * 12, mensualidad=1200.0, meses_totales=12, meses_pagados=3, hangar_unit_id=2),
        MSIPurchase(concepto='MUEBLE SALA', monto_total=900.0 * 6, mensualidad=900.0, meses_totales=6, meses_pagados=2, hangar_unit_id=3),
        MSIPurchase(concepto='TELEFONO', monto_total=450.0 * 13, mensualidad=450.0, meses_totales=13, meses_pagados=5, hangar_unit_id=5),
    ])

    # 6. Presupuestos variables
    gas = VariableBudget(nombre='GASOLINA', limite_maximo=3000.0, monto_gastado=1250.0, hangar_unit_id=2)
    salidas = VariableBudget(nombre='SALIDAS', limite_maximo=2500.0, monto_gastado=640.0, hangar_unit_id=2)
    db.session.add_all([gas, salidas])
    db.session.commit()

    db.session.add_all([
        BudgetTransaction(budget_id=gas.id, monto=800.0, nota='GASOLINERA CENTRO', fecha=hace(9)),
        BudgetTransaction(budget_id=gas.id, monto=450.0, nota='GASOLINERA SUR', fecha=hace(3)),
        BudgetTransaction(budget_id=salidas.id, monto=640.0, nota='RESTAURANTE', fecha=hace(5)),
        CardTransaction(hangar_unit_id=2, monto=800.0, nota='[GASOLINA] GASOLINERA CENTRO', categoria='PRESUPUESTO VARIABLE', fecha=hace(9)),
        CardTransaction(hangar_unit_id=2, monto=450.0, nota='[GASOLINA] GASOLINERA SUR', categoria='PRESUPUESTO VARIABLE', fecha=hace(3)),
        CardTransaction(hangar_unit_id=2, monto=640.0, nota='[SALIDAS] RESTAURANTE', categoria='PRESUPUESTO VARIABLE', fecha=hace(5)),
    ])

    # 7. Gastos directos a tarjeta
    db.session.add_all([
        CardTransaction(hangar_unit_id=4, monto=326.0, nota='CAFE', categoria='RESTAURANTES/COMIDA', fecha=hace(2)),
        CardTransaction(hangar_unit_id=4, monto=1450.0, nota='SUPERMERCADO', categoria='OTROS', fecha=hace(4)),
        CardTransaction(hangar_unit_id=4, monto=99.0, nota='RECARGA CELULAR', categoria='SERVICIOS', fecha=hace(6)),
        CardTransaction(hangar_unit_id=3, monto=56.0, nota='PEAJE', categoria='TRANSPORTE/GAS', fecha=hace(7)),
        CardTransaction(hangar_unit_id=3, monto=248.0, nota='COMIDA', categoria='RESTAURANTES/COMIDA', fecha=hace(1)),
    ])
    db.session.commit()
    print('Datos de demostracion cargados.')
