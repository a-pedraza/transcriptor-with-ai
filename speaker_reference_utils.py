#!/usr/bin/env python3
"""
Utilidades para trabajar con speaker references en diarización
"""

import os
import base64
import mimetypes
from pydub import AudioSegment


def analyze_speaker_times(segments):
    """
    Analiza el tiempo total hablado por cada speaker

    Args:
        segments: Lista de segmentos de transcripción (pueden ser objetos Pydantic o dicts)

    Returns:
        dict: {speaker: {'total_time': float, 'segments': [...]}}
    """
    speaker_times = {}

    for segment in segments:
        # Soportar tanto objetos Pydantic como diccionarios
        if isinstance(segment, dict):
            speaker = segment.get('speaker', 'Unknown')
            start = segment.get('start', 0)
            end = segment.get('end', 0)
        else:
            speaker = getattr(segment, 'speaker', 'Unknown')
            start = getattr(segment, 'start', 0)
            end = getattr(segment, 'end', 0)

        duration = end - start

        if speaker not in speaker_times:
            speaker_times[speaker] = {
                'total_time': 0,
                'segments': []
            }

        speaker_times[speaker]['total_time'] += duration
        speaker_times[speaker]['segments'].append({
            'start': start,
            'end': end,
            'duration': duration
        })

    return speaker_times


def select_top_speakers(speaker_times, max_speakers=4):
    """
    Selecciona los TOP N speakers por tiempo hablado

    Args:
        speaker_times: Diccionario de speaker_times
        max_speakers: Máximo número de speakers a retornar

    Returns:
        list: Lista de speakers ordenados por tiempo (descendente)
    """
    # Ordenar por tiempo total (descendente)
    sorted_speakers = sorted(
        speaker_times.items(),
        key=lambda x: x[1]['total_time'],
        reverse=True
    )

    # Retornar solo los TOP N
    return [speaker for speaker, _ in sorted_speakers[:max_speakers]]


def extract_reference_clip(audio_file, start, end, output_file):
    """
    Extrae un clip de audio de referencia

    Args:
        audio_file: Archivo de audio original
        start: Tiempo de inicio en segundos
        end: Tiempo de fin en segundos
        output_file: Archivo de salida

    Returns:
        str: Ruta al archivo creado
    """
    audio = AudioSegment.from_file(audio_file)

    start_ms = int(start * 1000)
    end_ms = int(end * 1000)

    clip = audio[start_ms:end_ms]
    clip.export(output_file, format="mp3")

    return output_file


def find_best_reference_segment(speaker_data, min_duration=2, max_duration=10):
    """
    Encuentra el mejor segmento para usar como referencia

    Args:
        speaker_data: Datos del speaker (dict con 'segments')
        min_duration: Duración mínima en segundos
        max_duration: Duración máxima en segundos

    Returns:
        dict: Segmento seleccionado o None si no hay válidos
    """
    # Filtrar segmentos válidos (2-10 segundos)
    valid_segments = [
        seg for seg in speaker_data['segments']
        if min_duration <= seg['duration'] <= max_duration
    ]

    if not valid_segments:
        return None

    # Retornar el más largo dentro del rango válido
    return max(valid_segments, key=lambda x: x['duration'])


def create_speaker_references(audio_file, first_chunk_response, chunk_offset=0, max_speakers=4):
    """
    Crea clips de referencia basándose en la transcripción del primer chunk

    Args:
        audio_file: Archivo de audio original
        first_chunk_response: Respuesta de transcripción del primer chunk
        chunk_offset: Offset de tiempo del chunk en segundos
        max_speakers: Número máximo de speakers para referencias

    Returns:
        tuple: (speaker_names, reference_files) o (None, None) si no hay referencias válidas
    """
    print("\n" + "=" * 70)
    print("CREANDO REFERENCIAS DE SPEAKERS")
    print("=" * 70)

    # Obtener segmentos
    segments = []
    if hasattr(first_chunk_response, 'segments'):
        segments = first_chunk_response.segments
    elif isinstance(first_chunk_response, dict) and 'segments' in first_chunk_response:
        segments = first_chunk_response['segments']

    if not segments:
        print("No hay segmentos para analizar")
        return None, None

    # Analizar tiempos de cada speaker
    speaker_times = analyze_speaker_times(segments)

    # Seleccionar TOP speakers
    top_speakers = select_top_speakers(speaker_times, max_speakers)

    print(f"\nTop {len(top_speakers)} speakers por tiempo hablado:")
    for i, speaker in enumerate(top_speakers, 1):
        time = speaker_times[speaker]['total_time']
        print(f"  {i}. Speaker {speaker}: {time:.2f}s")

    # Extraer clips de referencia
    speaker_names = []
    reference_files = []

    for speaker in top_speakers:
        # Encontrar el mejor segmento para referencia
        best_segment = find_best_reference_segment(speaker_times[speaker])

        if not best_segment:
            print(f"\nADVERTENCIA: Speaker {speaker} no tiene segmentos validos (2-10s)")
            continue

        # Ajustar tiempos con el offset del chunk
        actual_start = best_segment['start'] + chunk_offset
        actual_end = best_segment['end'] + chunk_offset

        output_file = f"temp_speaker_{speaker}_ref.mp3"

        print(f"\nSpeaker {speaker}:")
        print(f"  Segmento: [{actual_start:.2f}s - {actual_end:.2f}s] = {best_segment['duration']:.2f}s")
        print(f"  Archivo: {output_file}")

        try:
            extract_reference_clip(audio_file, actual_start, actual_end, output_file)
            speaker_names.append(speaker)
            reference_files.append(output_file)
        except Exception as e:
            print(f"  ERROR extrayendo clip: {e}")
            continue

    print("\n" + "=" * 70)
    print(f"Referencias creadas: {len(reference_files)} speakers")
    print("=" * 70)

    if not reference_files:
        return None, None

    return speaker_names, reference_files


def encode_references_for_api(speaker_names, reference_files):
    """
    Codifica los clips de referencia en formato base64 para la API

    Args:
        speaker_names: Lista de nombres de speakers
        reference_files: Lista de rutas a archivos de referencia

    Returns:
        dict: Diccionario para pasar a extra_body de la API
    """
    encoded_references = []

    for clip in reference_files:
        mime_type, _ = mimetypes.guess_type(clip)
        mime_type = mime_type or "audio/mpeg"

        with open(clip, 'rb') as f:
            audio_data = f.read()
            base64_data = base64.b64encode(audio_data).decode('utf-8')
            data_uri = f"data:{mime_type};base64,{base64_data}"
            encoded_references.append(data_uri)

    return {
        "known_speaker_names": speaker_names,
        "known_speaker_references": encoded_references
    }


def cleanup_reference_files(reference_files):
    """
    Limpia archivos de referencia temporales

    Args:
        reference_files: Lista de archivos a eliminar
    """
    for file in reference_files:
        if os.path.exists(file):
            try:
                os.remove(file)
            except Exception as e:
                print(f"No se pudo eliminar {file}: {e}")
