"""Grafana Cloud client for sending metrics."""

import logging
import time
import base64
import snappy
from typing import List, Dict, Any
from fastapi import HTTPException
import httpx

from ...config import Config
from ...models import NuonWebhook
from ..utils import extract_metadata

logger = logging.getLogger(__name__)


class GrafanaClient:
    """Client for sending metrics to Grafana Cloud Prometheus."""

    def __init__(self):
        """Initialize the Grafana client with API credentials."""
        self.metrics_url = Config.GRAFANA_METRICS_URL
        self.instance_id = Config.GRAFANA_INSTANCE_ID
        self.api_token = Config.GRAFANA_API_TOKEN

    # BASE INTEGRATION INTERFACE
    async def send(self, webhook: NuonWebhook, event_type: str) -> bool:
        """
        Send webhook to Grafana (implements BaseIntegration interface).
        
        Extracts metrics from webhook and sends to Grafana Cloud.
        Works automatically for all webhook types.
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Not used (kept for interface compatibility)
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # Extract metrics and labels
        metrics = self._extract_metrics(webhook)
        labels = self._build_labels(webhook)
        timestamp = int(time.time())
        
        # Send to Grafana
        return await self._send_to_grafana(metrics, labels, timestamp)

    # METRICS EXTRACTION
    def _extract_metrics(self, webhook: NuonWebhook) -> List[Dict[str, Any]]:
        """
        Extract numeric metrics from webhook.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            List of metric dictionaries with name and value
        """
        metrics = []
        
        # Always send count metric
        metrics.append({
            "name": "nuon_webhook_count",
            "value": 1.0
        })
        
        # Add duration metric if available
        if webhook.data.outcome and webhook.data.outcome.duration_ms is not None:
            metrics.append({
                "name": "nuon_webhook_duration_ms",
                "value": float(webhook.data.outcome.duration_ms)
            })
        
        # Add success metric if terminal state
        if webhook.data.outcome and webhook.data.outcome.status:
            success_value = 1.0 if webhook.data.outcome.status == "succeeded" else 0.0
            metrics.append({
                "name": "nuon_webhook_success",
                "value": success_value
            })
        
        return metrics

    # LABELS BUILDER
    def _build_labels(self, webhook: NuonWebhook) -> Dict[str, str]:
        """
        Build labels (Grafana's version of tags) from webhook.
        
        Uses shared metadata extraction, returns as-is (dict format)
        which is what Grafana expects.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            Dictionary of label key-value pairs
        """
        # Extract metadata using shared helper (already in dict format for Grafana)
        return extract_metadata(webhook)

    # PROTOBUF MESSAGE BUILDER
    def _build_remote_write_request(self, metrics: List[Dict[str, Any]], labels: Dict[str, str], timestamp: int) -> bytes:
        """
        Build Prometheus Remote Write protobuf message.
        
        Uses simplified protobuf construction following Prometheus spec.
        
        Args:
            metrics: List of metric dictionaries
            labels: Label key-value pairs
            timestamp: Unix timestamp (seconds)
            
        Returns:
            Protobuf-encoded bytes
        """
        from google.protobuf import text_format
        from google.protobuf.message import Message
        
        # Build time series for each metric
        timeseries = []
        timestamp_ms = timestamp * 1000  # Convert to milliseconds
        
        for metric in metrics:
            # Build labels for this metric (metric name + common labels)
            metric_labels = [{"name": "__name__", "value": metric["name"]}]
            for k, v in labels.items():
                metric_labels.append({"name": k, "value": v})
            
            # Build sample (timestamp + value)
            sample = {"value": metric["value"], "timestamp": timestamp_ms}
            
            # Build time series
            timeseries.append({
                "labels": metric_labels,
                "samples": [sample]
            })
        
        # Build write request
        write_request = {"timeseries": timeseries}
        
        # Convert to protobuf bytes using manual encoding
        # This is a simplified protobuf encoding for Remote Write format
        return self._encode_protobuf(write_request)
    
    def _encode_protobuf(self, data: dict) -> bytes:
        """
        Manually encode data to Prometheus Remote Write protobuf format.
        
        This implements the minimal protobuf encoding needed for Remote Write.
        
        Args:
            data: Dictionary with timeseries data
            
        Returns:
            Protobuf-encoded bytes
        """
        # For now, use a simple encoding approach
        # We'll encode the timeseries data following the Prometheus protobuf schema
        
        output = bytearray()
        
        for ts in data["timeseries"]:
            # Encode each timeseries
            ts_bytes = self._encode_timeseries(ts)
            # Field 1 is repeated TimeSeries (wire type 2 = length-delimited)
            output.append(0x0a)  # Field 1, wire type 2
            output.extend(self._encode_varint(len(ts_bytes)))
            output.extend(ts_bytes)
        
        return bytes(output)
    
    def _encode_timeseries(self, ts: dict) -> bytes:
        """Encode a single timeseries to protobuf."""
        output = bytearray()
        
        # Encode labels (field 1)
        for label in ts["labels"]:
            label_bytes = self._encode_label(label)
            output.append(0x0a)  # Field 1, wire type 2
            output.extend(self._encode_varint(len(label_bytes)))
            output.extend(label_bytes)
        
        # Encode samples (field 2)
        for sample in ts["samples"]:
            sample_bytes = self._encode_sample(sample)
            output.append(0x12)  # Field 2, wire type 2
            output.extend(self._encode_varint(len(sample_bytes)))
            output.extend(sample_bytes)
        
        return bytes(output)
    
    def _encode_label(self, label: dict) -> bytes:
        """Encode a label to protobuf."""
        output = bytearray()
        
        # Name (field 1, string)
        name_bytes = label["name"].encode("utf-8")
        output.append(0x0a)  # Field 1, wire type 2
        output.extend(self._encode_varint(len(name_bytes)))
        output.extend(name_bytes)
        
        # Value (field 2, string)
        value_bytes = label["value"].encode("utf-8")
        output.append(0x12)  # Field 2, wire type 2
        output.extend(self._encode_varint(len(value_bytes)))
        output.extend(value_bytes)
        
        return bytes(output)
    
    def _encode_sample(self, sample: dict) -> bytes:
        """Encode a sample to protobuf."""
        output = bytearray()
        
        # Value (field 1, double)
        import struct
        output.append(0x09)  # Field 1, wire type 1 (64-bit)
        output.extend(struct.pack('<d', sample["value"]))
        
        # Timestamp (field 2, int64)
        output.append(0x10)  # Field 2, wire type 0 (varint)
        output.extend(self._encode_varint(sample["timestamp"]))
        
        return bytes(output)
    
    def _encode_varint(self, value: int) -> bytes:
        """Encode an integer as a protobuf varint."""
        output = bytearray()
        while value > 127:
            output.append((value & 0x7f) | 0x80)
            value >>= 7
        output.append(value & 0x7f)
        return bytes(output)

    # SEND TO GRAFANA
    async def _send_to_grafana(self, metrics: List[Dict[str, Any]], labels: Dict[str, str], timestamp: int) -> bool:
        """
        Send metrics to Grafana Cloud Prometheus endpoint.
        
        Uses Prometheus Remote Write format (Protobuf + Snappy).
        
        Args:
            metrics: List of metric dictionaries
            labels: Label key-value pairs
            timestamp: Unix timestamp
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # Build protobuf message
        protobuf_data = self._build_remote_write_request(metrics, labels, timestamp)
        
        # Compress with Snappy
        compressed_data = snappy.compress(protobuf_data)
        
        # Build Basic Auth header (base64-encoded)
        auth_string = f"{self.instance_id}:{self.api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.metrics_url,
                    content=compressed_data,
                    headers={
                        "Authorization": f"Basic {auth_b64}",
                        "Content-Encoding": "snappy",
                        "Content-Type": "application/x-protobuf",
                        "X-Prometheus-Remote-Write-Version": "0.1.0"
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully sent {len(metrics)} metrics to Grafana")
                    return True
                else:
                    logger.error(f"Grafana API returned {response.status_code}: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to send metrics to Grafana: {response.status_code}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send metrics to Grafana: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send metrics to Grafana: {str(e)}"
            )
