TEXTS = {
    "es": {
        "meta": {
            "title": "SynthDataFactory API",
            "description": """
            🏭 **El Generador de Datos Sintéticos Open Source Definitivo**
            
            API REST para generar datasets sintéticos complejos, simular tráfico IoT y probar sistemas de Big Data en tiempo real.
            
            ## 🎯 Características
            * **Simulaciones Multi-Salida**: Archivos, MQTT, Kafka, HTTP, RabbitMQ.
            * **Modo Multi-Sensor**: Flotas de IoT.
            * **Generación Inteligente**: Faker, pesos, rangos.
            """,
            "contact_name": "SynthDataFactory",
            "tags": [
                {"name": "Simulaciones", "description": "Operaciones para crear, controlar y monitorizar simulaciones"},
                {"name": "Archivos", "description": "Gestión y descarga de archivos generados"}
            ]
        },
        "endpoints": {
            "start": {
                "summary": "Iniciar una nueva simulación",
                "desc": "Crea y encola una nueva simulación de datos sintéticos. La simulación corre en background.",
                "response": "Simulación creada y encolada exitosamente"
            },
            "stop": {
                "summary": "Detener una simulación",
                "desc": "Envía una señal de parada controlada. El estado pasará a 'stopped'.",
                "response": "Señal de parada enviada",
                "error_404": "Simulación no encontrada"
            },
            "all": {
                "summary": "Obtener estado de todas las simulaciones",
                "desc": "Retorna el estado actual (queued, running, completed, stopped) de todas las simulaciones."
            },
            "list_files": {
                "summary": "Listar archivos generados",
                "desc": "Obtiene la lista de archivos (JSON, CSV, etc.) ordenados por fecha."
            },
            "download": {
                "summary": "Descargar un archivo",
                "desc": "Descarga directa del archivo generado.",
                "error_404": "Archivo no encontrado"
            }
        }
    },
    "en": {
        "meta": {
            "title": "SynthDataFactory API (EN)",
            "description": """
            🏭 **The Ultimate Open Source Synthetic Data Generator**
            
            REST API to generate complex synthetic datasets, simulate IoT traffic, and test Big Data systems in real-time.
            
            ## 🎯 Features
            * **Multi-Output Simulations**: Files, MQTT, Kafka, HTTP, RabbitMQ.
            * **Multi-Sensor Mode**: IoT Fleets.
            * **Smart Generation**: Faker, weighted distributions, ranges.
            """,
            "contact_name": "SynthDataFactory",
            "tags": [
                {"name": "Simulations", "description": "Operations to create, control, and monitor simulations"},
                {"name": "Files", "description": "Management and download of generated files"}
            ]
        },
        "endpoints": {
            "start": {
                "summary": "Start a new simulation",
                "desc": "Creates and queues a new synthetic data simulation running in the background.",
                "response": "Simulation created and queued successfully"
            },
            "stop": {
                "summary": "Stop a simulation",
                "desc": "Sends a controlled stop signal. Status will change to 'stopped'.",
                "response": "Stop signal sent",
                "error_404": "Simulation not found"
            },
            "all": {
                "summary": "Get status of all simulations",
                "desc": "Returns current status (queued, running, completed, stopped) of all simulations."
            },
            "list_files": {
                "summary": "List generated files",
                "desc": "Gets the list of files (JSON, CSV, etc.) sorted by date."
            },
            "download": {
                "summary": "Download a file",
                "desc": "Direct download of the generated file.",
                "error_404": "File not found"
            }
        }
    }
}