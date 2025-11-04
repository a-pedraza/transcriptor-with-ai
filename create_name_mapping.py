"""
Script para crear mapeo de iniciales a nombres completos.
Toma capturas al inicio y final del video para identificar todos los participantes.
"""

import os
import subprocess
import base64
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, Dict
import json

# Load environment variables
load_dotenv()

class Participant(BaseModel):
    """Información de un participante identificado"""
    full_name: str  # Nombre completo (ej: "Kate Ballet")
    initials: Optional[str] = None  # Iniciales si son visibles (ej: "KB")
    role_or_info: Optional[str] = None  # Info adicional (ej: "External", "Host")

class ParticipantMapping(BaseModel):
    """Mapeo completo de participantes encontrados"""
    participants: List[Participant]
    total_found: int
    screenshot_timestamp: str
    notes: str  # Observaciones sobre la captura

def extract_screenshot(video_file, timestamp_seconds, output_file):
    """Extrae screenshot del video en timestamp específico"""
    hours = int(timestamp_seconds // 3600)
    minutes = int((timestamp_seconds % 3600) // 60)
    seconds = timestamp_seconds % 60

    timestamp_str = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    cmd = [
        'ffmpeg',
        '-ss', timestamp_str,
        '-i', video_file,
        '-frames:v', '1',
        '-q:v', '2',
        '-y',
        output_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error extrayendo screenshot: {result.stderr}")
        return None

    if not os.path.exists(output_file):
        print(f"Screenshot no fue creado: {output_file}")
        return None

    return output_file

def encode_image(image_path):
    """Convierte imagen a base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_participants_from_screenshot(client, screenshot_path, timestamp_info):
    """
    Usa GPT-4 Vision para extraer TODOS los participantes visibles.
    """

    prompt = """
TAREA: Identifica TODOS los participantes visibles en esta videollamada.

BUSCA EN ESTOS LUGARES:
1. **AVATARES/VIDEOS de participantes** (usualmente arriba o al lado)
2. **LISTA DE PARTICIPANTES** (panel lateral si está visible)
3. **NOMBRES en pantalla** (cualquier lugar donde aparezcan nombres)

PARA CADA PARTICIPANTE ENCUENTRA:
- **Nombre completo** (ej: "Kate Ballet", "Sean Hamad")
- **Iniciales** si son visibles en el avatar (ej: "KB", "SH")
- **Info adicional** (ej: "External", "Host", "Organizer")

INSTRUCCIONES CRÍTICAS:
- NO ignores a nadie, incluso si solo ves iniciales
- Si ves "KB" pero no el nombre completo, repórtalo como iniciales
- Si alguien está compartiendo pantalla, ignora el contenido compartido
- Enfócate en los participantes, NO en el contenido

RESPONDE con la lista COMPLETA de participantes.
"""

    base64_image = encode_image(screenshot_path)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            response_format=ParticipantMapping,
            temperature=0
        )

        result = completion.choices[0].message.parsed
        return result

    except Exception as e:
        print(f"Error analizando screenshot: {e}")
        return None

def create_name_mapping(video_file, video_duration_seconds, output_dir="mapping_screenshots"):
    """
    Crea mapeo de nombres tomando capturas al inicio y final del video.
    """

    client = OpenAI()

    # Crear directorio para screenshots
    os.makedirs(output_dir, exist_ok=True)

    # Definir momentos para capturas
    # Inicio: 10s, 30s, 60s
    # Final: 30s antes del final, 15s antes del final
    start_timestamps = [10, 30, 60]
    end_timestamps = [
        max(video_duration_seconds - 30, 0),
        max(video_duration_seconds - 15, 0)
    ]

    all_timestamps = start_timestamps + end_timestamps

    print("="*80)
    print("CREACION DE MAPEO DE NOMBRES")
    print("="*80)
    print(f"Video: {video_file}")
    print(f"Duracion: {video_duration_seconds}s ({video_duration_seconds/60:.1f} min)")
    print(f"Capturas a tomar: {len(all_timestamps)}")
    print()

    all_participants = {}  # {nombre_completo: Participant}

    for i, timestamp in enumerate(all_timestamps, 1):
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        timestamp_str = f"{hours:02d}h{minutes:02d}m{seconds:02d}s"

        position = "inicio" if timestamp < 120 else "final"

        print(f"[{i}/{len(all_timestamps)}] Captura en {timestamp_str} ({position})...")

        # Extraer screenshot
        screenshot_file = os.path.join(
            output_dir,
            f"mapping_{position}_{int(timestamp)}s_{timestamp_str}.jpg"
        )

        screenshot_path = extract_screenshot(video_file, timestamp, screenshot_file)

        if not screenshot_path:
            print(f"  X Error extrayendo screenshot")
            continue

        print(f"  OK Screenshot guardado")

        # Analizar con GPT-4 Vision
        print(f"  Analizando con GPT-4 Vision...")
        result = extract_participants_from_screenshot(client, screenshot_path, timestamp_str)

        if not result:
            print(f"  X Error en analisis")
            continue

        print(f"  OK Encontrados {result.total_found} participantes")

        # Agregar participantes al mapeo
        for participant in result.participants:
            if participant.full_name not in all_participants:
                all_participants[participant.full_name] = participant
                print(f"    + {participant.full_name}", end="")
                if participant.initials:
                    print(f" ({participant.initials})", end="")
                if participant.role_or_info:
                    print(f" - {participant.role_or_info}", end="")
                print()
            else:
                # Ya lo tenemos, pero actualizar info si es necesario
                existing = all_participants[participant.full_name]
                if not existing.initials and participant.initials:
                    existing.initials = participant.initials
                    print(f"    ~ Actualizado {participant.full_name}: iniciales = {participant.initials}")

        print()

    print("="*80)
    print("MAPEO COMPLETO")
    print("="*80)
    print(f"Total participantes identificados: {len(all_participants)}")
    print()

    # Crear mapeos
    initials_to_name = {}  # {"KB": "Kate Ballet"}
    name_list = []

    for participant in all_participants.values():
        name_list.append(participant.full_name)
        if participant.initials:
            initials_to_name[participant.initials] = participant.full_name
            print(f"  {participant.initials:4s} -> {participant.full_name}", end="")
        else:
            print(f"  ---- -> {participant.full_name}", end="")

        if participant.role_or_info:
            print(f" ({participant.role_or_info})", end="")
        print()

    # Guardar mapeo en archivo JSON
    mapping_data = {
        "initials_to_name": initials_to_name,
        "all_names": name_list,
        "participants_detailed": [
            {
                "full_name": p.full_name,
                "initials": p.initials,
                "role_or_info": p.role_or_info
            }
            for p in all_participants.values()
        ]
    }

    mapping_file = "name_mapping.json"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, indent=2, ensure_ascii=False)

    print()
    print(f"OK Mapeo guardado en: {mapping_file}")
    print()

    return mapping_data

if __name__ == "__main__":
    # Configuración
    video_file = "G:\\personal\\transcription-project\\Recording 2025-10-27 150252.mp4"

    # Obtener duración del video
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_file
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    video_duration = float(result.stdout.strip())

    # Crear mapeo
    mapping = create_name_mapping(video_file, video_duration)

    print("="*80)
    print("LISTO!")
    print("="*80)
    print(f"Mapeo creado con {len(mapping['all_names'])} participantes")
    print(f"Mapeo de iniciales: {len(mapping['initials_to_name'])} entradas")
