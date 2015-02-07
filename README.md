# Celery-Remote-Methods
Enables fully-remote objects with instance methods over Celery.

Annotate a class with `@RemoteWorker` and methods with `@remote_task(class_name)`, and instances of the class will be created in remote workers only, and no instance state is exchanged when its methods are called.

Pros: should be more lightweight than standard `@task(filter=task_method)` when instances are heavy, method tasks can use non-pickleable objects internally

Cons: instance state is local per worker, code is not yet well-tested

```python
from celery import Celery
app = Celery('tasks', backend='amqp', broker='amqp://')

from remote_work import RemoteWorker, remote_task

@RemoteWorker
class BadAdder(object):
    def __init__(self, error=0):
        print "Instantiated!"
        self.error = error

    @remote_task("BadAdder")
    def add_badly(self, x, y):
        return x + y + self.error

bad_adder = None

def test():
    global bad_adder
    if not bad_adder:
        # create an instance. Note that this will not cause the __init__ method to be called locally,
        # only in the worker when we first call bad_adder.delay(...)
        bad_adder = BadAdder(10)
    async_res = bad_adder.add_badly.delay(1, 2)
    async_res.get()
    print async_res.result

```
