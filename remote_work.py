"""
The goal of all this messiness is to allow creating and executing celery tasks of instance methods WITHOUT pickling and
sending the state of the object.

Important: as of yet, current_app needs to be initialized and importable before importing this module.

Why not use just functions, you ask? I'm not really sure. I made this because I'm working on a project where I have a
general-purpose RSS parser class that I want to send tasks to, as well as classes representing statistical models, which
are quite heavy, and I wanted to use the same style of communication with both. In retrospect, that seems like not a
very well thought-out decision, but hey, I already made this now.

I don't really know if this works like I think it does, but from my (limited) testing it seems to do the job.

Usage is simple: you write your class, and decorate the methods you want with @remote_task. The class itself
needs to be decorated using @RemoteWorker. Then, to remotely call obj.method, you call obj.method_delay(), almost like
for a normal task.

How it works behind the scenes:
When the module containing your classes get imported, the @remote_task decorator
    a)  creates a function for the worker, which when called either instantiates the class using the same arguments that
     the caller's object __init__ was supplied with (that information is basically the only repeated state transfer), or
     re-uses the previously created instance (which can be found because the metaclass creates and tracks instances)
    b) creates a method that uses current_app.send_task(), which becomes the method_delay attribute of the original
    function.

Afterwards, the @RemoteWorker decorator registers the class as a worker and sets its metaclass, which is needed for
creating instances later and keeping tracks of those instances, respectively. Once the object is instantiated, the
metaclass __new__ supplied the objects annotated members with a reference to the instance, and also makes sure to skip
calling the __init__ method in the caller's process (__init__ is only called in the worker, to conserve memory on heavy
objects and, well, because that's the whole point of this module).

So practically, the object isn't fully instatiated in the caller process (only via __new__, not __init__), but once the
method is called, the worker side creates an instance using the __init__ arguments used on the calling object.
After that, the corresponding instance is re-used on the worker side on each call to method_delay of the object.

If the RemoteWorker DOES rely on internal state changes at run time, make sure to only have one celery worker that
executes it's task.
"""
try:
    from celery import current_app
except:
    print "current_app needs to be importable!"
import new

class_table = dict()
bound_delay_registry = dict()

class _RemoteWorkerMeta(type):
    instances = dict()
    num_instances = 0

    def __call__(cls, *args, **kwargs):
        __instance_id__ = kwargs.get("__instance_id__", cls.num_instances)
        kwargs.pop("__instance_id__", None)


        if (__instance_id__, cls) in cls.instances:
            _instance, instantiation_args = cls.instances[(__instance_id__, cls)]
        else:
            __skip__init = kwargs.get("__skip__init", True)
            kwargs.pop("__skip__init", None)

            _instance = cls.__new__(cls, *args, **kwargs)

            if not __skip__init:
                _instance.__init__(*args, **kwargs)

            for a_name in filter(lambda a: not a.startswith("__"), dir(_instance))[:]:
                attr = getattr(_instance, a_name)
                if getattr(attr, "__is_remote__", False):
                    new_name = a_name + "_delay"
                    setattr(_instance, new_name, new.instancemethod(bound_delay_registry[attr.__task_name__], _instance, cls))

            _instance.__instance_id__ = __instance_id__
            cls.instances[(__instance_id__, cls)] = (_instance, (args, kwargs))
            cls.num_instances += 1

        return _instance


def RemoteWorker(cls):
    __name = str(cls.__name__)
    __bases = tuple(cls.__bases__)
    __dict = dict(cls.__dict__)
    for each_slot in __dict.get("__slots__", tuple()):
        __dict.pop(each_slot, None)

    __dict["__metaclass__"] = _RemoteWorkerMeta
    __dict["__wrapped__"] = cls

    newcls = _RemoteWorkerMeta(__name, __bases, __dict)
    class_table[cls.__name__] = newcls
    return newcls


class _remote_method_delay(object):
    def __init__(self, task_name):
        self.task_name = task_name
        self._instance = None

    def __call__(self, *args, **kwargs):
        __instance_id__ = self._instance.__instance_id__
        _, instantiation_args = self._instance.__class__.instances[(__instance_id__, self._instance.__class__)]
        kwargs.update({
            "__class_name__": self._instance.__class__.__name__,
            "__instance_id__": __instance_id__,
            "__instantiation_args__": instantiation_args
        })
        res = current_app.send_task(self.task_name, args, kwargs)
        return res



def remote_task(*decorator_args, **decorator_kwargs):
    no_args = False
    if len(decorator_args) == 1 and not decorator_kwargs and callable(decorator_args[0]):
        # We were called without args
        method_ = decorator_args[0]
        no_args = True

    task_name_ = decorator_kwargs.get("task_name", None)

    def remote_task_decorator(method):
        method_name = method.__name__
        task_name = task_name_ or method_name

        @current_app.task(name=task_name)
        def method_using_local_class_instance(*args, **kwargs):
            __class_name__ = kwargs["__class_name__"]
            __instance_id__ = kwargs["__instance_id__"]
            r_args, r_kwargs = kwargs["__instantiation_args__"]
            del kwargs["__class_name__"]
            del kwargs["__instance_id__"]
            del kwargs["__instantiation_args__"]

            method_class = class_table[__class_name__]
            _instance = method_class(*r_args, __instance_id__=__instance_id__, __skip__init=False, **r_kwargs)
            actual_local_method = getattr(_instance, method_name)
            return actual_local_method(*args, **kwargs)

        def method_delay(self, *args, **kwargs):
            __instance_id__ = self.__instance_id__
            _, instantiation_args = self.__class__.instances[(__instance_id__, self.__class__)]
            kwargs.update({
                "__class_name__": self.__class__.__name__,
                "__instance_id__": __instance_id__,
                "__instantiation_args__": instantiation_args
            })
            res = current_app.send_task(task_name, args, kwargs)
            return res

        #method.__delay = method_delay
        method.__task_name__ = task_name
        method.__is_remote__ = True

        bound_delay_registry[task_name] = method_delay

        return method

    if no_args:
        return remote_task_decorator(method_)
    else:
        return remote_task_decorator


