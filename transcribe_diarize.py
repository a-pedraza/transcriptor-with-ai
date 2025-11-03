#!/usr/bin/env python3
"""
Script para transcribir audio con diarización usando GPT-4o-transcribe-diarize de OpenAI
Soporta archivos de cualquier tamaño dividiéndolos automáticamente en chunks
"""

import os
import subprocess
import json
import time
from openai import OpenAI
from pydub import AudioSegment
from pydub.utils import mediainfo
from dotenv import load_dotenv


# Límite de OpenAI: 1400 segundos. Usamos 1200 (20 minutos) para tener margen
MAX_CHUNK_DURATION = 1200  # segundos


def get_audio_duration(audio_file_path):
    """
    Obtiene la duración del archivo de audio en segundos

    Args:
        audio_file_path: Ruta al archivo de audio

    Returns:
        float: Duración en segundos
    """
    try:
        info = mediainfo(audio_file_path)
        duration = float(info['duration'])
        return duration
    except Exception as e:
        print(f"Advertencia: No se pudo obtener duración con pydub, intentando con ffprobe...")
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                 audio_file_path],
                capture_output=True,
                text=True
            )
            return float(result.stdout.strip())
        except Exception as e2:
            print(f"Error obteniendo duración: {e2}")
            return None


def split_audio(audio_file_path, chunk_duration=MAX_CHUNK_DURATION):
    """
    Divide el audio en chunks si es necesario

    Args:
        audio_file_path: Ruta al archivo de audio
        chunk_duration: Duración máxima de cada chunk en segundos

    Returns:
        list: Lista de rutas a los chunks creados
    """
    duration = get_audio_duration(audio_file_path)

    if duration is None:
        print("No se pudo determinar la duración del archivo")
        return [audio_file_path]

    print(f"Duración del audio: {duration:.2f} segundos ({duration/60:.2f} minutos)")

    # Si el archivo es menor al límite, no dividir
    if duration <= MAX_CHUNK_DURATION:
        print("El archivo está dentro del límite, no es necesario dividir")
        return [audio_file_path]

    print(f"El archivo supera el límite de {MAX_CHUNK_DURATION} segundos")
    print("Dividiendo en chunks...")

    # Cargar el audio
    audio = AudioSegment.from_file(audio_file_path)

    chunks = []
    chunk_duration_ms = chunk_duration * 1000  # pydub usa milisegundos

    num_chunks = int((duration / chunk_duration) + 1)

    for i in range(num_chunks):
        start_ms = i * chunk_duration_ms
        end_ms = min((i + 1) * chunk_duration_ms, len(audio))

        chunk = audio[start_ms:end_ms]

        # Guardar chunk temporal
        chunk_filename = f"temp_chunk_{i}.mp3"
        chunk.export(chunk_filename, format="mp3")
        chunks.append(chunk_filename)

        print(f"  Chunk {i+1}/{num_chunks}: {start_ms/1000:.2f}s - {end_ms/1000:.2f}s ({chunk_filename})")

    return chunks


def transcribe_chunk(client, audio_file_path, chunk_index=0, time_offset=0):
    """
    Transcribe un chunk de audio con identificación de hablantes

    Args:
        client: Cliente de OpenAI
        audio_file_path: Ruta al archivo de audio
        chunk_index: Índice del chunk (para logging)
        time_offset: Offset de tiempo en segundos para ajustar timestamps

    Returns:
        dict: Resultado de la transcripción con diarización
    """
    print(f"\nTranscribiendo chunk {chunk_index + 1}: {audio_file_path}")
    print("-" * 50)

    # Abrir el archivo de audio
    with open(audio_file_path, "rb") as audio_file:
        # Realizar la transcripción con diarización
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe-diarize",
            file=audio_file,
            response_format="diarized_json",  # Formato específico para diarización
            chunking_strategy="auto"  # Estrategia de chunking (debe ser string, no dict)
        )

    # Nota: Los timestamps no se ajustan aquí porque los objetos Pydantic son inmutables
    # El offset se manejará al combinar las transcripciones
    return response


