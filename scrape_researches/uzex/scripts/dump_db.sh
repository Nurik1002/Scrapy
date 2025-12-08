#!/bin/bash
TIMESTAMP=$(date +%F_%H-%M-%S)
FILENAME="dump_$TIMESTAMP.sql"
echo "Dumping database to $FILENAME..."
docker-compose exec -T db pg_dump -U uzex_user uzex_db > "../data/$FILENAME"
echo "Database dumped to data/$FILENAME"
