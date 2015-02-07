from celery import Celery
app = Celery('tasks', backend='amqp', broker='amqp://')

from remote_work import RemoteWorker, remote_task

@RemoteWorker
class BadAdder(object):
    def __init__(self, error=0):
        print "Instantiated!"
        self.error = error

    @remote_task
    def add_badly(self, x, y):
        return x + y + self.error

bad_adder = None

def test():
    global bad_adder

    # create an instance. Note that this will not cause the __init__ method to be called locally,
    # only in the worker when we first call bad_adder.delay(...)
    bad_adder = bad_adder or BadAdder(10)

    async_res = bad_adder.add_badly_delay(1, 2)
    async_res.get()
    print async_res.result
