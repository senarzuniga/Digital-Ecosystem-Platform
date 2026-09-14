# HD Palletizer — Especificación de captura de datos y KPIs

**Equipo:** INGECART Heavy Duty Palletizer (robot + escuadrado 4 caras + conveyors)  
**Plataforma destino:** Digital Ecosystem Platform (DEP) — Machine Connectivity, Smart Plant Dashboard  
**Referencia competitiva:** Alliance Machine Systems Raptor XR / RDC / RaptorPAL  
**Revisión:** 1.0 — 14 de septiembre de 2026  
**Audiencia:** proveedor de ingeniería de software, Ingeniería de Control INGECART, Producto

---

## 0. Principios de diseño

1. **El PLC calcula el estado; el histórico calcula el KPI.** Los contadores, los estados y los códigos de parada nacen en el PLC con timestamp de PLC. Los KPIs (OEE, MTBF, tiempo de ciclo) se derivan en la plataforma a partir de eventos y contadores, nunca se recalculan a mano en la HMI.
2. **Eventos por cambio, no por tiempo.** Los estados, alarmas y contadores se publican **on-change** (report by exception) con un *heartbeat* periódico. Muestrear estados por tiempo pierde microparadas e infla el tráfico.
3. **Contadores monótonos, no tasas.** Se transmite el acumulado (`bundles_total`), no "paquetes por minuto". La tasa se deriva y así sobrevive a pérdidas de red.
4. **Cada dato con calidad.** Cada muestra lleva `quality` (`good`, `uncertain`, `bad`) y `source_ts` (PLC) además de `ingest_ts` (servidor).
5. **Un KPI solo se publica si su base de tiempo está definida.** OEE por turno, por pedido y por día; nunca "OEE en tiempo real" sin ventana.

---

## 1. Arquitectura de captura

```
PLC HD Palletizer (Siemens S7 / robot controller KUKA·Kawasaki)
        │  OPC UA (subscriptions, on-change)  ── señales de control, contadores, estados
        │  MQTT (Sparkplug B o JSON DEP)      ── publicación a broker de planta
        ▼
Edge gateway (buffer local ≥ 72 h, store-and-forward)
        │  dep/machines/{company_id}/{asset_id}/telemetry
        │  dep/machines/{company_id}/{asset_id}/event
        │  dep/machines/{company_id}/{asset_id}/alert
        ▼
DEP backend (FastAPI) → time-series store (machine_telemetry / Timescale) → KPI engine → Streamlit dashboards
```

- **Protocolo primario:** OPC UA con suscripciones (`MonitoredItems`, `samplingInterval` según tabla). Compatible con `backend/connectors/opcua_connector.py` mediante `node_mapping` en `connector_config`.
- **Protocolo secundario / robot:** MQTT hacia broker de planta; los topics siguen la convención de `backend/connectors/mqtt_connector.py`.
- **Sincronización horaria:** NTP en PLC, robot y edge. Desviación máxima admitida: 100 ms.
- **Persistencia en edge:** el gateway mantiene la cola ante caída de red; ningún contador se pierde.

---

## 2. Catálogo de señales

Nomenclatura: `hdp.<grupo>.<señal>`. Tipos: `BOOL`, `INT`, `DINT`, `REAL`, `STRING`, `ENUM`.

### 2.1 Estado de máquina y modo (base de OEE)

| Señal | Tipo | Unidad | Captura | Frecuencia / deadband | Uso |
|---|---|---|---|---|---|
| `hdp.state.machine_state` | ENUM | — | on-change + heartbeat 5 s | — | Estado ISO 22400: `producing`, `idle_starved`, `idle_blocked`, `stopped_fault`, `stopped_planned`, `changeover`, `manual`, `off` |
| `hdp.state.operating_mode` | ENUM | — | on-change | — | `auto`, `semi_auto`, `manual`, `maintenance` |
| `hdp.state.stop_reason_code` | INT | código | on-change | — | Código de la tabla de causas (anexo A). Obligatorio al salir de `producing` |
| `hdp.state.planned_stop` | BOOL | — | on-change | — | Distingue parada planificada (no penaliza disponibilidad) |
| `hdp.state.emergency_stop` | BOOL | — | on-change | — | Seguridad; latencia ≤ 100 ms |
| `hdp.state.safety_zone_intrusion` | BOOL | — | on-change | — | Escáner / puerta abierta |
| `hdp.state.heartbeat` | DINT | contador | 1 s | — | Detección de pérdida de comunicación |

