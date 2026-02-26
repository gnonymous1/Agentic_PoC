# AgentOS Production Deployment

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### 1. Clone and Configure

```bash
cd Agentic_PoC
cp .env.example .env
```

Edit `.env` and set:
- `SECRET_KEY` - Random 32+ character string
- `JWT_SECRET` - Random 32+ character string  
- `DB_PASSWORD` - Strong database password
- `REDIS_PASSWORD` - Strong Redis password
- `LLM_API_KEY` - Your LLM provider API key

### 2. Deploy

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh production
```

### 3. Access

- **AgentOS Dashboard**: http://localhost:8000
- **Grafana**: http://localhost:3000 (admin/GRAFANA_PASSWORD)
- **Prometheus**: http://localhost:9090

## Architecture

```
┌─────────────┐
│   Nginx     │ :80, :443
│  (Proxy)    │
└──────┬──────┘
       │
┌──────▼──────┐
│  AgentOS    │ :8000, :8765, :8766
│   (App)     │
└──────┬──────┘
       │
   ┌───┴────┬────────┬──────────┐
   │        │        │          │
┌──▼───┐ ┌─▼──┐ ┌───▼────┐ ┌───▼──────┐
│Postgres Redis Prometheus Grafana    │
└──────┘ └────┘ └────────┘ └──────────┘
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| AgentOS | 8000 | Main API |
| Gateway | 8765 | WebSocket Gateway |
| Web Channel | 8766 | Web Channel WS |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Nginx | 80/443 | Reverse Proxy |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboards |

## Management

### View Logs
```bash
docker-compose logs -f agentos
```

### Restart Services
```bash
docker-compose restart agentos
```

### Backup Database
```bash
docker-compose exec postgres pg_dump -U agentos agentos > backup.sql
```

### Rollback
```bash
./scripts/rollback.sh backups/db_backup_YYYYMMDD_HHMMSS.sql
```

### Scale Workers
```bash
docker-compose up -d --scale agentos=3
```

## Monitoring

### Grafana Dashboards
1. Open http://localhost:3000
2. Login with admin/GRAFANA_PASSWORD
3. Navigate to Dashboards → AgentOS

### Prometheus Metrics
- Request rate: `rate(http_requests_total[5m])`
- Error rate: `rate(http_requests_total{status=~"5.."}[5m])`
- Response time: `histogram_quantile(0.95, http_request_duration_seconds_bucket)`

## Security

### Change Default Passwords
```bash
# Generate secure passwords
openssl rand -base64 32

# Update .env file
SECRET_KEY=<generated_key>
JWT_SECRET=<generated_key>
DB_PASSWORD=<generated_password>
```

### Enable HTTPS
1. Obtain SSL certificate (Let's Encrypt recommended)
2. Place cert.pem and key.pem in `nginx/ssl/`
3. Uncomment HTTPS server block in `nginx/nginx.conf`
4. Restart nginx: `docker-compose restart nginx`

### Firewall Rules
```bash
# Allow only necessary ports
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## Troubleshooting

### Health Check Fails
```bash
curl http://localhost:8000/health
docker-compose logs agentos
```

### Database Connection Issues
```bash
docker-compose exec postgres psql -U agentos -c "SELECT 1"
```

### High Memory Usage
```bash
docker stats
# Adjust worker count in docker-compose.yml
```

### Clear Redis Cache
```bash
docker-compose exec redis redis-cli FLUSHALL
```

## Performance Tuning

### Database
- Increase `shared_buffers` in PostgreSQL config
- Add indexes for frequent queries
- Enable query caching

### Application
- Adjust `WORKERS` count based on CPU cores
- Enable Redis caching for LLM responses
- Use connection pooling

### Nginx
- Increase `worker_connections`
- Enable HTTP/2
- Configure caching for static assets

## Backup Strategy

### Automated Backups
```bash
# Add to crontab
0 2 * * * cd /path/to/Agentic_PoC && docker-compose exec -T postgres pg_dump -U agentos agentos > backups/daily_$(date +\%Y\%m\%d).sql
```

### Retention Policy
- Daily backups: Keep 7 days
- Weekly backups: Keep 4 weeks
- Monthly backups: Keep 12 months

## Scaling

### Horizontal Scaling
1. Deploy multiple AgentOS instances
2. Use external PostgreSQL (RDS/Cloud SQL)
3. Use external Redis (ElastiCache/Memorystore)
4. Add load balancer

### Vertical Scaling
- Increase container resources in docker-compose.yml
- Adjust worker count
- Optimize database queries

## Support

- Documentation: `/docs`
- API Reference: `/api/docs`
- Issues: GitHub Issues
- Email: support@agentos.local
