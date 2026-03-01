# 🤖 Asistente IA - Generador de Esquemas

[🇪🇸 Español](AI_ASSISTANT.md) | [🇬🇧 English](AI_ASSISTANT.en.md)

El asistente IA de SynthDataFactory utiliza **GROQ** con el modelo **llama-3.3-70b-versatile** para generar automáticamente esquemas de datos y sugerir configuración de sink basándose en descripciones en lenguaje natural.

## 🚀 Configuración

### 1. Obtener API Key de GROQ

1. Visita [https://console.groq.com/keys](https://console.groq.com/keys)
2. Crea una cuenta o inicia sesión
3. Genera una nueva API key
4. Copia la API key generada

### 2. Configurar Variable de Entorno

#### Opción A: Usando archivo .env (Recomendado)

1. Copia el archivo `.env.example` a `.env` en la raíz del proyecto:
   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env` y reemplaza `your_groq_api_key_here` con tu API key real:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

#### Opción B: Variable de entorno del sistema

En Windows:
```cmd
set GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

En Linux/Mac:
```bash
export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Reiniciar Docker Compose

Si el sistema ya está en ejecución, reinicia los contenedores para que carguen la nueva variable:

```bash
docker-compose down
docker-compose up -d
```

## 📝 Cómo Usar el Asistente IA

### 1. Acceder al Asistente

1. Abre SynthDataFactory en tu navegador (http://localhost)
2. Inicia sesión (login/registro) en la barra superior
3. Haz clic en el botón **"⭐ Asistente IA"** en la barra superior
4. Se abrirá un modal con un campo de texto

### 2. Describir tus Datos

Describe en lenguaje natural qué tipo de datos quieres simular. Sé específico sobre:
- **Tipo de dispositivo/sistema**: ej. sensores IoT, usuarios, transacciones
- **Campos importantes**: ej. temperatura, humedad, nombre, email
- **Rangos de valores**: ej. temperatura entre 20-80°C
- **Contexto**: ej. planta industrial, sistema bancario, red social

### 3. Ejemplos de Descripciones

#### Ejemplo 1: Sensores IoT
```
Sensores IoT de temperatura, humedad y presión atmosférica en una planta industrial.
La temperatura debe estar entre 20-80°C, la humedad entre 0-100% y la presión entre
900-1100 hPa. Incluir también el estado del sensor (OK, WARNING, ERROR).
```

**Resultado esperado**:
- Campo `temperatura` (float, min: 20, max: 80)
- Campo `humedad` (float, min: 0, max: 100)
- Campo `presion` (float, min: 900, max: 1100)
- Campo `estado` (choice, options: ["OK", "WARNING", "ERROR"])

#### Ejemplo 2: Sistema de Usuarios
```
Sistema de registro de usuarios con nombre completo, email, ciudad y país.
Incluir también una fecha de registro.
```

**Resultado esperado**:
- Campo `nombre_completo` (name)
- Campo `email` (email)
- Campo `ciudad` (city)
- Campo `pais` (country)
- Campo `fecha_registro` (datetime)

#### Ejemplo 3: Transacciones Bancarias
```
Transacciones bancarias con monto entre 10-5000 euros, tipo de transacción
(pago, transferencia, retiro), y un identificador único UUID.
```

**Resultado esperado**:
- Campo `monto` (float, min: 10, max: 5000)
- Campo `tipo_transaccion` (choice, options: ["pago", "transferencia", "retiro"])
- Campo `id_transaccion` (uuid)

### 4. Generar el Esquema

1. Escribe tu descripción en el campo de texto
2. Haz clic en **"🪄 Generar Esquema"**
3. Espera unos segundos mientras la IA procesa tu solicitud
4. El esquema se cargará automáticamente en el diseñador
5. Si el modelo lo sugiere, también se aplicará `target_type` y parámetros del sink
6. ¡Revisa y ajusta si es necesario, luego lanza la simulación!

## 🗄️ Sinks sugeridos por IA

La respuesta del asistente puede incluir:
- `suggested_target_type`: `file`, `mqtt`, `kafka`, `http`, `rabbitmq`, `postgres`, `mongodb`, `mysql`
- `suggested_sink_config`: configuración recomendada para ese target

Si no hay contexto técnico suficiente, la IA tiende a sugerir `file` + `json`.

Formato esperado de respuesta (resumen):

```json
{
  "simulation_name": "nombre",
  "suggested_records": 1000,
  "suggested_target_type": "postgres",
  "suggested_sink_config": {
    "postgres_host": "localhost",
    "postgres_port": 5432,
    "postgres_db": "synthdata",
    "postgres_user": "postgres",
    "postgres_table": "synthetic_data"
  },
  "schema_fields": []
}
```

## 🎯 Tipos de Datos Soportados

El asistente IA puede generar los siguientes tipos de campos (según disponibilidad del modelo y prompt):

| Tipo | Descripción | Parámetros |
|------|-------------|------------|
| `int` | Número entero | min, max |
| `float` | Número decimal | min, max |
| `name` | Nombre de persona (Faker) | - |
| `email` | Dirección de email (Faker) | - |
| `city` | Nombre de ciudad (Faker) | - |
| `country` | Nombre de país (Faker) | - |
| `phone` | Número de teléfono | - |
| `address` | Dirección completa | - |
| `company` | Nombre de empresa | - |
| `job` | Profesión | - |
| `ip_address` | IPv4 | - |
| `latitude` | Latitud | - |
| `longitude` | Longitud | - |
| `credit_card` | Tarjeta de crédito (ficticia) | - |
| `iban` | Código IBAN (ficticio) | - |
| `url` | URL web | - |
| `choice` | Lista de opciones | options |
| `datetime` | Fecha y hora ISO 8601 | - |
| `uuid` | Identificador único UUID4 | - |
| `timeseries` | Serie temporal sintética | base_value, trend_slope, seasonal_amplitude, seasonal_period, noise_level |

## 🔧 Personalización Post-Generación

Después de que la IA genere el esquema, puedes:

1. **Agregar más campos** manualmente
2. **Modificar rangos** de valores (min/max)
3. **Ajustar porcentajes de nulos** para cada campo
4. **Cambiar tipos de datos**
5. **Agregar/eliminar opciones** en campos de tipo `choice`
6. **Guardar como plantilla** para reutilizar

## ⚠️ Solución de Problemas

### Error: "GROQ_API_KEY not configured"
- Verifica que el archivo `.env` existe en la raíz del proyecto
- Asegúrate de que la variable `GROQ_API_KEY` está correctamente configurada
- Reinicia Docker Compose: `docker-compose restart`

### Error: "Error calling GROQ API"
- Verifica que tu API key es válida
- Comprueba tu conexión a internet
- Revisa si has alcanzado el límite de requests de GROQ (límite gratuito)

### El esquema generado no es exactamente lo que necesito
- El asistente IA hace su mejor esfuerzo, pero puede requerir ajustes manuales
- Sé más específico en tu descripción
- Prueba diferentes formulaciones de la descripción
- Ajusta manualmente el esquema después de la generación

## 📊 Límites y Consideraciones

- **Modelo utilizado**: llama-3.3-70b-versatile
- **Temperatura**: 0.7 (balance entre creatividad y precisión)
- **Máximo de tokens**: 2048
- **Tiempo de respuesta**: 2-5 segundos típicamente

## 💡 Consejos

1. **Sé específico**: Cuanto más detallada sea tu descripción, mejor será el resultado
2. **Incluye rangos**: Especifica rangos de valores para campos numéricos
3. **Menciona unidades**: ej. "temperatura en °C", "distancia en metros"
4. **Indica opciones**: Para campos categóricos, menciona las opciones posibles
5. **Revisa siempre**: La IA es una herramienta de ayuda, siempre revisa el resultado

## 🚀 Ejemplo Completo

**Descripción**:
```
Datos de estaciones meteorológicas que miden temperatura exterior entre -10 y 45 grados
Celsius, velocidad del viento entre 0 y 120 km/h, dirección del viento (Norte, Sur,
Este, Oeste), precipitación entre 0 y 50 mm, y calidad del aire (Buena, Moderada, Mala).
Incluir también el ID de la estación como UUID.
```

**Esquema Generado**:
```json
{
  "simulation_name": "Estaciones_Meteorologicas",
  "suggested_records": 500,
  "schema_fields": [
    {"name": "temperatura", "type": "float", "min": -10, "max": 45, "null_percentage": 0},
    {"name": "velocidad_viento", "type": "float", "min": 0, "max": 120, "null_percentage": 0},
    {"name": "direccion_viento", "type": "choice", "options": ["Norte", "Sur", "Este", "Oeste"], "null_percentage": 0},
    {"name": "precipitacion", "type": "float", "min": 0, "max": 50, "null_percentage": 0},
    {"name": "calidad_aire", "type": "choice", "options": ["Buena", "Moderada", "Mala"], "null_percentage": 0},
    {"name": "id_estacion", "type": "uuid", "null_percentage": 0}
  ]
}
```

---

**¿Necesitas ayuda?** Abre un issue en [GitHub](https://github.com/JesusRosaB/SynthDataFactory/issues)