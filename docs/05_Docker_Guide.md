# Docker Guide

## 1. Why Docker here?
The pipeline needs two infra services — **Kafka** and **PostgreSQL**.
Docker runs both as isolated containers with one command, identical on every
teammate's machine. The application code (producer, Spark, API, frontend)
runs directly on the host in a Python virtualenv / Node, which keeps
development and debugging simple.

```
docker-compose.yml
├── kafka     (apache/kafka:3.9.0)   ports 9092 (clients), 9093 (KRaft)
└── postgres  (postgres:16-alpine)   port 5432, volume pgdata
```

## 2. Every container explained

### 2.1 kafka (`apache/kafka:3.9.0`)
| Setting | Value | Meaning |
|---|---|---|
| KAFKA_NODE_ID | 1 | single-broker cluster |
| KAFKA_PROCESS_ROLES | broker,controller | **KRaft mode** — Kafka stores its own metadata, no Zookeeper needed (a deliberate simplification) |
| KAFKA_CONTROLLER_QUORUM_VOTERS | 1@kafka:9093 | controller election |
| KAFKA_LISTENERS | PLAINTEXT://:9092, CONTROLLER://:9093 | client + controller listeners |
| KAFKA_ADVERTISED_LISTENERS | PLAINTEXT://localhost:9092 | address handed to clients (host access) |
| replication factors | 1 | single broker → no replication (acceptable for a demo) |
| healthcheck | `kafka-broker-api-versions.sh` | container marked healthy only when the broker answers |

### 2.2 postgres (`postgres:16-alpine`)
| Setting | Value |
|---|---|
| user / password / db | sentiment / sentiment / sentiment (demo defaults) |
| volume | `pgdata` — data survives container restarts |
| init script | `db/init.sql` mounted into `/docker-entrypoint-initdb.d/` — creates `comments` + `window_stats` on **first** start |

## 3. Commands

```bash
docker compose up -d          # start both containers (detached)
docker compose ps             # status + health
docker compose logs -f kafka  # follow logs
docker compose down           # stop (keeps pgdata volume)
docker compose down -v        # stop AND erase database data
```

## 4. Kafka cheat-sheet (run inside the container)

```bash
# list / create / describe topics
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-raw --partitions 3
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic comments-raw

# console produce / consume (smoke test)
echo "hello" | docker exec -i sma-kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic comments-raw
docker exec sma-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic comments-raw --from-beginning --max-messages 5

# consumer lag
docker exec sma-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --all-groups --describe
```

## 5. PostgreSQL cheat-sheet

```bash
docker exec sma-postgres psql -U sentiment -d sentiment -c "SELECT count(*) FROM comments;"
docker exec sma-postgres psql -U sentiment -d sentiment -c "SELECT * FROM window_stats ORDER BY window_start DESC LIMIT 5;"
docker exec sma-postgres psql -U sentiment -d sentiment   # interactive shell
```

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| kafka container restarts, log: `advertised.listeners cannot use the nonroutable meta-address 0.0.0.0` | listener env vars incomplete | keep LISTENERS + ADVERTISED_LISTENERS + CONTROLLER_* set together (see docker-compose.yml) |
| `connection refused :9092` from host | container not healthy yet | wait for `(healthy)` in `docker compose ps` |
| tables missing | init.sql only runs on **first** start | `docker compose down -v && docker compose up -d` (erases data) |
| port already in use | local Kafka/Postgres running | stop them or change the mapped port |
| Spark writes fail with PK conflicts | same comment id twice in one batch | already handled: producer generates unique ids; sink dedupes |
