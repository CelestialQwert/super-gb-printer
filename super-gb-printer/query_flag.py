import asyncio
import select

class QueryThreadSafeFlag(asyncio.ThreadSafeFlag):

    def __init__(self):
        asyncio.ThreadSafeFlag.__init__(self)
        self.poller = select.poll()
        self.reg = self, select.POLLIN
        self.poller.register(*self.reg)

    def check(self):
        return (self.reg in self.poller.ipoll(0))
