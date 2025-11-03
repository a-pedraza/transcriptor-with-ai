#!/usr/bin/env python3
"""
Script para analizar la consistencia de hablantes entre chunks
"""

# Límites de los chunks (en segundos)
CHUNK_BOUNDARIES = [0, 1200, 2400, 3600, 3624.62]

def analyze_transcription(file_path):
    """Analiza la distribución de hablantes por chunk"""

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Analizar cada segmento
    chunks_data = {
        "Chunk 1 (0-20min)": [],
        "Chunk 2 (20-40min)": [],
        "Chunk 3 (40-60min)": [],
        "Chunk 4 (60-60.4min)": []
    }

    chunk_names = list(chunks_data.keys())

    for line in lines:
        if line.strip() and line.startswith('['):
            # Extraer timestamp y speaker
            try:
                start_str = line.split('[')[1].split('s')[0]
                start_time = float(start_str)
                speaker = line.split(']')[1].split(':')[0].strip()

                # Determinar a qué chunk pertenece
                chunk_idx = 0
                for i in range(len(CHUNK_BOUNDARIES) - 1):
                    if CHUNK_BOUNDARIES[i] <= start_time < CHUNK_BOUNDARIES[i + 1]:
                        chunk_idx = i
                        break

                chunks_data[chunk_names[chunk_idx]].append({
                    'time': start_time,
                    'speaker': speaker
                })
            except:
                continue

    # Imprimir análisis
    print("=" * 70)
    print("ANÁLISIS DE CONSISTENCIA DE HABLANTES")
    print("=" * 70)

    for chunk_name, segments in chunks_data.items():
        if not segments:
            continue

        speakers = {}
        for seg in segments:
            speaker = seg['speaker']
            if speaker not in speakers:
                speakers[speaker] = 0
            speakers[speaker] += 1

        total_segments = len(segments)
        print(f"\n{chunk_name}:")
        print(f"  Total segmentos: {total_segments}")
        print(f"  Hablantes detectados: {list(speakers.keys())}")

        for speaker, count in sorted(speakers.items()):
            percentage = (count / total_segments) * 100
            print(f"    {speaker}: {count} segmentos ({percentage:.1f}%)")

        # Mostrar primeros 3 segmentos del chunk
        print(f"  Primeros 3 segmentos:")
        for seg in segments[:3]:
            print(f"    [{seg['time']:.2f}s] {seg['speaker']}")

    print("\n" + "=" * 70)
    print("OBSERVACIONES:")
    print("=" * 70)
    print("\n⚠️  IMPORTANTE: Los labels de hablantes (A, B, C, etc.) pueden NO ser")
    print("consistentes entre chunks diferentes.")
    print("\nPor ejemplo:")
    print("  - 'Speaker A' en Chunk 1 podría ser 'Speaker B' en Chunk 2")
    print("  - Cada chunk se procesó independientemente")
    print("\n💡 Para resolver esto:")
    print("  1. Proporcionar clips de referencia de hablantes conocidos")
    print("  2. Usar post-procesamiento con análisis de voz")
    print("  3. Revisar manualmente las transiciones entre chunks")
    print("=" * 70)


if __name__ == "__main__":
    analyze_transcription("transcription_output.txt")
