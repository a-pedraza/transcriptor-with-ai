"""
Genera reporte de verificación desde los resultados de identificación
"""

import json
import os

def create_html_report(results, output_file="verification_report_new.html"):
    """Crea reporte HTML interactivo"""

    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Verificación de Identificaciones - Nuevo Método</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .speaker { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .speaker-header { background: #2c3e50; color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px; }
        .attempt { margin: 15px 0; padding: 15px; background: #ecf0f1; border-left: 4px solid #3498db; }
        .screenshot { max-width: 800px; border: 2px solid #ddd; border-radius: 4px; margin: 10px 0; }
        .info { margin: 5px 0; }
        .label { font-weight: bold; color: #2c3e50; }
        .confidence-high { color: #27ae60; font-weight: bold; }
        .confidence-medium { color: #f39c12; font-weight: bold; }
        .confidence-low { color: #e74c3c; font-weight: bold; }
        .indicators { background: #e8f5e9; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .method-note { background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>🔍 Verificación de Identificaciones - NUEVO MÉTODO</h1>

    <div class="method-note">
        <strong>MÉTODO USADO:</strong>
        <ul>
            <li>✅ Se creó mapeo inicial de participantes (inicio + final del video)</li>
            <li>✅ Se buscó <strong>BORDE RESALTADO</strong> en avatares (indicador de quién habla)</li>
            <li>❌ Se IGNORÓ contenido de pantalla compartida</li>
            <li>✅ Iniciales (KB, DM, etc.) se resolvieron usando el mapeo</li>
        </ul>
    </div>
"""

    # Ordenar speakers
    sorted_speakers = sorted(results.items(), key=lambda x: x[0])

    for speaker, data in sorted_speakers:
        if not data:
            continue

        confidence_class = f"confidence-{data['confidence']}"

        num_people = data.get('number_of_people_detected', '?')
        html += f"""
    <div class="speaker">
        <div class="speaker-header">
            <h2>Speaker {speaker}</h2>
            <div class="info">Personas detectadas: <strong>{num_people}</strong></div>
            <div class="info">Identificado como: <strong>{data.get('identified_name', 'No identificado')}</strong></div>
            <div class="info">Iniciales encontradas: <strong>{data.get('initials_found', 'N/A')}</strong></div>
            <div class="info">Confianza: <span class="{confidence_class}">{data['confidence'].upper()}</span></div>
        </div>
"""

        # Indicators
        if data.get('visual_indicators'):
            html += """
        <div class="indicators">
            <div class="label">Indicadores visuales encontrados:</div>
            <ul>
"""
            for indicator in data['visual_indicators']:
                html += f"                <li>{indicator}</li>\n"
            html += """            </ul>
        </div>
"""

        # Reasoning
        if data.get('reasoning'):
            html += f"""
        <div class="info">
            <span class="label">Razonamiento:</span> {data['reasoning']}
        </div>
"""

        # Screenshot
        screenshot = data.get('screenshot', '')
        if screenshot and os.path.exists(screenshot):
            # Get relative path
            screenshot_rel = os.path.basename(screenshot)
            screenshot_dir = os.path.basename(os.path.dirname(screenshot))
            screenshot_path = f"{screenshot_dir}/{screenshot_rel}"

            # Get timestamp info
            timestamp_mmss = data.get('timestamp_mmss', 'N/A')
            timestamp_seconds = data.get('timestamp_seconds', 0)
            segment_duration = data.get('segment_duration', 0)

            html += f"""
        <div class="attempt">
            <div class="info"><span class="label">Timestamp:</span> <strong>{timestamp_mmss}</strong> ({timestamp_seconds:.1f}s total)</div>
            <div class="info"><span class="label">Duración del segmento:</span> {segment_duration:.1f}s</div>
            <div class="info"><span class="label">Screenshot:</span> {screenshot_path}</div>
            <img src="{screenshot_path}" class="screenshot" alt="Screenshot">
        </div>
"""

        html += """
    </div>
"""

    html += """
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Reporte HTML creado: {output_file}")

def create_text_report(results, output_file="verification_report_new.txt"):
    """Crea reporte de texto"""

    lines = []
    lines.append("="*80)
    lines.append("REPORTE DE VERIFICACION - NUEVO METODO")
    lines.append("="*80)
    lines.append("")
    lines.append("METODO USADO:")
    lines.append("- Mapeo inicial de participantes (inicio + final del video)")
    lines.append("- Busqueda de BORDE RESALTADO en avatares (quien habla)")
    lines.append("- IGNORA contenido de pantalla compartida")
    lines.append("- Iniciales resueltas con mapeo")
    lines.append("")
    lines.append("="*80)
    lines.append("")

    for speaker in sorted(results.keys()):
        data = results[speaker]
        if not data:
            continue

        lines.append(f"SPEAKER {speaker}")
        lines.append("-"*80)
        lines.append(f"Personas detectadas: {data.get('number_of_people_detected', '?')}")
        lines.append(f"Identificado como: {data.get('identified_name', 'No identificado')}")
        lines.append(f"Iniciales encontradas: {data.get('initials_found', 'N/A')}")
        lines.append(f"Confianza: {data['confidence']}")
        lines.append("")

        if data.get('visual_indicators'):
            lines.append("  Indicadores visuales:")
            for ind in data['visual_indicators']:
                lines.append(f"    - {ind}")
            lines.append("")

        if data.get('reasoning'):
            lines.append(f"  Razonamiento: {data['reasoning']}")
            lines.append("")

        if data.get('screenshot'):
            timestamp_mmss = data.get('timestamp_mmss', 'N/A')
            timestamp_seconds = data.get('timestamp_seconds', 0)
            segment_duration = data.get('segment_duration', 0)

            lines.append(f"  Timestamp: {timestamp_mmss} ({timestamp_seconds:.1f}s total)")
            lines.append(f"  Duracion del segmento: {segment_duration:.1f}s")
            lines.append(f"  Screenshot: {data['screenshot']}")
            lines.append("")

        lines.append("")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Reporte de texto creado: {output_file}")

if __name__ == "__main__":
    # Cargar resultados
    results_file = "speaker_identifications.json"

    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # Crear reportes
    create_html_report(results)
    create_text_report(results)

    print("")
    print("="*80)
    print("LISTO!")
    print("="*80)
    print("Abre 'verification_report_new.html' en tu navegador para revisar")
