from engine import Engine

engine = Engine()
try:
    engine.save_fetched_products()
except Exception as e:
    print(f"An error occurred while accessing the websites: {e}")
finally:
    del engine
