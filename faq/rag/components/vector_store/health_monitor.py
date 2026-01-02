"""
Vector Store Health Monitor

Provides health monitoring and diagnostics for vector stores,
including Qdrant connectivity, performance metrics, and fallback status.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from threading import Lock
from dataclasses import dataclass, asdict

from faq.rag.interfaces.base import VectorStoreInterface
from .vector_store_factory import VectorStoreFactory


logger = logging.getLogger(__name__)


@dataclass
class HealthMetric:
    """Health metric data structure."""
    name: str
    value: float
    threshold: float
    status: str  # 'healthy', 'warning', 'critical'
    timestamp: datetime
    unit: str = ""
    description: str = ""


@dataclass
class HealthReport:
    """Comprehensive health report."""
    overall_status: str  # 'healthy', 'degraded', 'unhealthy'
    timestamp: datetime
    store_type: str
    metrics: List[HealthMetric]
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]


class VectorStoreHealthMonitor:
    """
    Monitors health and performance of vector stores.
    
    Features:
    - Real-time health monitoring
    - Performance metrics tracking
    - Threshold-based alerting
    - Historical health data
    - Fallback status monitoring
    """
    
    def __init__(self, 
                 check_interval: int = 60,
                 history_retention_hours: int = 24):
        """
        Initialize health monitor.
        
        Args:
            check_interval: Health check interval in seconds
            history_retention_hours: How long to retain health history
        """
        self.check_interval = check_interval
        self.history_retention = timedelta(hours=history_retention_hours)
        self._lock = Lock()
        
        # Health history
        self._health_history: List[HealthReport] = []
        self._last_check: Optional[datetime] = None
        
        # Thresholds
        self.thresholds = {
            'response_time_ms': 1000.0,  # 1 second
            'error_rate': 0.05,  # 5%
            'connection_failures': 3,
            'fallback_usage_rate': 0.1  # 10%
        }
        
        logger.info("VectorStoreHealthMonitor initialized")
    
    def check_health(self, vector_store: VectorStoreInterface) -> HealthReport:
        """
        Perform comprehensive health check on vector store.
        
        Args:
            vector_store: Vector store instance to check
            
        Returns:
            HealthReport with detailed health information
        """
        with self._lock:
            start_time = time.time()
            timestamp = datetime.now()
            
            metrics = []
            errors = []
            warnings = []
            recommendations = []
            
            # Determine store type
            store_type = self._get_store_type(vector_store)
            
            try:
                # Basic connectivity test
                connectivity_metric = self._check_connectivity(vector_store)
                metrics.append(connectivity_metric)
                
                if connectivity_metric.status == 'critical':
                    errors.append("Vector store connectivity failed")
                
                # Performance metrics
                performance_metrics = self._check_performance(vector_store)
                metrics.extend(performance_metrics)
                
                # Storage metrics
                storage_metrics = self._check_storage(vector_store)
                metrics.extend(storage_metrics)
                
                # Qdrant-specific checks
                if store_type == 'qdrant':
                    qdrant_metrics = self._check_qdrant_specific(vector_store)
                    metrics.extend(qdrant_metrics)
                
                # Fallback status
                fallback_metrics = self._check_fallback_status(vector_store)
                metrics.extend(fallback_metrics)
                
                # Generate recommendations
                recommendations = self._generate_recommendations(metrics, store_type)
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                errors.append(f"Health check error: {str(e)}")
                
                # Create error metric
                error_metric = HealthMetric(
                    name="health_check_error",
                    value=1.0,
                    threshold=0.0,
                    status="critical",
                    timestamp=timestamp,
                    description=f"Health check failed: {str(e)}"
                )
                metrics.append(error_metric)
            
            # Determine overall status
            overall_status = self._determine_overall_status(metrics, errors)
            
            # Create health report
            report = HealthReport(
                overall_status=overall_status,
                timestamp=timestamp,
                store_type=store_type,
                metrics=metrics,
                errors=errors,
                warnings=warnings,
                recommendations=recommendations
            )
            
            # Store in history
            self._health_history.append(report)
            self._cleanup_history()
            self._last_check = timestamp
            
            check_duration = time.time() - start_time
            logger.debug(f"Health check completed in {check_duration:.3f}s - Status: {overall_status}")
            
            return report
    
    def _get_store_type(self, vector_store: VectorStoreInterface) -> str:
        """Determine the type of vector store."""
        class_name = vector_store.__class__.__name__
        
        if 'Qdrant' in class_name:
            return 'qdrant'
        elif 'VectorStore' in class_name:
            return 'local'
        else:
            return 'unknown'
    
    def _check_connectivity(self, vector_store: VectorStoreInterface) -> HealthMetric:
        """Check basic connectivity to vector store."""
        try:
            start_time = time.time()
            
            # Try to get stats (basic operation)
            stats = vector_store.get_vector_stats()
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Check if we got valid stats
            if isinstance(stats, dict) and 'total_vectors' in stats:
                status = 'healthy' if response_time < self.thresholds['response_time_ms'] else 'warning'
            else:
                status = 'warning'
                
            return HealthMetric(
                name="connectivity",
                value=response_time,
                threshold=self.thresholds['response_time_ms'],
                status=status,
                timestamp=datetime.now(),
                unit="ms",
                description="Basic connectivity and response time"
            )
            
        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            return HealthMetric(
                name="connectivity",
                value=0.0,
                threshold=self.thresholds['response_time_ms'],
                status="critical",
                timestamp=datetime.now(),
                unit="ms",
                description=f"Connectivity failed: {str(e)}"
            )
    
    def _check_performance(self, vector_store: VectorStoreInterface) -> List[HealthMetric]:
        """Check performance metrics."""
        metrics = []
        
        try:
            stats = vector_store.get_vector_stats()
            
            # Response time metric
            avg_search_time = stats.get('average_search_time', 0.0) * 1000  # Convert to ms
            
            response_time_metric = HealthMetric(
                name="average_search_time",
                value=avg_search_time,
                threshold=self.thresholds['response_time_ms'],
                status='healthy' if avg_search_time < self.thresholds['response_time_ms'] else 'warning',
                timestamp=datetime.now(),
                unit="ms",
                description="Average search response time"
            )
            metrics.append(response_time_metric)
            
            # Search count metric
            search_count = stats.get('search_count', 0)
            search_count_metric = HealthMetric(
                name="search_count",
                value=float(search_count),
                threshold=0.0,
                status='healthy',
                timestamp=datetime.now(),
                unit="count",
                description="Total number of searches performed"
            )
            metrics.append(search_count_metric)
            
        except Exception as e:
            logger.error(f"Performance check failed: {e}")
            error_metric = HealthMetric(
                name="performance_check_error",
                value=1.0,
                threshold=0.0,
                status="warning",
                timestamp=datetime.now(),
                description=f"Performance check failed: {str(e)}"
            )
            metrics.append(error_metric)
        
        return metrics
    
    def _check_storage(self, vector_store: VectorStoreInterface) -> List[HealthMetric]:
        """Check storage-related metrics."""
        metrics = []
        
        try:
            stats = vector_store.get_vector_stats()
            
            # Vector count metric
            total_vectors = stats.get('total_vectors', 0)
            vector_count_metric = HealthMetric(
                name="total_vectors",
                value=float(total_vectors),
                threshold=0.0,
                status='healthy' if total_vectors > 0 else 'warning',
                timestamp=datetime.now(),
                unit="count",
                description="Total number of stored vectors"
            )
            metrics.append(vector_count_metric)
            
            # Memory usage (if available)
            memory_usage = stats.get('memory_usage_mb', 0.0)
            if memory_usage > 0:
                memory_metric = HealthMetric(
                    name="memory_usage",
                    value=memory_usage,
                    threshold=1000.0,  # 1GB threshold
                    status='healthy' if memory_usage < 1000.0 else 'warning',
                    timestamp=datetime.now(),
                    unit="MB",
                    description="Memory usage of vector store"
                )
                metrics.append(memory_metric)
            
        except Exception as e:
            logger.error(f"Storage check failed: {e}")
            error_metric = HealthMetric(
                name="storage_check_error",
                value=1.0,
                threshold=0.0,
                status="warning",
                timestamp=datetime.now(),
                description=f"Storage check failed: {str(e)}"
            )
            metrics.append(error_metric)
        
        return metrics
    
    def _check_qdrant_specific(self, vector_store: VectorStoreInterface) -> List[HealthMetric]:
        """Check Qdrant-specific metrics."""
        metrics = []
        
        try:
            # Check if this is a Qdrant store
            if hasattr(vector_store, 'health_check'):
                qdrant_health = vector_store.health_check()
                
                # Qdrant availability
                qdrant_available = qdrant_health.get('qdrant_available', False)
                availability_metric = HealthMetric(
                    name="qdrant_availability",
                    value=1.0 if qdrant_available else 0.0,
                    threshold=1.0,
                    status='healthy' if qdrant_available else 'critical',
                    timestamp=datetime.now(),
                    description="Qdrant server availability"
                )
                metrics.append(availability_metric)
                
                # Collection status
                collection_exists = qdrant_health.get('collection_exists', False)
                collection_metric = HealthMetric(
                    name="collection_exists",
                    value=1.0 if collection_exists else 0.0,
                    threshold=1.0,
                    status='healthy' if collection_exists else 'warning',
                    timestamp=datetime.now(),
                    description="Qdrant collection existence"
                )
                metrics.append(collection_metric)
                
                # Connection errors
                connection_errors = qdrant_health.get('stats', {}).get('connection_errors', 0)
                error_metric = HealthMetric(
                    name="connection_errors",
                    value=float(connection_errors),
                    threshold=self.thresholds['connection_failures'],
                    status='healthy' if connection_errors < self.thresholds['connection_failures'] else 'warning',
                    timestamp=datetime.now(),
                    unit="count",
                    description="Number of connection errors"
                )
                metrics.append(error_metric)
                
        except Exception as e:
            logger.error(f"Qdrant-specific check failed: {e}")
            error_metric = HealthMetric(
                name="qdrant_check_error",
                value=1.0,
                threshold=0.0,
                status="warning",
                timestamp=datetime.now(),
                description=f"Qdrant check failed: {str(e)}"
            )
            metrics.append(error_metric)
        
        return metrics
    
    def _check_fallback_status(self, vector_store: VectorStoreInterface) -> List[HealthMetric]:
        """Check fallback usage and status."""
        metrics = []
        
        try:
            stats = vector_store.get_vector_stats()
            
            # Fallback usage
            fallback_usage = stats.get('fallback_usage', 0)
            total_operations = max(stats.get('search_count', 1), 1)  # Avoid division by zero
            fallback_rate = fallback_usage / total_operations
            
            fallback_metric = HealthMetric(
                name="fallback_usage_rate",
                value=fallback_rate,
                threshold=self.thresholds['fallback_usage_rate'],
                status='healthy' if fallback_rate < self.thresholds['fallback_usage_rate'] else 'warning',
                timestamp=datetime.now(),
                unit="ratio",
                description="Rate of fallback store usage"
            )
            metrics.append(fallback_metric)
            
            # Fallback availability
            fallback_available = stats.get('fallback_available', False)
            if isinstance(fallback_available, bool):
                availability_metric = HealthMetric(
                    name="fallback_availability",
                    value=1.0 if fallback_available else 0.0,
                    threshold=1.0,
                    status='healthy' if fallback_available else 'warning',
                    timestamp=datetime.now(),
                    description="Fallback store availability"
                )
                metrics.append(availability_metric)
            
        except Exception as e:
            logger.error(f"Fallback check failed: {e}")
            error_metric = HealthMetric(
                name="fallback_check_error",
                value=1.0,
                threshold=0.0,
                status="warning",
                timestamp=datetime.now(),
                description=f"Fallback check failed: {str(e)}"
            )
            metrics.append(error_metric)
        
        return metrics
    
    def _determine_overall_status(self, metrics: List[HealthMetric], errors: List[str]) -> str:
        """Determine overall health status from metrics and errors."""
        if errors:
            return 'unhealthy'
        
        critical_count = sum(1 for m in metrics if m.status == 'critical')
        warning_count = sum(1 for m in metrics if m.status == 'warning')
        
        if critical_count > 0:
            return 'unhealthy'
        elif warning_count > 0:
            return 'degraded'
        else:
            return 'healthy'
    
    def _generate_recommendations(self, metrics: List[HealthMetric], store_type: str) -> List[str]:
        """Generate recommendations based on health metrics."""
        recommendations = []
        
        # Check for high response times
        for metric in metrics:
            if metric.name == "average_search_time" and metric.status == 'warning':
                recommendations.append("Consider optimizing search performance or scaling vector store")
            
            if metric.name == "connectivity" and metric.status in ['warning', 'critical']:
                recommendations.append("Check network connectivity to vector store")
            
            if metric.name == "fallback_usage_rate" and metric.status == 'warning':
                recommendations.append("High fallback usage detected - investigate primary store issues")
            
            if metric.name == "total_vectors" and metric.value == 0:
                recommendations.append("No vectors found - ensure data has been ingested")
        
        # Store-specific recommendations
        if store_type == 'qdrant':
            qdrant_available = any(m.name == "qdrant_availability" and m.value == 1.0 for m in metrics)
            if not qdrant_available:
                recommendations.append("Qdrant server is unavailable - check server status and configuration")
        
        return recommendations
    
    def _cleanup_history(self) -> None:
        """Clean up old health history entries."""
        cutoff_time = datetime.now() - self.history_retention
        self._health_history = [
            report for report in self._health_history 
            if report.timestamp > cutoff_time
        ]
    
    def get_health_history(self, hours: int = 24) -> List[HealthReport]:
        """
        Get health history for the specified time period.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            List of health reports within the time period
        """
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return [
                report for report in self._health_history 
                if report.timestamp > cutoff_time
            ]
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current health status.
        
        Returns:
            Dictionary with health summary information
        """
        with self._lock:
            if not self._health_history:
                return {
                    'status': 'unknown',
                    'message': 'No health checks performed yet'
                }
            
            latest_report = self._health_history[-1]
            
            return {
                'status': latest_report.overall_status,
                'timestamp': latest_report.timestamp.isoformat(),
                'store_type': latest_report.store_type,
                'metrics_count': len(latest_report.metrics),
                'errors_count': len(latest_report.errors),
                'warnings_count': len(latest_report.warnings),
                'recommendations_count': len(latest_report.recommendations),
                'last_check_age_seconds': (datetime.now() - latest_report.timestamp).total_seconds()
            }
    
    def export_health_data(self) -> Dict[str, Any]:
        """
        Export all health data for analysis or backup.
        
        Returns:
            Dictionary with complete health monitoring data
        """
        with self._lock:
            return {
                'monitor_config': {
                    'check_interval': self.check_interval,
                    'history_retention_hours': self.history_retention.total_seconds() / 3600,
                    'thresholds': self.thresholds
                },
                'health_history': [
                    {
                        'overall_status': report.overall_status,
                        'timestamp': report.timestamp.isoformat(),
                        'store_type': report.store_type,
                        'metrics': [asdict(metric) for metric in report.metrics],
                        'errors': report.errors,
                        'warnings': report.warnings,
                        'recommendations': report.recommendations
                    }
                    for report in self._health_history
                ],
                'summary': self.get_health_summary()
            }