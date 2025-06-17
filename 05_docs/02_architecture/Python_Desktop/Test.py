import threading
import time

shared_counter = 0
lock = threading.Lock()
USE_LOCK = False  # Set to True to see correct result, False for race condition

def increase():
    global shared_counter
    for _ in range(2000):
        if USE_LOCK:
            with lock:
                shared_counter += 1
        else:
            shared_counter += 1
        time.sleep(0.0001)

threads = []
for _ in range(20):
    t = threading.Thread(target=increase)
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("Expected:", 20 * 2000)
print("Actual:  ", shared_counter)
