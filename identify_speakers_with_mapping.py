"""
Script para identificar speakers usando mapeo de nombres.
Busca indicadores visuales de quién está hablando activamente.
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

class SpeakerIdentification(BaseModel):
    """Resultado de identificación de un speaker"""
    number_of_people_detected: int  # Número de personas con borde resaltado
    speaking_person_name: Optional[str] = None  # Nombre completo si se encuentra
    speaking_person_initials: Optional[str] = None  # Iniciales si se encuentran
    confidence: str  # 'high', 'medium', 'low'
    visual_indicators: List[str]  # Qué se vio (ej: "borde resaltado en avatar KB")
    reasoning: str

def load_name_mapping(mapping_file="name_mapping.json"):
    """Carga el mapeo de nombres desde archivo"""
    if not os.path.exists(mapping_file):
        print(f"ADVERTENCIA: No se encontro mapeo de nombres: {mapping_file}")
        return None

    with open(mapping_file, 'r', encoding='utf-8') as f:
        return json.load(f)

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

def identify_active_speaker(client, screenshot_path, context_text, known_participants):
    """
    Identifica quién está hablando activamente en el screenshot.
    """

    # Crear lista de participantes conocidos para el prompt
    participants_info = "Participantes conocidos en la llamada:\n"
    for p in known_participants.get('participants_detailed', []):
        participants_info += f"  - {p['full_name']}"
        if p.get('initials'):
            participants_info += f" (iniciales: {p['initials']})"
        if p.get('role_or_info'):
            participants_info += f" - {p['role_or_info']}"
        participants_info += "\n"

    prompt = f"""
TAREA: Identifica quién está hablando ACTIVAMENTE en este momento.

{participants_info}

PASO 1: EXAMINA CUIDADOSAMENTE cada avatar y CUENTA cuántos tienen borde resaltado
Mira el lado derecho donde están los avatares. Para CADA avatar (JK, DM, ML, PW, SH, DS, KB, JH, SP, KM, A):
- ¿Tiene un borde azul/verde/blanco alrededor? (puede ser BRILLANTE o SUTIL)
- Cuenta TODOS los bordes, incluso los sutiles
- Reporta el número EXACTO en number_of_people_detected
- Lista cuáles tienen borde (ej: "KB y DM tienen borde")

IMPORTANTE: Un borde puede ser:
- Muy brillante y obvio
- Sutil pero presente
- Azul claro, azul oscuro, verde, o blanco

DEBES reportar number_of_people_detected como número entero (1, 2, 3, etc.)

PASO 2: Evalúa la situación basándote en el CONTEO EXACTO
- Si EXACTAMENTE 1 persona tiene borde → confidence = "high"
- Si 2 o MÁS personas tienen borde → confidence = "low" (SIN EXCEPCIONES)
- Si ninguno tiene borde → busca otros indicadores, confidence = "medium"

REGLA ABSOLUTA: Si encontraste 2+ personas con borde, DEBES marcar confidence = "low"
NO importa si uno es "más prominente" - si hay 2+, es "low"

PASO 3: Identifica a la persona
- Si hay SOLO 1 con borde: reporta ese
- Si hay 2+ con borde: reporta el más prominente PERO marca confidence = "low"
- En reasoning, menciona todos los que tienen borde

INSTRUCCIONES CRÍTICAS:
- **SÉ MUY CUIDADOSO** al contar - no te apresures
- **CUENTA BORDES SUTILES** también - no solo los muy brillantes
- **IGNORA** el contenido de pantalla compartida (Excel, PowerPoint, etc.)
- **Si tienes DUDA** entre 1 o 2 personas → marca confidence = "low"

CONTEXTO del audio:
"{context_text[:200]}..."

En tu reasoning, LISTA específicamente cuántos avatares tienen borde y cuáles son (ej: "2 personas: KB y DM").
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
            response_format=SpeakerIdentification,
            temperature=0
        )

        result = completion.choices[0].message.parsed
        return result

    except Exception as e:
        print(f"Error analizando screenshot: {e}")
        return None