### 2.2 Producción y contadores (Performance y Quality)

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.prod.bundles_in_total` | DINT | paquetes | on-change | cada evento | Paquetes recibidos en entrada |
| `hdp.prod.bundles_placed_total` | DINT | paquetes | on-change | cada evento | Paquetes colocados en palet (salida buena) |
| `hdp.prod.bundles_rejected_total` | DINT | paquetes | on-change | cada evento | Rechazados, caídos o reprocesados |
| `hdp.prod.layers_completed_total` | DINT | capas | on-change | cada evento | Base del análisis de patrón |
| `hdp.prod.pallets_completed_total` | DINT | palets | on-change | cada evento | Salida final |
| `hdp.prod.pallets_rejected_total` | DINT | palets | on-change | cada evento | Palets rehechos / rechazados por operario |
| `hdp.prod.boxes_per_bundle` | INT | cajas | on-change (receta) | — | Convierte paquetes a cajas |
| `hdp.prod.bundles_per_layer` | INT | paquetes | on-change (receta) | — | Patrón activo |
| `hdp.prod.layers_per_pallet` | INT | capas | on-change (receta) | — | Patrón activo |
| `hdp.prod.recipe_id` | STRING | — | on-change | — | Identificador de receta / SKU |
| `hdp.prod.order_id` | STRING | — | on-change | — | Pedido en curso (desde MES / HMI) |
| `hdp.prod.ideal_cycle_time_s` | REAL | s | on-change (receta) | — | Tiempo ideal por paquete para la receta; base de Performance |

### 2.3 Ciclo del robot (Performance fino y desgaste)

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.robot.cycle_start` / `cycle_end` | evento | timestamp | por ciclo | cada pick | Tiempo de ciclo real por paquete |
| `hdp.robot.cycle_time_s` | REAL | s | por ciclo | cada pick | Distribución de ciclos (P50/P95) |
| `hdp.robot.pick_ok` / `place_ok` | BOOL | — | por ciclo | cada pick | Ciclo válido |
| `hdp.robot.wait_for_bundle_s` | REAL | s | por ciclo | cada pick | Tiempo esperando entrada (starvation) |
| `hdp.robot.wait_for_pallet_s` | REAL | s | por ciclo | cada pick | Tiempo esperando salida (blocking) |
| `hdp.robot.drop_detected` | evento | — | on-change | — | Caída de paquete (fotocélula) |
| `hdp.robot.speed_override_pct` | REAL | % | on-change, deadband 1 % | — | Velocidad programada del robot |
| `hdp.robot.joint_temp_c[1..6]` | REAL | °C | 10 s | deadband 0,5 °C | Tendencia térmica de ejes |
| `hdp.robot.joint_torque_pct[1..6]` | REAL | % | 200 ms durante ciclo | agregar máx/media por ciclo | Sobreesfuerzo y desgaste de reductores |
| `hdp.robot.controller_alarm_code` | INT | código | on-change | — | Alarmas del controlador |

### 2.4 Garra / EOAT

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.gripper.clamp_force_pct` | REAL | % | por ciclo (máx) | — | Sujeción insuficiente → caídas |
| `hdp.gripper.clamp_position_mm` | REAL | mm | por ciclo | — | Deriva mecánica |
| `hdp.gripper.servo_current_a` | REAL | A | 100 ms durante cierre | agregar máx por ciclo | Desgaste servo / fricción |
| `hdp.gripper.vacuum_kpa` | REAL | kPa | 100 ms durante pick | agregar mín por ciclo | Solo si hay ventosas para hojas |
| `hdp.gripper.grip_cycles_total` | DINT | ciclos | on-change | — | Vida útil de la garra |

### 2.5 Escuadrado de 4 caras

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.squaring.cycle_time_s` | REAL | s | por capa | — | Cuello de botella oculto |
| `hdp.squaring.final_position_mm[x,y]` | REAL | mm | por capa | — | Repetibilidad geométrica |
| `hdp.squaring.force_peak_n` | REAL | N | por capa | — | Aplastamiento de cajas |
| `hdp.squaring.servo_current_a` | REAL | A | 100 ms durante ciclo | máx por capa | Desgaste |
| `hdp.squaring.result_ok` | BOOL | — | por capa | — | Capa dentro de tolerancia |

