from celery import Celery
app = Celery('tasks', backend='amqp', broker='amqp://')

from remote_work import RemoteWorker, remote_task

bad_adder, nbad_adder = None, None


@RemoteWorker(remote_only=True)
class BadAdder(object):
    def __init__(self, error=0):
        # this should only be visible in the worker, not the caller.
        print "Instantiated!"
        self.error = error

    @remote_task
    def add_badly(self, x, y):
        return x + y + self.error

    # task name can be supplied, this is only necessary when there would otherwise be a conflict with the method name.
    @remote_task(task_name="unnecessary_other_name")
    def sub_badly(self, x, y):
        return x + y + self.error

@RemoteWorker
class NegativeBadAdder(object):
    def __init__(self, error=0):
        print "Instantiated (neg)!"
        self.error = error

    def test_local(self):
        print "this works! I'm %s." % self

    # example for when a task name is necessary. caller side, we still use obj.add_badly_delay!
    @remote_task(task_name="neg_add_badly")
    def add_badly(self, x, y):
        return x + y - self.error

def test():
    global bad_adder, nbad_adder

    # create an instance. Note that this will not cause the __init__ method to be called locally,
    # only in the worker when we first call bad_adder.delay(...)
    bad_adder = bad_adder or BadAdder(10)
    nbad_adder = nbad_adder or NegativeBadAdder(10)

    nbad_adder.test_local()

    async_res = bad_adder.add_badly_delay(1, 2)
    async_res2 = nbad_adder.add_badly_delay(1, 2)
    async_res.get()
    async_res2.get()

    print async_res.result, async_res2.result
