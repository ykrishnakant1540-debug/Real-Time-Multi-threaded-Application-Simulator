import threading
from models import ThreadState
import time
import random

class Semaphore:
    """Semaphore compatible with simulator expectations.
    - Constructor signature: Semaphore(value=1, name=None, msg_queue=None)
    - Exposes name, value, waiting_threads, log
    - wait(thread) returns True if acquired, False if blocked
    - signal(thread) releases and potentially unblocks one waiting thread
    - reset() restores initial value and clears queues/logs
    """

    def __init__(self, value: int = 1, name: str | None = None, msg_queue=None):
        # Public fields expected by simulator
        self.value = max(0, int(value))
        self.name = name or f"Semaphore-{id(self)}"
        self.waiting_threads = []  # list of Thread
        self.log = []

        # Internal
        self._initial_value = self.value
        self._lock = threading.Lock()
        self._msg_queue = msg_queue  # optional queue-like with put()
        self._sem_id = id(self)

        # Notify creation if a proper queue is provided
        if hasattr(self._msg_queue, "put"):
            self._msg_queue.put({
                "type": "semaphore_created",
                "sem_id": self._sem_id,
                "name": self.name,
                "count": self.value,
            })

    def _log(self, entry: str):
        timestamp = time.time()
        self.log.append((timestamp, entry))

    def wait(self, thread):
        """Try to acquire the semaphore; return True if acquired else False.
        Also updates thread states consistent with models.Thread.
        """
        with self._lock:
            if self.value > 0:
                self.value -= 1
                # Mark running if not terminated
                if thread.state != ThreadState.TERMINATED:
                    thread.unblock()  # ensure READY->RUNNING timeline in simulator hook
                    thread.run  # no call; state changes are handled in simulator hook
                self._log(f"{thread.name} acquired {self.name}")
                if hasattr(self._msg_queue, "put"):
                    self._msg_queue.put({
                        "type": "semaphore_wait",
                        "thread_id": getattr(thread, "id", None),
                        "sem_id": self._sem_id,
                        "success": True,
                    })
                return True
            else:
                # Block the thread and queue it
                thread.block(resource=self)
                self.waiting_threads.append(thread)
                self._log(f"{thread.name} blocked on {self.name}")
                if hasattr(self._msg_queue, "put"):
                    self._msg_queue.put({
                        "type": "semaphore_wait",
                        "thread_id": getattr(thread, "id", None),
                        "sem_id": self._sem_id,
                        "success": False,
                    })
                return False

    def signal(self, thread=None):
        """Release the semaphore and wake one waiting thread if any."""
        with self._lock:
            if self.waiting_threads:
                next_thread = self.waiting_threads.pop(0)
                next_thread.unblock()
                self._log(f"{getattr(next_thread, 'name', 'Thread')} unblocked by {self.name}")
                if hasattr(self._msg_queue, "put"):
                    self._msg_queue.put({
                        "type": "semaphore_signal",
                        "sem_id": self._sem_id,
                        "thread_id": getattr(next_thread, "id", None),
                    })
            else:
                self.value += 1
                self._log(f"{self.name} released; value={self.value}")
                if hasattr(self._msg_queue, "put"):
                    self._msg_queue.put({
                        "type": "semaphore_signal",
                        "sem_id": self._sem_id,
                        "thread_id": None,
                    })

    def reset(self):
        with self._lock:
            self.value = self._initial_value
            self.waiting_threads.clear()
            self.log.clear()
            # No state changes to blocked threads on reset; simulator recreates primitives.


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.waiting_queue = []

    def enter(self, thread):
        thread.state = ThreadState.READY
        time.sleep(1)
        with self.lock:
            if thread.state == ThreadState.BLOCKED:
                time.sleep(2)
                self.waiting_queue.append(thread)
                self.condition.wait()
            thread.state = ThreadState.RUNNING
            #thread.run_task()
            print(f"Thread {thread.thread_id} is now RUNNING inside the monitor.")

    def exit(self,thread):
        with self.lock:
            if self.waiting_queue:
                next_thread = self.waiting_queue.pop(0)
                next_thread.state = ThreadState.BLOCKED
                self.condition.notify()
                print(f"Thread {thread.thread_id} is leaving the monitor.")
        

