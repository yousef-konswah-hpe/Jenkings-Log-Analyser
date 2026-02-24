# common/kafka_config.py

KAFKA_BROKER = "10.157.21.212:9092"
TOPIC = "ai_requests"

CONSUMER_CONFIG = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'ai-consumer-group',
    'auto.offset.reset': 'earliest'
}

PRODUCER_CONFIG = {
    'bootstrap.servers': KAFKA_BROKER
}
