# Traffic Reducer
### Sistema Inteligente para la Optimización del Tráfico Urbano

## Descripción General
Traffic Reducer es un sistema basado en **inteligencia artificial** diseñado para optimizar el flujo vehicular en intersecciones urbanas. El proyecto surge como respuesta a las limitaciones de los sistemas semafóricos tradicionales, los cuales operan con temporizaciones fijas que no se adaptan a las condiciones reales del tránsito.

Mediante el uso de visión por computadora y modelos inteligentes de toma de decisiones, Traffic Reducer permite una gestión dinámica, segura y eficiente del tráfico urbano.

---

## Planteamiento del Problema
En muchos países, los semáforos funcionan bajo configuraciones estáticas que no consideran las variaciones del flujo vehicular en tiempo real. Esta situación genera múltiples consecuencias negativas, tales como:

- Congestión frecuente en intersecciones críticas  
- Largas filas vehiculares en ciertos carriles mientras otros permanecen subutilizados  
- Incremento en los tiempos de espera y pérdida de productividad  
- Mayor consumo de combustible y emisiones contaminantes  
- Aumento del estrés en conductores y peatones  
- Retrasos en la circulación de vehículos de emergencia (ambulancias, bomberos y policía)  

---

## Solución Propuesta
Traffic Reducer propone un modelo inteligente y adaptativo para el control semafórico, capaz de responder a las condiciones reales del tránsito.

El sistema:

- Analiza el volumen y densidad vehicular mediante cámaras en intersecciones  
- Detecta peatones en cruces y pasos peatonales  
- Identifica vehículos de emergencia a través de patrones visuales y señales prioritarias  
- Procesa la información en tiempo real utilizando inteligencia artificial  
- Ajusta dinámicamente las fases y tiempos de los semáforos  
- Prioriza automáticamente a peatones y servicios de emergencia cuando es necesario  

---

## Gestión Inteligente de Prioridades
El modelo ha sido optimizado para otorgar **prioridad contextual** en escenarios críticos, tales como:

- Cruce seguro y oportuno de peatones  
- Paso inmediato de ambulancias, unidades de bomberos y patrullas policiales  
- Reducción de tiempos de respuesta ante emergencias  
- Balance entre fluidez vehicular y seguridad vial  

Este enfoque garantiza que la optimización del tráfico no comprometa la seguridad humana.

---

## Objetivos del Proyecto

### Objetivo General
Reducir el tiempo promedio de espera de los vehículos en intersecciones urbanas mediante la automatización del control semafórico utilizando inteligencia artificial.

### Objetivos Específicos
- Optimizar el flujo vehicular en tiempo real  
- Disminuir la congestión en intersecciones de alta demanda  
- Garantizar prioridad a peatones y vehículos de emergencia  
- Mejorar la seguridad vial  
- Reducir el impacto ambiental del tránsito urbano  

---

## Métricas de Evaluación
El desempeño del sistema puede evaluarse a través de las siguientes métricas:

- Reducción del tiempo promedio de espera  
- Disminución de la longitud de las filas vehiculares  
- Reducción de detenciones innecesarias  
- Incremento de la velocidad promedio de circulación  
- Mejora en los tiempos de respuesta de los servicios de emergencia  

---

## Propuesta de Valor

### Impacto Social
- Mejora en la experiencia de movilidad diaria  
- Mayor seguridad para peatones  
- Reducción del estrés asociado al tránsito  
- Facilitación del desplazamiento de servicios esenciales  

### Impacto Ambiental
- Disminución del tiempo de ralentí vehicular  
- Reducción de emisiones contaminantes  
- Menor consumo de combustibles fósiles  
- Disminución de la contaminación acústica  

### Impacto Económico
- Alternativa de bajo costo frente a sistemas tradicionales  
- Reducción de pérdidas por tiempo improductivo  
- Optimización del consumo de combustible  
- Viabilidad para ciudades con presupuestos limitados  

---

## Conclusión
Traffic Reducer demuestra cómo la inteligencia artificial puede aplicarse de forma efectiva a los desafíos de la movilidad urbana. Su enfoque adaptativo permite una gestión más eficiente, segura y sostenible del tránsito, priorizando la vida humana y optimizando la infraestructura existente.

---

## Traffic Reducer
**Inteligencia artificial al servicio de la movilidad urbana**






## MANUAL DE INSTALACIÓN Y USO - SYSTEMA DE TRÁFICO IA

Este archivo detalla los pasos para instalar y ejecutar el sistema de control de tráfico con visión artificial.

### 1. REQUISITOS PREVIOS
Asegúrate de tener instalado Python (preferiblemente versión 3.10 o 3.11).
Puedes verificarlo abriendo la terminal y escribiendo:
   python --version

### 2. INSTALACIÓN DE DEPENDENCIAS (LIBRERÍAS)
El sistema necesita varias librerías para funcionar (IA, Visión, Web, etc.).
Todas están listadas en el archivo "requirements.txt".

Para instalarlas automáticamente, abre una terminal en esta carpeta y ejecuta:

   pip install -r requirements.txt

Esto instalará:
- Flask (Servidor Web)  
- OpenCV (Visión Artificial)
- Ultralytics (Detección de Autos YOLOv8)
- YT-DLP (Conexión con YouTube)
- Pandas/Numpy/Sklearn (Procesamiento de Datos)

### 3. CÓMO ARRANCAR EL PROGRAMA
Una vez instaladas las dependencias, sigue estos pasos para iniciar el sistema:

1. Abre la terminal en la carpeta del proyecto.
2. Ejecuta el siguiente comando:

   py traffic_app/app.py

   (Nota: Si "py" no funciona, prueba con "python traffic_app/app.py" o "python3 traffic_app/app.py")

3. Verás mensajes en la terminal indicando que el modelo se cargó y la cámara se está iniciando.
4. Cuando veas "Stream Connected" y "Running on http://127.0.0.1:5000", el sistema está listo.

### 4. USO DEL SISTEMA
1. Abre tu navegador web (Chrome, Edge, etc.).
2. Entra a la dirección: http://127.0.0.1:5000
3. Verás la simulación de tráfico.
4. Para activar la Visión Artificial en vivo, haz clic en el interruptor:
   "LIVE SIMULATION MODE"
5. El sistema empezará a detectar autos en el video de YouTube y ajustará los semáforos automáticamente según la "Ley de la Mayoría" (Carril con más autos = Luz Verde).

### SOLUCIÓN DE PROBLEMAS
- Si ves errores rojos en la terminal sobre "TLS" o "Socket": Ignóralos, el sistema tiene un sistema de reconexión automática que los gestiona.
- Si el video no carga: Verifica tu conexión a internet, ya que depende de YouTube en vivo.