'''import threading
from models import ThreadState

class Semaphore:
    def __init__(self, count=1):
        self.count = count
        self.lock = threading.Lock()
        self.queue = []

    def wait(self, thread):
        """Acquire the semaphore."""
        with self.lock:
            if self.count > 0:
                self.count -= 1
                thread.state = ThreadState.RUNNING
                print(f"\tThread {thread.thread_id} is now RUNNING.")
            else:
                thread.state = ThreadState.BLOCKED
                self.queue.append(thread)
                print(f"\tThread {thread.thread_id} is BLOCKED and waiting.")

    def signal(self):
        """Release the semaphore."""
        with self.lock:
            if self.queue:
                thread = self.queue.pop(0)
                thread.state = ThreadState.READY
                print(f"\tThread {thread.thread_id} moved to READY state.")
            else:
                self.count += 1


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.waiting_queue = []  # Keep track of waiting threads

    def enter(self, thread):
        """Enter the monitor, blocking if necessary."""
        with self.lock:
            if thread.state == ThreadState.BLOCKED:
                self.waiting_queue.append(thread)
                print(f"Thread {thread.thread_id} is BLOCKED and waiting.")
                self.condition.wait()
            
            thread.state = ThreadState.RUNNING
            thread.run_task()
            print(f"Thread {thread.thread_id} is now RUNNING inside the monitor.")

    def exit(self, thread):
        """Exit the monitor, waking up a waiting thread if present."""
        with self.lock:
            if self.waiting_queue:
                next_thread = self.waiting_queue.pop(0)
                next_thread.state = ThreadState.READY
                print(f"Thread {next_thread.thread_id} moved to READY state.")
                self.condition.notify()
            
            thread.state = ThreadState.READY
            print(f"Thread {thread.thread_id} is leaving the monitor.")
'''
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------#
'''
import threading
import time
import random
from synchronization import Semaphore
from utils import log_message

# === Many-to-One Model === #
def many_to_one(num_threads, sem_val):
    """Simulates Many-to-One model: Multiple threads sharing a single scheduler."""
    scheduler = Semaphore(sem_val)  # initializing the value of semaphore(user-given)
    threads = []

    log_message(f"\n[Many-to-One] Starting with {num_threads} threads")

    for i in range(num_threads):
        t = threading.Thread(target=many_to_one_worker, args=(i, scheduler))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    log_message("[Many-to-One] Completed.\n")

def many_to_one_worker(thread_id, scheduler):
    """Worker function for Many-to-One model."""
    scheduler.acquire()
    log_message(f"[Thread {thread_id}] Running on single scheduler")
    time.sleep(random.uniform(0.5, 1.5))
    scheduler.release()

# === One-to-Many Model === #
def one_to_many(num_threads):
    """Simulates One-to-Many model: A single thread dispatching multiple worker threads."""
    log_message(f"\n[One-to-Many] Dispatching {num_threads} threads")

    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=one_to_many_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    log_message("[One-to-Many] Completed.\n")

def one_to_many_worker(thread_id):
    """Worker function for One-to-Many model."""
    log_message(f"[Thread {thread_id}] Running independently")
    time.sleep(random.uniform(0.5, 1.5))

# === Many-to-Many Model === #
def many_to_many(num_threads):
    """Simulates Many-to-Many model: Multiple threads working with multiple schedulers."""
    scheduler_count = min(num_threads, 3)  # Allow up to 3 schedulers
    schedulers = [Semaphore(1) for _ in range(scheduler_count)]

    log_message(f"\n[Many-to-Many] Running with {num_threads} threads and {scheduler_count} schedulers")

    threads = []
    for i in range(num_threads):
        scheduler = schedulers[i % scheduler_count]  # Assign thread to a scheduler
        t = threading.Thread(target=many_to_many_worker, args=(i, scheduler))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    log_message("[Many-to-Many] Completed.\n")

def many_to_many_worker(thread_id, scheduler):
    """Worker function for Many-to-Many model."""
    scheduler.acquire()
    log_message(f"[Thread {thread_id}] Running on a shared scheduler")
    time.sleep(random.uniform(0.5, 1.5))
    scheduler.release()
'''
