class Settings:

    MIN_EVENT_LENGTH: int = 20

    BUFFER_LENGTH: int = 1000

    EVENT_MERGE_TIME: float = 0.32

    EVENT_STD: float = 2.0  

    # 1 should work cannot guarente anything else
    MAX_SAMPLES_PER_CHUNK: int = 1