### 2.6 Manipulación de hojas (interlayer, base, tapa)

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.sheet.magazine_level_pct` | REAL | % | 30 s, deadband 5 % | — | Aviso de reposición |
| `hdp.sheet.placed_total` | DINT | hojas | on-change | — | Consumo |
| `hdp.sheet.pick_fail_total` | DINT | fallos | on-change | — | Doble hoja / fallo ventosa |
| `hdp.sheet.magazine_empty` | BOOL | — | on-change | — | Causa de parada |

### 2.7 Conveyors y flujo

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.conv.infeed_occupied` | BOOL | — | on-change | — | Detección starvation |
| `hdp.conv.infeed_queue_count` | INT | paquetes | on-change | — | Acumulación aguas arriba |
| `hdp.conv.outfeed_occupied` | BOOL | — | on-change | — | Detección blocking |
| `hdp.conv.pallet_present_load` | BOOL | — | on-change | — | Palet vacío disponible |
| `hdp.conv.pallet_present_out` | BOOL | — | on-change | — | Palet lleno sin retirar |
| `hdp.conv.speed_mpm[n]` | REAL | m/min | on-change, deadband 0,5 | — | Sincronismo |
| `hdp.conv.vfd_current_a[n]` | REAL | A | 5 s | deadband 0,2 A | Desgaste transmisión |
| `hdp.conv.upstream_request` / `downstream_ready` | BOOL | — | on-change | — | Interlocks con FFG / flejadora / retractiladora |

### 2.8 Energía y neumática

| Señal | Tipo | Unidad | Captura | Frecuencia | Uso |
|---|---|---|---|---|---|
| `hdp.energy.active_power_kw` | REAL | kW | 1 s | deadband 0,2 kW | Perfil de consumo |
| `hdp.energy.energy_total_kwh` | REAL | kWh | 60 s | monótono | kWh por palet |
| `hdp.energy.air_pressure_bar` | REAL | bar | 5 s | deadband 0,1 bar | Causa de fallos de garra |
| `hdp.energy.air_flow_nl_min` | REAL | Nl/min | 5 s | deadband 5 | Fugas |

### 2.9 Alarmas y mantenimiento

| Señal | Tipo | Captura | Uso |
|---|---|---|---|
| `hdp.alarm.active` (lista: código, severidad, ts_on, ts_off, ack_ts) | evento | on-change | Alarmas con duración y reconocimiento |
| `hdp.maint.robot_hours_total` | REAL h | 60 s | Mantenimiento por horas |
| `hdp.maint.grease_cycle_due` | BOOL | on-change | Lubricación |
| `hdp.maint.last_pm_date` | STRING | on-change | Trazabilidad |
| `hdp.maint.operator_id` | STRING | on-change | Análisis por turno / operario (anonimizable) |

### 2.10 Resumen de frecuencias

| Clase de dato | Método | Frecuencia | Latencia objetivo |
|---|---|---|---|
| Seguridad (E-stop, intrusión) | on-change | inmediato | ≤ 100 ms |
| Estados y códigos de parada | on-change + heartbeat | heartbeat 5 s | ≤ 500 ms |
| Contadores de producción | on-change | cada evento | ≤ 1 s |
| Eventos de ciclo robot | por ciclo | cada pick (~2,5 s) | ≤ 1 s |
| Servo / par / corriente | 100–200 ms en ciclo, agregados por ciclo | máx/media/mín por ciclo | 5 s |
| Temperaturas | periódico | 10 s, deadband 0,5 °C | 30 s |
| Energía | periódico | 1 s potencia / 60 s energía | 30 s |
| Niveles / consumibles | periódico | 30 s | 60 s |
| Alarmas | on-change con ts_on/ts_off | inmediato | ≤ 1 s |

**Volumen estimado:** ~60 tags, del orden de 40–60 kB/min en régimen con muestreo de par a 200 ms agregado en edge. Sin agregación, el par a 200 ms multiplica el tráfico por ~30; por eso se agrega en edge y solo se envía el raw bajo demanda (modo diagnóstico).

---

## 3. Modelo de datos en DEP

