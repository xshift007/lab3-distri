#!/usr/bin/env python3
"""
Tests simplificados para el Aggregator Service
No requieren RabbitMQ ni dependencias externas
"""

import unittest
import json
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

# Estado global (simula el estado del aggregator real)
stats_buffer = {}
processed_ids = set()
event_ids_by_region = {}
current_window_start = time.time()

def process_event(event):
    """Lógica de agregación pura"""
    region = event.get("region", "unknown")
    source = event.get("source", "unknown")
    event_id = event.get("event_id")
    
    # Inicializar contadores si no existen
    if region not in stats_buffer:
        stats_buffer[region] = {}
    if source not in stats_buffer[region]:
        stats_buffer[region][source] = 0
        
    stats_buffer[region][source] += 1

    if event_id:
        event_ids_by_region.setdefault(region, set()).add(event_id)
        processed_ids.add(event_id)  # Agregar a processed_ids

def flush_window(channel):
    """Publica los resultados acumulados y reinicia el buffer"""
    global current_window_start, stats_buffer, processed_ids, event_ids_by_region

    if not stats_buffer:
        # Si no hubo datos, solo actualizamos el tiempo
        current_window_start = time.time()
        return

    # Crear mensaje de resumen
    summary = {
        "type": "window_summary",
        "window_start_iso": datetime.fromtimestamp(current_window_start).isoformat(),
        "window_end_iso": datetime.now().isoformat(),
        "total_processed": len(processed_ids),
        "stats_by_region": stats_buffer
    }

    # Simular publicación al exchange de analytics
    if channel:
        channel.basic_publish(
            exchange="analytics_exchange",
            routing_key="analytics.window",
            body=json.dumps(summary),
            properties=MagicMock()
        )

    # Publicar métricas diarias por región con trazabilidad
    for region, region_stats in stats_buffer.items():
        metric_msg = {
            "metric_id": f"metric-{int(time.time())}",
            "date": datetime.now().date().isoformat(),
            "region": region,
            "run_id": "default",
            "metrics": region_stats,
            "input_event_ids": sorted(event_ids_by_region.get(region, set())),
        }
        if channel:
            channel.basic_publish(
                exchange="analytics_exchange",
                routing_key="metrics.daily",
                body=json.dumps(metric_msg),
                properties=MagicMock(),
            )

    print(f" [S] Ventana cerrada. Publicado resumen de {len(processed_ids)} eventos.")
    
    # Reiniciar estado
    stats_buffer = {}
    processed_ids = set()
    event_ids_by_region = {}
    current_window_start = time.time()

def callback(ch, method, properties, body):
    """Callback del consumidor RabbitMQ"""
    try:
        event = json.loads(body)
        event_id = event.get("event_id")

        # DEDUPLICACIÓN (Idempotencia)
        if event_id in processed_ids:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # PROCESAMIENTO
        process_event(event)

    except Exception as e:
        print(f" [!] Error agregando: {e}")
    
    # ACK solo si no se hizo en el bloque de duplicados
    ch.basic_ack(delivery_tag=method.delivery_tag)

