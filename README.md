# Proyecto de Transcripción con Diarización

Proyecto sencillo para transcribir audio con identificación de hablantes usando el nuevo modelo **GPT-4o-transcribe-diarize** de OpenAI.

## Características

- Transcripción de audio con alta precisión
- Diarización (identificación de hablantes): distingue automáticamente entre diferentes personas
- Soporte para archivos de cualquier tamaño: divide automáticamente archivos grandes
- Soporte para 100+ idiomas
- Timestamps precisos para cada segmento
- Velocidad: ~15 segundos para transcribir 10 minutos de audio

## Requisitos

- Python 3.7 o superior
- FFmpeg instalado en el sistema (para procesamiento de audio)
- API key de OpenAI con acceso al modelo `gpt-4o-transcribe-diarize`
- Archivo de audio (formatos soportados: mp3, mp4, mpeg, mpga, m4a, wav, webm)

## Instalación

1. Instalar FFmpeg (si no lo tienes):

**Windows:**
- Descarga desde https://ffmpeg.org/download.html
- O usa Chocolatey: `choco install ffmpeg`

**Linux:**
```bash
sudo apt-get install ffmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

2. Instalar las dependencias de Python:

```bash
pip install -r requirements.txt
```

3. Configurar tu API key de OpenAI:

**Opción 1 (Recomendada): Usar archivo .env**

Crea un archivo `.env` en el directorio del proyecto:

```bash
OPENAI_API_KEY=tu-api-key-aqui
```

**Opción 2: Variable de entorno**

Windows:
```cmd
set OPENAI_API_KEY=tu-api-key-aqui
```

Linux/Mac:
```bash
export OPENAI_API_KEY=tu-api-key-aqui
```

## Uso

### Uso básico

El script transcribirá automáticamente el archivo `audio.mp3` que se encuentra en el directorio:

```bash
python transcribe_diarize.py
```

### Salida

El script genera dos tipos de salida:

1. **Salida en consola**: Muestra la transcripción formateada con timestamps y hablantes
2. **Archivo de texto**: Guarda la transcripción en `transcription_output.txt`

### Formato de salida

```
[0.00s - 5.23s] Speaker A: Hola, ¿cómo estás?
[5.50s - 8.91s] Speaker B: Muy bien, gracias por preguntar.
[9.12s - 15.44s] Speaker A: Me alegro, quería preguntarte sobre el proyecto.
```

## Cómo funciona

El script funciona automáticamente con archivos de cualquier tamaño:

1. **Archivos pequeños (< 20 minutos)**: Se transcriben directamente sin división
2. **Archivos grandes (> 20 minutos)**: Se dividen automáticamente en chunks de 20 minutos, se transcriben por separado y se combinan manteniendo los timestamps correctos

Para tu archivo actual:
- Duración: 60.4 minutos
- Se dividirá en: 4 chunks de ~20 minutos cada uno
- Tiempo estimado: 2-3 minutos de procesamiento total

## Limitaciones

- Los hablantes se identifican como "Speaker A", "Speaker B", etc. (no asigna nombres automáticamente)
- Requiere conexión a internet
- Cada chunk tiene un límite de 1400 segundos, pero el script maneja esto automáticamente

## Estructura del proyecto

```
transcription-project/
├── audio.mp3                    # Archivo de audio a transcribir
├── transcribe_diarize.py        # Script principal
├── requirements.txt             # Dependencias de Python
├── .env.example                 # Ejemplo de configuración
└── README.md                    # Esta documentación
```

## Solución de problemas

### Error: "No se encontró OPENAI_API_KEY"
Asegúrate de haber configurado la variable de entorno con tu API key.

### Error: "API key inválida"
Verifica que tu API key sea correcta y tenga créditos disponibles.

### Error: "Archivo demasiado grande"
El archivo no puede superar los 1400 segundos. Considera dividirlo en partes más pequeñas.

### Error: "Formato no soportado"
Convierte tu audio a uno de los formatos soportados: mp3, mp4, mpeg, mpga, m4a, wav, webm.

## Más información

- [Documentación oficial de GPT-4o-transcribe-diarize](https://platform.openai.com/docs/models/gpt-4o-transcribe-diarize)
- [API Reference de OpenAI](https://platform.openai.com/docs/api-reference/audio)
