# AERO HUD

Panel de mando financiero personal con estética de cabina de aviación. Junta en un solo lugar la nómina, las tarjetas, las deudas a meses sin intereses (MSI), las tandas, las suscripciones y los presupuestos variables, y calcula cuánto efectivo libre queda cada mes.

Proyecto personal hecho con Flask. Los datos de la demostración son inventados.

## Pantallas

| Radar (flujo de efectivo del mes) | Hangar (tarjetas y simulador de nómina) |
| --- | --- |
| ![Radar](docs/radar.png) | ![Hangar](docs/hangar.png) |

| Logística (tandas, MSI y cargas recurrentes) | Conciliación (cierre de mes) |
| --- | --- |
| ![Logística](docs/logistica.png) | ![Conciliación](docs/conciliacion.png) |

## Qué hace

- **Radar:** resume el mes. Ingreso neto proyectado, menos ahorro, gastos fijos, tandas y MSI, igual a presupuesto disponible; gráfica de distribución, rendimiento anual contra una meta y presupuestos variables con botón para registrar cada gasto.
- **Hangar y nómina:** administra cuentas y tarjetas (límite, día de corte, día de pago, tasa) y simula la nómina: ISR retenido contra el cálculo con la tabla del SAT, aguinaldo, prima vacacional y fondo de ahorro.
- **Logística:** tandas con su avance y su turno, compras a MSI con pago mensual, y cargas recurrentes (seguros, suscripciones, ahorro) ligadas a la tarjeta de la que salen.
- **Conciliación:** cierre mensual. Audita las salidas del mes, reinicia presupuestos y asigna el ahorro a una cuenta destino.
- **Sistema experto:** reglas simples que avisan de deuda por MSI y de gasto hormiga. El botón de consulta con IA es un marcador de posición para una integración futura.

## Arquitectura

```
Flask (app factory)
 ├── radar      resumen del mes, presupuestos, conciliación
 ├── hangar     cuentas, tarjetas y simulador de nómina
 ├── logistics  tandas, MSI y cargas recurrentes
 └── payroll    cálculo de nómina e ISR
SQLAlchemy + SQLite  ·  Jinja2 + Tailwind + Chart.js
```

Cada módulo es un blueprint de Flask con sus rutas y plantillas. El modelo de datos (`app/models.py`) tiene 8 tablas: perfil de usuario, unidades del hangar, cargas recurrentes, tandas, compras MSI, presupuestos variables, gastos de presupuesto y gastos de tarjeta.

## Cómo correrlo

```bash
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py             # carga datos de demostración
python run.py                   # http://localhost:8888
```

Variables opcionales: `SECRET_KEY`, `DATABASE_URL`, `PORT` y `FLASK_DEBUG=1`.

Sin `seed_demo.py` la base arranca vacía y puedes capturar tus propios datos desde la interfaz. La base local no se sube al repositorio.

## Ideas para seguir

- Conectar el botón de IA a un modelo para dar recomendaciones sobre el flujo del mes.
- Importar movimientos desde el estado de cuenta en PDF o CSV.
- Alertas de fechas de corte y pago.
- Pruebas automáticas de los cálculos de ISR y MSI.

## Stack

Python, Flask, SQLAlchemy, SQLite, Jinja2, Tailwind CSS, Chart.js.