Extender `MachineTelemetry` (hoy: `temperature`, `vibration`, `power_kw`, `pressure`, `speed_rpm`, `oee`) con dos tablas normalizadas, sin romper el esquema actual:

```sql
-- Muestras numéricas de cualquier tag
CREATE TABLE machine_signal_sample (
  asset_id      TEXT NOT NULL,
  tag           TEXT NOT NULL,          -- p.ej. hdp.robot.cycle_time_s
  source_ts     TIMESTAMPTZ NOT NULL,   -- reloj del PLC
  ingest_ts     TIMESTAMPTZ NOT NULL,
  value_num     DOUBLE PRECISION,
  value_str     TEXT,
  quality       SMALLINT NOT NULL,      -- 0 good, 1 uncertain, 2 bad
  PRIMARY KEY (asset_id, tag, source_ts)
);

-- Eventos de estado con duración (base de OEE y Pareto de paradas)
CREATE TABLE machine_state_event (
  asset_id      TEXT NOT NULL,
  state         TEXT NOT NULL,          -- producing, idle_starved, ...
  reason_code   INTEGER,
  planned       BOOLEAN NOT NULL DEFAULT FALSE,
  ts_start      TIMESTAMPTZ NOT NULL,
  ts_end        TIMESTAMPTZ,            -- NULL mientras está abierto
  order_id      TEXT,
  recipe_id     TEXT,
  shift_id      TEXT,
  PRIMARY KEY (asset_id, ts_start)
);
```

Reglas:

- El estado se cierra al llegar el siguiente; duración = `ts_end - ts_start`.
- Toda parada `stopped_fault` sin `reason_code` en 60 s se marca `unclassified` y aparece como KPI de disciplina (`% paradas clasificadas`).
- Los contadores se guardan como acumulados; las deltas se calculan con protección de *rollover* y de reinicio de PLC (`delta < 0 → delta = valor actual`).

---

## 4. Definiciones matemáticas de KPI

Base normativa: ISO 22400-2 (KPIs de fabricación). Ventana `W` = turno, pedido o día.

### 4.1 Tiempos

```
T_cal      = duración de la ventana W
T_planned  = T_cal − Σ duración(estado = stopped_planned ∨ off)        -- Planned Busy Time
T_run      = Σ duración(estado = producing)                             -- Actual Production Time
T_down_unpl= Σ duración(estado = stopped_fault ∧ planned = false)
T_starved  = Σ duración(estado = idle_starved)
T_blocked  = Σ duración(estado = idle_blocked)
T_change   = Σ duración(estado = changeover)
```

`T_starved` y `T_blocked` se **excluyen** de la disponibilidad del paletizador cuando el análisis es de máquina (la causa es externa) y se **incluyen** cuando el análisis es de línea. El dashboard debe mostrar ambos: **OEE máquina** y **OEE línea**.

### 4.2 Disponibilidad

```
A_machine = (T_planned − T_down_unpl − T_change) / T_planned
A_line    = T_run / T_planned
```

### 4.3 Rendimiento (Performance)

```
Δbundles_placed = bundles_placed_total(fin W) − bundles_placed_total(inicio W)
Δbundles_total  = Δbundles_placed + Δbundles_rejected
ideal_time      = Σ_por_receta ( Δbundles_total_receta × ideal_cycle_time_s_receta )
P = ideal_time / T_run                      -- acotado a [0, 1]
```

`ideal_cycle_time_s` proviene de la receta (FAT por SKU), no del mejor ciclo observado. Si la receta no lo define, se usa el **P10 de los ciclos válidos de esa receta en los últimos 30 días** y se marca el KPI como `estimated`.

### 4.4 Calidad

```
Q_bundle = Δbundles_placed / Δbundles_total
Q_pallet = Δpallets_completed / (Δpallets_completed + Δpallets_rejected)
Q = Q_bundle × Q_pallet
```

### 4.5 OEE y derivados

```
OEE_machine = A_machine × P × Q
OEE_line    = A_line × P × Q
TEEP        = OEE_line × (T_planned / T_cal)
```

Publicar siempre con la ventana y el número de paquetes de la muestra; para W con `Δbundles_total < 200` se marca `low_confidence`.

### 4.6 Ciclo del robot

