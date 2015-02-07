# Celery-Remote-Methods
Enables fully-remote objects with instance methods over Celery.

Annotate a class with `@RemoteWorker` and methods with `@remote_task`, and no instance state is exchanged when its delay methods are called. Instances of the class will be created in remote workers only if `@RemoteWorker(remote_only=True)` is used, but by default an instance will exist on both sides.

Pros: should be more lightweight than standard `@task(filter=task_method)` when instances are heavy, method tasks can use non-pickleable objects internally

Cons: instance state is local per worker, code is not yet well-tested

```python
from celery import Celery
app = Celery('tasks', backend='amqp', broker='amqp://')

from remote_work import RemoteWorker, remote_task

bad_adder = None

@RemoteWorker(remote_only=True)  # instance only exists in worker
class BadAdder(object):
    def __init__(self, error=0):
        print "Instantiated BadAdder!"
        self.error = error

    @remote_task
    def add_badly(self, x, y):
        return x + y + self.error


@RemoteWorker  # instances will exist locally and in worker
class NegativeBadAdder(object):
    def __init__(self, error=0):
        print "Instantiated NegativeBadAdder!"
        self.error = error

    def method_we_need_locally(self):
        print "this works! I'm %s." % self

    @remote_task(task_name="neg_add_badly")
    def add_badly(self, x, y):
        return x + y - self.error

def test():
    global bad_adder, nbad_adder

    # create an instance. Note that this will not cause the __init__ method to be called locally,
    # only in the worker when we first call bad_adder.add_badly_delay(...)
    bad_adder = bad_adder or BadAdder(10)
    nbad_adder = nbad_adder or NegativeBadAdder(10)

    nbad_adder.method_we_need_locally()

    async_res = bad_adder.add_badly_delay(1, 2)
    async_res2 = nbad_adder.add_badly_delay(1, 2)
    async_res.get()
    async_res2.get()

    print async_res.result, async_res2.result

```
