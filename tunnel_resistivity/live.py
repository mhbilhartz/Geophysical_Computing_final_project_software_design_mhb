"""Debounced, latest-request-only background runner, independent of Panel/physics."""
from concurrent.futures import ThreadPoolExecutor
import threading


class LatestOnlyRunner:
    """One worker, at most one pending snapshot; callbacks use the UI dispatcher.

    Scheduler supplies later(ms, callback), cancel(handle), dispatch(callback).
    Requests invalidate the active generation immediately and signal cooperative
    cancellation. A completed old generation can never publish results/errors.
    """
    def __init__(self,work,scheduler,*,on_result,on_error,on_progress,debounce_ms=400,executor=None):
        self.work=work;self.scheduler=scheduler
        self.on_result=on_result;self.on_error=on_error;self.on_progress=on_progress
        self.debounce_ms=debounce_ms
        self.executor=executor or ThreadPoolExecutor(max_workers=1,thread_name_prefix='resistivity-survey')
        self.revision=0;self.closed=False
        self._timer=None;self._pending=None;self._ready=False;self._active=None
        self._lock=threading.RLock()

    def invalidate(self):
        with self._lock:
            self.revision+=1
            if self._timer is not None:self.scheduler.cancel(self._timer)
            self._timer=None;self._pending=None;self._ready=False
            if self._active is not None:self._active[2].set()
            return self.revision

    def request(self,snapshot):
        with self._lock:
            if self.closed:return
            revision=self.invalidate();self._pending=(revision,snapshot)
            self._timer=self.scheduler.later(self.debounce_ms,lambda:self._due(revision))
            return revision

    def _due(self,revision):
        with self._lock:
            if self.closed or revision!=self.revision:return
            self._timer=None;self._ready=True;self._start()

    def _start(self):
        if self.closed or self._active is not None or self._pending is None or not self._ready:return
        revision,snapshot=self._pending;self._pending=None;self._ready=False
        cancelled=threading.Event()
        future=self.executor.submit(self.work,snapshot,cancelled=cancelled.is_set,
                                    progress=lambda done,total:self._post_progress(revision,done,total))
        self._active=(revision,future,cancelled)
        future.add_done_callback(lambda completed:self._dispatch(lambda:self._finish(revision,completed)))

    def _dispatch(self,callback):
        with self._lock:
            if not self.closed:self.scheduler.dispatch(callback)

    def _post_progress(self,revision,done,total):
        def update():
            with self._lock:
                if not self.closed and revision==self.revision:self.on_progress(done,total)
        self._dispatch(update)

    def _finish(self,revision,future):
        with self._lock:
            if self.closed:return
            if self._active is None or self._active[1] is not future:return
            self._active=None
            if revision==self.revision:
                try:result=future.result()
                except Exception as exc:self.on_error(exc)
                else:self.on_result(result)
            self._start()

    @property
    def busy(self):
        with self._lock:return self._active is not None

    def close(self):
        with self._lock:
            if self.closed:return
            self.invalidate();self.closed=True
        self.executor.shutdown(wait=False,cancel_futures=True)