def combine_transcriptions(transcriptions, offsets):
    """
    Combina múltiples transcripciones en una sola, ajustando timestamps

    Args:
        transcriptions: Lista de respuestas de transcripción
        offsets: Lista de offsets de tiempo para cada transcripción

    Returns:
        dict: Transcripción combinada con segmentos ajustados
    """
    combined = {
        'text': '',
        'segments': []
    }

    for trans, offset in zip(transcriptions, offsets):
        if hasattr(trans, 'text'):
            combined['text'] += trans.text + ' '

        if hasattr(trans, 'segments'):
            # Crear segmentos ajustados con el offset
            for seg in trans.segments:
                adjusted_segment = {
                    'speaker': getattr(seg, 'speaker', 'Speaker A'),
                    'text': getattr(seg, 'text', ''),
                    'start': getattr(seg, 'start', 0) + offset,
                    'end': getattr(seg, 'end', 0) + offset
                }
                combined['segments'].append(adjusted_segment)

    return combined


def print_transcription(result, show_all=True):
    """
    Imprime la transcripción de manera formateada

    Args:
        result: Resultado de la transcripción (puede ser respuesta API o dict)
        show_all: Si es False, solo muestra primeros y últimos segmentos
    """
    print("\n" + "=" * 70)
    print("TRANSCRIPCIÓN CON DIARIZACIÓN")
    print("=" * 70 + "\n")

    segments = []
    if hasattr(result, 'segments'):
        segments = result.segments
    elif isinstance(result, dict) and 'segments' in result:
        segments = result['segments']

    if segments:
        total_segments = len(segments)

        if show_all or total_segments <= 20:
            # Mostrar todos los segmentos
            for segment in segments:
                # Soportar tanto objetos Pydantic como diccionarios
                if isinstance(segment, dict):
                    speaker = segment.get('speaker', 'Speaker A')
                    text = segment.get('text', '')
                    start = segment.get('start', 0)
                    end = segment.get('end', 0)
                else:
                    speaker = getattr(segment, 'speaker', 'Speaker A')
                    text = getattr(segment, 'text', '')
                    start = getattr(segment, 'start', 0)
                    end = getattr(segment, 'end', 0)
                print(f"[{start:.2f}s - {end:.2f}s] {speaker}: {text}")
        else:
            # Mostrar primeros 10 y últimos 10
            print(f"Mostrando primeros 10 y últimos 10 de {total_segments} segmentos...\n")

            for segment in segments[:10]:
                if isinstance(segment, dict):
                    speaker = segment.get('speaker', 'Speaker A')
                    text = segment.get('text', '')
                    start = segment.get('start', 0)
                    end = segment.get('end', 0)
                else:
                    speaker = getattr(segment, 'speaker', 'Speaker A')
                    text = getattr(segment, 'text', '')
                    start = getattr(segment, 'start', 0)
                    end = getattr(segment, 'end', 0)
                print(f"[{start:.2f}s - {end:.2f}s] {speaker}: {text}")

            print("\n... [segmentos intermedios omitidos] ...\n")

            for segment in segments[-10:]:
                if isinstance(segment, dict):
                    speaker = segment.get('speaker', 'Speaker A')
                    text = segment.get('text', '')
                    start = segment.get('start', 0)
                    end = segment.get('end', 0)
                else:
                    speaker = getattr(segment, 'speaker', 'Speaker A')
                    text = getattr(segment, 'text', '')
                    start = getattr(segment, 'start', 0)
                    end = getattr(segment, 'end', 0)
                print(f"[{start:.2f}s - {end:.2f}s] {speaker}: {text}")
    else:
        # Si solo hay texto sin segmentos
        if hasattr(result, 'text'):
            print(result.text)
        elif isinstance(result, dict) and 'text' in result:
            print(result['text'])

    print("\n" + "=" * 70)


