import yaml
import orjson
import asyncio
import time
import logging
from pygelf import GelfTcpHandler, GelfUdpHandler


class Aggregation:
    def __init__(self, cfg):
        self.flush_after = cfg["flush_after"]
        self.group_by = cfg["group_by"]
        self.fields = cfg["fields"]
        self.buckets = {}
        self.drop_incomplete = cfg.get("drop_incomplete", False)
        self.all_fields = cfg["all_fields"]
        self.name = cfg["name"]

    def process(self, msg):
        msg = {a[1:]: b for a, b in msg.items() if a not in ("message", "_message", "_level", "msg", "_msg", "short_message", "_short_message", "_taskName", "_gim_tags", "_source") and a.startswith("_") and not a.startswith("_gl2")}
        if not all(a in msg for a in self.group_by):
            return
        k = tuple(msg.get(k) for k in self.group_by)
        now = time.time()
        if k not in self.buckets:
            self.buckets[k] = {
                "created": now,
                "values": {"aggregation_complete": "complete", "aggregation_name":self.name}
            }

        if self.all_fields:
            for f in msg:
                if f in self.fields:
                    if f not in self.buckets[k]["values"]:
                        self.buckets[k]["values"][f] = msg[f]
                    else:
                        if not isinstance(self.buckets[k]["values"][f], list):
                            self.buckets[k]["values"][f] = [self.buckets[k]["values"][f]]
                        self.buckets[k]["values"][f].append(msg[f])
                else: 
                    self.buckets[k]["values"][f] = msg[f]
        else:
            for f in self.fields:
                if f in msg:
                    if f not in self.buckets[k]["values"]:
                        self.buckets[k]["values"][f] = msg[f]
                    else:
                        if not isinstance(self.buckets[k]["values"][f], list):
                            self.buckets[k]["values"][f] = [self.buckets[k]["values"][f]]
                        self.buckets[k]["values"][f].append(msg[f])
            for g in self.group_by:
                self.buckets[k]["values"][g] = msg.get(g)

    def flush(self):
        now = time.time()
        out = []
        to_delete = []

        for k, b in self.buckets.items():
            if all(a in b["values"] for a in self.fields):
                out.append(b["values"])
                to_delete.append(k)

            elif now - b["created"] >= self.flush_after:
                if not self.drop_incomplete:
                    b["values"]["aggregation_complete"] = "partial"
                    out.append(b["values"])
                to_delete.append(k)

        for k in to_delete:
            del self.buckets[k]

        return out


class PyGelfSender:
    def __init__(self, host, port, protocol="tcp"):
        self.logger = logging.getLogger("gelf")
        self.logger.setLevel(logging.INFO)
        if protocol.lower() == "udp":
            handler = GelfUdpHandler(host=host, port=port, include_extra_fields=True)
        else:
            handler = GelfTcpHandler(host=host, port=port, include_extra_fields=True)
        self.logger.addHandler(handler)

    def send(self, msg):
        self.logger.critical("Aggregated Log", extra=msg)


async def handle(reader, aggs):
    buf = b""
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break
        buf += chunk
        while b"\x00" in buf:
            msg, buf = buf.split(b"\x00", 1)
            if not msg:
                continue
            try:
                obj = orjson.loads(msg)
            except Exception:
                continue
            #print("[RECV]", obj)
            for a in aggs:
                a.process(obj)


async def server(host, port, aggs):
    srv = await asyncio.start_server(
        lambda r, w: handle(r, aggs),
        host,
        port
    )
    #print(f"listening on {host}:{port}")
    async with srv:
        await srv.serve_forever()


async def flusher(aggs, sender):
    while True:
        await asyncio.sleep(1)

        for a in aggs:
            for msg in a.flush():
                sender.send(msg)
                #print("[SEND]", msg)


def load():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def build(cfg):
    return [Aggregation(a) for a in cfg["aggregations"]]


async def main():
    cfg = load()
    aggs = build(cfg)
    sender = PyGelfSender(
        cfg["output"]["host"],
        cfg["output"]["port"],
        cfg["output"]["protocol"]
    )
    await asyncio.gather(
        server(cfg["listen"]["host"], cfg["listen"]["port"], aggs),
        flusher(aggs, sender),
    )


if __name__ == "__main__":
    asyncio.run(main())