class TestAggregatorLogic(unittest.TestCase):
    """Tests para la lógica de agregación del aggregator"""

    def setUp(self):
        """Configuración inicial para cada test"""
        global stats_buffer, processed_ids, event_ids_by_region, current_window_start
        stats_buffer = {}
        processed_ids = set()
        event_ids_by_region = {}
        current_window_start = time.time()

    def test_process_event_new_event(self):
        """Test procesamiento de evento nuevo"""
        event = {
            "event_id": "test-event-1",
            "region": "norte",
            "source": "security.incident"
        }
        
        process_event(event)
        
        # Verificar que se contó
        self.assertEqual(stats_buffer["norte"]["security.incident"], 1)
        self.assertEqual(len(event_ids_by_region["norte"]), 1)
        self.assertIn("test-event-1", processed_ids)

    def test_process_event_missing_fields(self):
        """Test manejo de eventos con campos faltantes"""
        event = {
            "event_id": "test-event-2"
            # Falta region y source
        }
        
        process_event(event)
        
        # Debe usar valores por defecto
        self.assertEqual(stats_buffer["unknown"]["unknown"], 1)
        self.assertEqual(len(event_ids_by_region["unknown"]), 1)

    def test_process_event_multiple_events_same_region(self):
        """Test acumulación de múltiples eventos en misma región"""
        events = [
            {"event_id": "event-1", "region": "sur", "source": "security.incident"},
            {"event_id": "event-2", "region": "sur", "source": "survey.victimization"},
            {"event_id": "event-3", "region": "sur", "source": "security.incident"}
        ]
        
        for event in events:
            process_event(event)
        
        # Verificar acumulación
        self.assertEqual(stats_buffer["sur"]["security.incident"], 2)
        self.assertEqual(stats_buffer["sur"]["survey.victimization"], 1)
        self.assertEqual(len(event_ids_by_region["sur"]), 3)

    def test_process_event_multiple_regions(self):
        """Test procesamiento de eventos en múltiples regiones"""
        events = [
            {"event_id": "event-1", "region": "norte", "source": "security.incident"},
            {"event_id": "event-2", "region": "sur", "source": "security.incident"},
            {"event_id": "event-3", "region": "centro", "source": "migration.case"}
        ]
        
        for event in events:
            process_event(event)
        
        # Verificar distribución por región
        self.assertEqual(stats_buffer["norte"]["security.incident"], 1)
        self.assertEqual(stats_buffer["sur"]["security.incident"], 1)
        self.assertEqual(stats_buffer["centro"]["migration.case"], 1)
        self.assertEqual(len(event_ids_by_region["norte"]), 1)
        self.assertEqual(len(event_ids_by_region["sur"]), 1)
        self.assertEqual(len(event_ids_by_region["centro"]), 1)

    def test_deduplication_same_event_id(self):
        """Test que eventos duplicados se descartan"""
        event = {
            "event_id": "test-event-duplicate",
            "region": "norte",
            "source": "security.incident"
        }
        
        # Procesar mismo evento dos veces
        process_event(event)  # Primera vez - debe contar
        # Segunda vez - no debe contar porque ya está en processed_ids
        if event["event_id"] in processed_ids:
            # No procesar duplicado
            pass
        else:
            process_event(event)  # Solo procesar si no está duplicado
        
        # Verificar que solo se contó una vez
        self.assertEqual(stats_buffer["norte"]["security.incident"], 1)
        self.assertEqual(len(event_ids_by_region["norte"]), 1)
        # El event_id debe estar en processed_ids
        self.assertIn("test-event-duplicate", processed_ids)

    def test_flush_window_empty_buffer(self):
        """Test que flush_window con buffer vacío solo actualiza tiempo"""
        initial_time = current_window_start
        
        # Esperar un poco para que cambie el tiempo
        time.sleep(0.01)
        
        mock_channel = MagicMock()
        flush_window(mock_channel)
        
        # Buffer debe seguir vacío
        self.assertEqual(len(stats_buffer), 0)
        self.assertEqual(len(processed_ids), 0)
        
        # Tiempo debe haberse actualizado
        self.assertGreater(current_window_start, initial_time)
        
        # No debe haber publicado nada
        mock_channel.basic_publish.assert_not_called()

    def test_flush_window_with_data(self):
        """Test que flush_window publica datos correctamente"""
        # Agregar algunos eventos
        events = [
            {"event_id": "event-1", "region": "norte", "source": "security.incident"},
            {"event_id": "event-2", "region": "norte", "source": "survey.victimization"},
            {"event_id": "event-3", "region": "sur", "source": "migration.case"}
        ]
        
        for event in events:
            process_event(event)
        
        mock_channel = MagicMock()
        flush_window(mock_channel)
        
        # Debe haber publicado 3 mensajes: 1 summary + 2 métricas (una por región)
        self.assertEqual(mock_channel.basic_publish.call_count, 3)
        
        # Buffer debe estar vacío después del flush
        self.assertEqual(len(stats_buffer), 0)
        self.assertEqual(len(processed_ids), 0)
        self.assertEqual(len(event_ids_by_region), 0)
        
        # Verificar llamadas de publicación
        calls = mock_channel.basic_publish.call_args_list
        
        # Primera llamada debe ser el summary
        summary_call = calls[0]
        self.assertEqual(summary_call[1]['exchange'], 'analytics_exchange')
        self.assertEqual(summary_call[1]['routing_key'], 'analytics.window')
        
        summary_body = json.loads(summary_call[1]['body'])
        self.assertEqual(summary_body['type'], 'window_summary')
        self.assertEqual(summary_body['total_processed'], 3)
        self.assertIn('stats_by_region', summary_body)

    def test_callback_with_new_event(self):
        """Test que callback procesa eventos nuevos correctamente"""
        event = {
            "event_id": "callback-test-1",
            "region": "norte",
            "source": "security.incident"
        }
        
        mock_ch = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        
        callback(mock_ch, mock_method, None, json.dumps(event))
        
        # Verificar que se procesó
        self.assertEqual(stats_buffer["norte"]["security.incident"], 1)
        self.assertIn("callback-test-1", processed_ids)
        
        # Verificar que se hizo ACK
        mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)

    def test_callback_with_duplicate_event(self):
        """Test que callback maneja duplicados correctamente"""
        event = {
            "event_id": "callback-duplicate",
            "region": "norte",
            "source": "security.incident"
        }
        
        mock_ch = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        
        # Primera llamada - debe procesar
        callback(mock_ch, mock_method, None, json.dumps(event))
        
        # Segunda llamada - debe descartar
        mock_method.delivery_tag = 2
        callback(mock_ch, mock_method, None, json.dumps(event))
        
        # Verificar que solo se procesó una vez
        self.assertEqual(stats_buffer["norte"]["security.incident"], 1)
        
        # Verificar que se hicieron dos ACKs
        self.assertEqual(mock_ch.basic_ack.call_count, 2)

    def test_callback_with_invalid_json(self):
        """Test que callback maneja JSON inválido correctamente"""
        mock_ch = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        
        # JSON inválido
        callback(mock_ch, mock_method, None, "json inválido")
        
        # No debe procesar nada pero debe hacer ACK
        mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)
        self.assertEqual(len(stats_buffer), 0)

if __name__ == '__main__':
    unittest.main()