```
cycle_time_s       = ts(place_ok) − ts(cycle_start)              -- por paquete
cycle_mean_W       = media(cycle_time_s | pick_ok ∧ place_ok)
cycle_P50 / P95    = percentiles sobre ciclos válidos en W
cycle_cv           = desviación_típica / media                   -- estabilidad
throughput_gross   = Δbundles_total / T_run × 60                  -- paquetes/min efectivos
throughput_net     = Δbundles_placed / T_planned × 60            -- paquetes/min sobre tiempo planificado
boxes_per_hour     = Δbundles_placed × boxes_per_bundle / (T_planned/3600)
```

`cycle_mean` excluye explícitamente `wait_for_bundle_s` y `wait_for_pallet_s`: el ciclo mide al robot, la espera mide a la línea.

### 4.7 Pérdidas (Six Big Losses adaptadas)

```
Loss_breakdown  = T_down_unpl / T_planned
Loss_changeover = T_change / T_planned
Loss_starved    = T_starved / T_planned
Loss_blocked    = T_blocked / T_planned
Loss_speed      = 1 − P
Loss_quality    = 1 − Q
Microstops      = nº eventos stopped_fault con duración < 120 s
```

Pareto de `reason_code` por duración total y por frecuencia.

### 4.8 Fiabilidad

```
MTBF_h  = T_run / nº eventos stopped_fault(planned = false)           -- horas
MTTR_min= Σ duración(stopped_fault) / nº eventos stopped_fault × 60
```

Reportar MTBF solo con ≥ 5 fallos en la ventana; si no, agregar ventana (mes rodante).

### 4.9 Energía

```
kWh_per_pallet = Δenergy_total_kwh / Δpallets_completed
kWh_per_1000_boxes = Δenergy_total_kwh / (Δbundles_placed × boxes_per_bundle) × 1000
idle_power_share = Σ(active_power_kw × Δt | estado ≠ producing) / Δenergy_total_kwh
```

### 4.10 Índices de condición (mantenimiento predictivo)

```
gripper_wear_index = z(servo_current_a_max) × 0,5 + z(clamp_position_mm drift) × 0,3 + z(drop_rate) × 0,2
joint_stress_index = media_ejes( z(joint_torque_pct_max) ) ponderada por nº ciclos
squaring_drift_mm  = |final_position_mm − referencia_receta|  (media móvil 100 capas)
```

`z()` = puntuación normalizada frente a la línea base de los primeros 30 días de operación estable de esa receta. Umbrales: aviso a 2σ, alarma a 3σ.

### 4.11 Disciplina de datos

```
classified_stop_pct = paradas con reason_code / paradas totales
data_completeness   = muestras recibidas / muestras esperadas (heartbeat)
clock_skew_ms       = |source_ts − ingest_ts| mediana
```

Si `data_completeness < 98 %` en W, el OEE de esa ventana se publica con marca `data_gap`.

---

## 5. Visualización por audiencia

### 5.1 Operario (HMI / Live Signals) — refresco 1–5 s

- Estado actual con color y causa activa.
- Paquetes/min actual vs objetivo de receta (gauge).
- Cola de entrada, palet disponible, nivel de hojas.
- Alarmas activas con tiempo transcurrido.
- Siguiente acción sugerida (reponer hojas, retirar palet, reset seguridad).

### 5.2 Producción / Plant manager — refresco 1 min, ventana turno

- OEE máquina y OEE línea del turno con desglose A × P × Q (barras apiladas).
- Cascada de pérdidas: planificado → averías → cambios → starved → blocked → velocidad → calidad.
- Pareto Top-10 causas de parada (duración y frecuencia).
- Histograma de ciclo del robot con P50/P95 y CV por receta.
- Timeline de estados del turno (Gantt de colores).
- Producción acumulada vs plan (cajas y palets).

### 5.3 Mantenimiento — refresco 5 min, ventana 7–30 días

- MTBF/MTTR rodantes.
- Tendencias: corriente servo garra, par por eje, temperatura ejes, deriva escuadrado.
- Índices de condición con banda 2σ/3σ.
- Contadores de vida: ciclos garra, horas robot, hojas colocadas.
- Alarmas recurrentes (misma causa > 3 veces/semana).

### 5.4 Board / Dirección — semanal y mensual

