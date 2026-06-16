"""
Grafana dashboard JSON model for GNONE platform observability.
"""

GRAFANA_DASHBOARD = {
    "title": "GNONE — Content Manufacturing Platform",
    "version": 1,
    "timezone": "utc",
    "panels": [
        {
            "title": "Pipeline Latency (P50 / P95 / P99)",
            "type": "timeseries",
            "datasource": "Prometheus",
            "targets": [
                {
                    "expr": "histogram_quantile(0.50, rate(gnone_pipeline_latency_seconds_bucket[5m]))",
                    "legendFormat": "P50",
                },
                {
                    "expr": "histogram_quantile(0.95, rate(gnone_pipeline_latency_seconds_bucket[5m]))",
                    "legendFormat": "P95",
                },
                {
                    "expr": "histogram_quantile(0.99, rate(gnone_pipeline_latency_seconds_bucket[5m]))",
                    "legendFormat": "P99",
                },
            ],
        },
        {
            "title": "Requests & Error Rate",
            "type": "timeseries",
            "datasource": "Prometheus",
            "targets": [
                {"expr": "rate(gnone_requests_total[5m])", "legendFormat": "Requests"},
                {"expr": "rate(gnone_errors_total[5m])", "legendFormat": "Errors"},
            ],
        },
        {
            "title": "Critic Approval Rate",
            "type": "gauge",
            "datasource": "Prometheus",
            "targets": [
                {
                    "expr": "sum(rate(gnone_critic_cycles_total{result='approved'}[1h])) / sum(rate(gnone_critic_cycles_total[1h])) * 100",
                    "legendFormat": "Approval Rate %",
                },
            ],
        },
        {
            "title": "Content by Platform (Last 24h)",
            "type": "barchart",
            "datasource": "Prometheus",
            "targets": [
                {
                    "expr": "increase(gnone_content_pieces_total[24h])",
                    "legendFormat": "{{platform}}",
                },
            ],
        },
        {
            "title": "Revenue Closed",
            "type": "stat",
            "datasource": "Prometheus",
            "targets": [
                {"expr": "sum(gnone_revenue_closed_total)", "legendFormat": "Total Revenue"},
            ],
        },
        {
            "title": "Refinement Cycle Distribution",
            "type": "heatmap",
            "datasource": "Prometheus",
            "targets": [
                {"expr": "rate(gnone_refinement_cycles_bucket[1h])"},
            ],
        },
    ],
}