def save_transcription(result, output_file):
    """
    Guarda la transcripción en un archivo

    Args:
        result: Resultado de la transcripción
        output_file: Ruta del archivo de salida
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        segments = []
        if hasattr(result, 'segments'):
            segments = result.segments
        elif isinstance(result, dict) and 'segments' in result:
            segments = result['segments']

        if segments:
            for segment in segments:
                # Soportar tanto objetos Pydantic como diccionarios
                if isinstance(segment, dict):
                    speaker = segment.get('speaker', 'Speaker A')
                    text = segment.get('text', '')
                    start = segment.get('start', 0)
                    end = segment.get('end', 0)
                else:
                    speaker = getattr(segment, 'speaker', 'Speaker A')
                    text = getattr(segment, 'text', '')
                    start = getattr(segment, 'start', 0)
                    end = getattr(segment, 'end', 0)
                f.write(f"[{start:.2f}s - {end:.2f}s] {speaker}: {text}\n")
        else:
            if hasattr(result, 'text'):
                f.write(result.text)
            elif isinstance(result, dict) and 'text' in result:
                f.write(result['text'])

    print(f"\nTranscripción guardada en: {output_file}")


def cleanup_temp_files(chunks, original_file):
    """
    Limpia archivos temporales creados

    Args:
        chunks: Lista de archivos de chunks
        original_file: Archivo original (no eliminar)
    """
    for chunk in chunks:
        if chunk != original_file and os.path.exists(chunk):
            try:
                os.remove(chunk)
                print(f"Eliminado archivo temporal: {chunk}")
            except Exception as e:
                print(f"No se pudo eliminar {chunk}: {e}")


def main():
    """
    Función principal
    """
    # Cargar variables de entorno desde .env
    load_dotenv()

    # Verificar que existe la API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: No se encontró OPENAI_API_KEY")
        print("Por favor configura tu API key de una de estas formas:")
        print("  1. Crea un archivo .env con: OPENAI_API_KEY=tu-api-key")
        print("  2. En Windows: set OPENAI_API_KEY=tu-api-key")
        print("  3. En Linux/Mac: export OPENAI_API_KEY=tu-api-key")
        return

    # Archivo de audio a transcribir
    audio_file = "audio.mp3"

    if not os.path.exists(audio_file):
        print(f"ERROR: No se encontró el archivo {audio_file}")
        return

    # Inicializar cliente de OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    try:
        script_start = time.time()

        # Dividir el audio si es necesario
        print("Paso 1: Analizando el archivo de audio...")
        step_start = time.time()
        chunks = split_audio(audio_file)
        step_duration = time.time() - step_start
        print(f"   ⏱ Tiempo: {step_duration:.2f}s")

        print(f"\nPaso 2: Transcribiendo {len(chunks)} chunk(s)...")
        transcribe_start = time.time()

        # Transcribir cada chunk
        transcriptions = []
        offsets = []
        for i, chunk in enumerate(chunks):
            chunk_start = time.time()
            time_offset = i * MAX_CHUNK_DURATION
            offsets.append(time_offset)
            response = transcribe_chunk(client, chunk, i, time_offset)
            transcriptions.append(response)
            chunk_duration = time.time() - chunk_start
            print(f"Chunk {i+1}/{len(chunks)} completado ✓ ({chunk_duration:.2f}s)")

        transcribe_duration = time.time() - transcribe_start
        print(f"   ⏱ Tiempo total de transcripción: {transcribe_duration:.2f}s")

        # Combinar resultados si hay múltiples chunks
        if len(chunks) > 1:
            print("\nPaso 3: Combinando transcripciones...")
            step_start = time.time()
            result = combine_transcriptions(transcriptions, offsets)
            step_duration = time.time() - step_start
            print(f"   ⏱ Tiempo: {step_duration:.2f}s")
        else:
            result = transcriptions[0]

        # Imprimir el resultado
        print("\nPaso 4: Mostrando resultados...")
        print_transcription(result, show_all=False)

        # Guardar en archivo de texto
        output_file = "transcription_output.txt"
        save_transcription(result, output_file)

        # Limpiar archivos temporales
        if len(chunks) > 1:
            print("\nPaso 5: Limpiando archivos temporales...")
            cleanup_temp_files(chunks, audio_file)

        script_duration = time.time() - script_start
        print(f"\n{'='*70}")
        print(f"¡Transcripción completada exitosamente!")
        print(f"⏱ Tiempo total: {script_duration:.2f}s ({script_duration/60:.2f} minutos)")
        print(f"{'='*70}")

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("\nPosibles causas:")
        print("1. API key inválida o sin créditos")
        print("2. Archivo de audio corrupto o formato no soportado")
        print("3. No tienes ffmpeg instalado (necesario para procesar audio)")
        print("4. Problema de conexión con la API de OpenAI")

        # Limpiar archivos temporales en caso de error
        if 'chunks' in locals():
            cleanup_temp_files(chunks, audio_file)


if __name__ == "__main__":
    main()