- OEE línea y TEEP con tendencia 13 semanas y objetivo.
- Cajas buenas producidas y palets/turno.
- Coste de pérdidas: `horas perdidas × coste hora línea`, por categoría.
- kWh por 1.000 cajas y tendencia.
- Disponibilidad vs SLA contratado; horas de servicio evitadas.
- Benchmark interno entre plantas / líneas con la misma receta.
- Semáforo de calidad de datos (`classified_stop_pct`, `data_completeness`).

Reglas de presentación: un KPI, una ventana, una definición visible en tooltip. Sin OEE "instantáneo". Los valores `estimated`, `low_confidence` o `data_gap` llevan marca visual.

---

## 6. Posicionamiento frente a Alliance Raptor

Hechos publicados por Alliance (acceso 2026-09-14): arquitectura robótica con visión y EOAT, Raptor XR RDC hasta 24 paquetes/min, integración con troqueladora rotativa, controles propios. **No publica** OEE, dashboards, IIoT ni estándares de conectividad en su material comercial.

Implicación de producto: la capacidad de datos no está publicada como diferenciador por el competidor. Para INGECART, la ventaja defendible es **entregar de serie la trazabilidad completa del ciclo, OEE máquina/línea conforme a ISO 22400 y conectividad abierta (OPC UA + MQTT)**, con evidencia contractual en FAT/SAT. Evitar comparar caudales comerciales sin matriz SKU equivalente; comparar en cambio: transparencia de datos, tiempo de clasificación de paradas y coste por 1.000 cajas medido.

---

## 7. Criterios de aceptación (FAT/SAT de datos)

1. 100 % de transiciones de estado con `reason_code` en ≤ 60 s durante 8 h de run-off.
2. `data_completeness ≥ 99 %` y `clock_skew_ms ≤ 100` durante 72 h.
3. Reconciliación: Δ`bundles_placed_total` = recuento físico ± 0,1 % en un turno.
4. OEE calculado por la plataforma reproduce el cálculo manual de un turno con desviación ≤ 0,5 puntos.
5. Corte de red de 30 min sin pérdida de eventos (store-and-forward verificado).
6. Cada KPI del dashboard muestra ventana, definición y marca de confianza.
7. Exportación CSV/Parquet de `machine_state_event` y `machine_signal_sample` por rango de fechas.

---

## Anexo A — Tabla de códigos de parada (propuesta inicial)

| Código | Categoría | Descripción | Planificada |
|---|---|---|---|
| 100–119 | Seguridad | E-stop, intrusión zona, puerta abierta | No |
| 120–139 | Robot | Alarma controlador, colisión, límite de par | No |
| 140–159 | Garra | Fallo pinza, caída de paquete, presión aire | No |
| 160–179 | Escuadrado | Fuera de tolerancia, atasco, fallo servo | No |
| 180–199 | Hojas | Magazine vacío, doble hoja, fallo ventosa | No |
| 200–219 | Conveyors | Atasco entrada/salida, fallo VFD, fotocélula | No |
| 220–239 | Flujo externo | Sin paquetes (starved), sin palet, salida bloqueada | No (externo) |
| 300–319 | Cambio | Cambio de receta, ajuste patrón | Sí |
| 320–339 | Planificado | Mantenimiento preventivo, limpieza, pausa | Sí |
| 340–359 | Organizativo | Sin operario, sin pedido, fin de turno | Sí |
| 999 | — | Sin clasificar (timeout 60 s) | No |

## Anexo B — Mapeo hacia la plataforma DEP actual

| Concepto DEP existente | Este documento |
|---|---|
| `FORMULA_LIBRARY` OEE/Availability/Performance/Quality | Secciones 4.2–4.5 sustituyen las expresiones genéricas por definiciones con base de tiempo explícita |
| `TYPE_LIBRARY["palletizer_hd"].must_signals` | Se amplía con estados ISO 22400, contadores monótonos y eventos de ciclo |
| `MachineTelemetry` | Se conserva; se añaden `machine_signal_sample` y `machine_state_event` |
| `opcua_connector.node_mapping` | Se usa para todos los tags `hdp.*` con suscripción por deadband |
| `mqtt_connector` topics `dep/machines/{company}/{asset}/telemetry|alert` | Se añade `/event` para `machine_state_event` |
| Roles `ROLE_PANELS` | Sección 5 define contenido por rol |