def load_transcription_segments(transcription_file):
    """Carga segmentos de transcripción desde archivo"""
    segments_by_speaker = {}

    with open(transcription_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith('['):
                continue

            # Parse format: [0.00s - 0.30s] A:  Sorry.
            try:
                # Extract timestamps and content
                timestamp_end = line.find(']')
                if timestamp_end == -1:
                    continue

                timestamp_part = line[1:timestamp_end]  # Remove [ and ]
                rest = line[timestamp_end + 1:].strip()

                # Parse timestamps (format: "0.00s - 0.30s")
                times = timestamp_part.split(' - ')
                start_seconds = float(times[0].replace('s', ''))
                end_seconds = float(times[1].replace('s', ''))

                # Parse speaker and text (format: "A:  Sorry.")
                if ':' not in rest:
                    continue

                speaker, text = rest.split(':', 1)
                speaker = speaker.strip()
                text = text.strip()

                # Add to segments
                if speaker not in segments_by_speaker:
                    segments_by_speaker[speaker] = []

                segments_by_speaker[speaker].append({
                    'start': start_seconds,
                    'end': end_seconds,
                    'text': text,
                    'speaker': speaker
                })

            except (ValueError, IndexError) as e:
                # Skip malformed lines
                continue

    return segments_by_speaker

def select_best_segments(segments, max_segments=3):
    """
    Selecciona los mejores segmentos para identificación.
    Prioriza segmentos largos donde la persona habla mucho tiempo.
    """
    # Filtrar segmentos muy cortos (< 8 segundos)
    # Preferir segmentos entre 10-30 segundos
    good_segments = [
        seg for seg in segments
        if 8 <= (seg['end'] - seg['start']) <= 30
    ]

    if not good_segments:
        # Si no hay buenos, aceptar cualquiera > 5 segundos
        good_segments = [seg for seg in segments if (seg['end'] - seg['start']) >= 5]

    if not good_segments:
        # Último recurso: todos
        good_segments = segments

    # Ordenar por duración (MÁS LARGO = MEJOR)
    # Queremos momentos donde la persona habla mucho tiempo seguido
    good_segments.sort(key=lambda s: (s['end'] - s['start']), reverse=True)

    return good_segments[:max_segments]

def identify_all_speakers(video_file, transcription_file, name_mapping, output_dir="identification_screenshots"):
    """Identifica todos los speakers usando el mapeo de nombres"""

    client = OpenAI()
    os.makedirs(output_dir, exist_ok=True)

    # Cargar transcripción
    print("Cargando transcripcion...")
    segments_by_speaker = load_transcription_segments(transcription_file)

    print(f"Encontrados {len(segments_by_speaker)} speakers")
    print()

    results = {}

    for speaker in sorted(segments_by_speaker.keys()):
        segments = segments_by_speaker[speaker]
        print("="*80)
        print(f"IDENTIFICANDO: Speaker {speaker}")
        print("="*80)
        print(f"Total segmentos: {len(segments)}")

        # Seleccionar mejores segmentos
        best_segments = select_best_segments(segments, max_segments=2)
        print(f"Segmentos seleccionados: {len(best_segments)}")
        print()

        result = None
        identified_name = None

        for attempt, segment in enumerate(best_segments, 1):
            duration = segment['end'] - segment['start']
            mid_point = (segment['start'] + segment['end']) / 2

            hours = int(mid_point // 3600)
            minutes = int((mid_point % 3600) // 60)
            seconds = int(mid_point % 60)

            print(f"Intento {attempt}/{len(best_segments)}")
            print(f"  Timestamp: {minutes:02d}:{seconds:02d} (total: {mid_point:.1f}s)")
            print(f"  Duracion segmento: {duration:.1f}s")
            print(f"  Texto: {segment['text'][:80]}...")
            print()

            # Extraer screenshot
            screenshot_file = os.path.join(
                output_dir,
                f"Speaker_{speaker}_attempt{attempt}_{int(mid_point)}s_{minutes:02d}m{seconds:02d}s.jpg"
            )

            screenshot_path = extract_screenshot(video_file, mid_point, screenshot_file)

            if not screenshot_path:
                print(f"  X Error extrayendo screenshot")
                continue

            print(f"  OK Screenshot guardado")

            # Identificar con GPT-4 Vision
            print(f"  Analizando con GPT-4 Vision...")
            identification = identify_active_speaker(
                client,
                screenshot_path,
                segment['text'],
                name_mapping
            )

            if not identification:
                print(f"  X Error en analisis")
                continue

            # VALIDACION: Si el reasoning menciona 2+ personas, forzar confidence a "low"
            reasoning_lower = identification.reasoning.lower()
            if any(phrase in reasoning_lower for phrase in ['2 personas', '3 personas', 'dos personas', 'tres personas', 'múltiples', 'multiples', 'ambos', 'both']):
                if identification.confidence != 'low':
                    print(f"  ! CORRECCION: Reasoning menciona multiples personas, forzando confidence a 'low'")
                    identification.confidence = 'low'

            # Resolver nombre usando mapeo
            resolved_name = identification.speaking_person_name

            if identification.speaking_person_initials and not resolved_name:
                # Intentar resolver con mapeo
                initials = identification.speaking_person_initials
                if initials in name_mapping.get('initials_to_name', {}):
                    resolved_name = name_mapping['initials_to_name'][initials]
                    print(f"  OK Iniciales '{initials}' mapeadas a: {resolved_name}")

            result = {
                'speaker_label': speaker,
                'identified_name': resolved_name,
                'initials_found': identification.speaking_person_initials,
                'confidence': identification.confidence,
                'number_of_people_detected': identification.number_of_people_detected,
                'visual_indicators': identification.visual_indicators,
                'reasoning': identification.reasoning,
                'attempts': attempt,
                'screenshot': screenshot_file,
                'timestamp_seconds': mid_point,
                'timestamp_mmss': f"{minutes:02d}:{seconds:02d}",
                'segment_duration': duration
            }

            print(f"  Personas detectadas: {identification.number_of_people_detected}")
            print(f"  Nombre: {resolved_name or 'No identificado'}")
            print(f"  Iniciales: {identification.speaking_person_initials or 'N/A'}")
            print(f"  Confianza: {identification.confidence}")
            print(f"  Indicadores: {', '.join(identification.visual_indicators)}")

            # Verificar si necesitamos otro intento
            if identification.confidence == 'low':
                print(f"  ! Confianza baja (posiblemente multiples personas hablando)")
                if attempt < len(best_segments):
                    print(f"  -> Intentando con siguiente segmento...")
                    print()
                    continue
                else:
                    print(f"  -> No hay mas segmentos, usando este resultado")

            print()

            # Si tenemos alta confianza, no intentar más
            if identification.confidence == 'high' and resolved_name:
                identified_name = resolved_name
                break

        results[speaker] = result
        print()

    return results

def save_results(results, output_file="speaker_identifications.json"):
    """Guarda resultados en archivo JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Resultados guardados en: {output_file}")

def print_summary(results):
    """Imprime resumen de resultados"""
    print()
    print("="*80)
    print("RESUMEN DE IDENTIFICACIONES")
    print("="*80)
    print()

    identified = 0
    for speaker, result in sorted(results.items()):
        if result and result.get('identified_name'):
            identified += 1
            print(f"Speaker {speaker:2s} -> {result['identified_name']:30s} (confianza: {result['confidence']})")
        else:
            print(f"Speaker {speaker:2s} -> NO IDENTIFICADO")

    print()
    print(f"Total identificados: {identified}/{len(results)}")

if __name__ == "__main__":
    # Configuración
    video_file = "G:\\personal\\transcription-project\\Recording 2025-10-27 150252.mp4"
    transcription_file = "G:\\personal\\transcription-project\\transcription_output_old.txt"
    name_mapping_file = "G:\\personal\\transcription-project\\name_mapping.json"

    # Cargar mapeo
    print("Cargando mapeo de nombres...")
    name_mapping = load_name_mapping(name_mapping_file)

    if not name_mapping:
        print("ERROR: Debes ejecutar create_name_mapping.py primero")
        exit(1)

    print(f"Mapeo cargado: {len(name_mapping['all_names'])} participantes conocidos")
    print()

    # Identificar speakers
    results = identify_all_speakers(video_file, transcription_file, name_mapping)

    # Guardar resultados
    save_results(results)

    # Imprimir resumen
    print_summary(results)
