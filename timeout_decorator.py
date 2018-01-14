"""Timeout decorator
    Original code:
        https://stackoverflow.com/questions/21827874/timeout-a-python-function-in-windows
"""

from threading import Thread
import functools


def timeout_decorator(timeout_sec):
    def deco(wrapped_func):
        @functools.wraps(wrapped_func)
        def wrapper(*args, **kwargs):
            res = TimeoutError("function '{0}' exceeded {1} seconds".format(wrapped_func.__name__, timeout_sec))

            def new_func():
                try:
                    nonlocal res
                    res = wrapped_func(*args, **kwargs)
                except Exception as e:
                    res = e

            t = Thread(target=new_func)
            t.daemon = True
            try:
                t.start()
                t.join(timeout_sec)
            except Exception as je:
                print('error starting thread')
                raise je

            if isinstance(res, BaseException):
                raise res
            return res

        return wrapper

    return deco


if __name__ == '__main__':
    from time import sleep

    func = timeout_decorator(timeout_sec=2)(sleep)
    try:
        func(3)
        print("wake up!")
    except TimeoutError:
        print("sleep too long")

    @timeout_decorator(2)
    def decorated_func(sec):
        sleep(sec)
        print("wake up!")
        return True
    try:
        decorated_func(1)
    except TimeoutError:
        print("sleep too long")
