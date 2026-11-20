"""Generate, mask and score the preregistered single-edition Qwen study."""
import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "notes/experiments/reference_readability"
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
WORK = Path(os.environ.get("BABEL_STUDY_WORK") or STATE_HOME / "babel" / "reference-readability")
ALPHABET = ROOT / "models/top256_alphabet/alphabet_top256.json"
PROTOCOL_HASH = "0771e4aaa3b99013d9ea22a4237c62bb9811156bdb221dc8dc292dc6ab0b8cf9"
FLAGS = ("readable", "through")
PANELS = ("a", "b")
PORT = 18862
LOOPBACK = "127.0.0.1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def write_once(path, data):
    """Publish a complete file once, allowing identical replays."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        staged = Path(tmp.name)
        try:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            try:
                os.link(staged, path)
            except FileExistsError:
                require(path.read_bytes() == data, f"Уже сохранены другие данные в {path}")
        finally:
            staged.unlink(missing_ok=True)


def save(path, value):
    write_once(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


@contextmanager
def lock(path, *, wait=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(f"Уже выполняется задание {path.stem}") from None
        yield


def draw(seed, count):
    rows = []
    for stream, size in (("even", count // 2), ("odd", count // 2), ("far", count)):
        used = set()
        counter = 0
        while len(used) < size:
            xof = hashlib.shake_256(f"{seed}/{stream}/{counter}".encode("ascii"))
            counter += 1
            if stream == "far":
                n = int.from_bytes(xof.digest(4096), "big") | (1 << 32767)
            else:
                n = (int.from_bytes(xof.digest(8), "big") & ~1) | int(stream == "odd")
            if n < 64 or n in used:
                continue
            used.add(n)
            rows.append({
                "item": f"{stream}-{len(used):02d}",
                "group": "far" if stream == "far" else "near",
                "address": hex(n) if stream == "far" else str(n),
            })
    return rows


def address_digest(row):
    return sha(int(row["address"], 0).to_bytes(4096, "big"))


class Study:
    def __init__(self, data):
        self.data = data
        require(sha((data / "protocol.json").read_bytes()) == PROTOCOL_HASH, "Изменился протокол")
        p = self.protocol = load(data / "protocol.json")
        for name, checksum in (
            ("sample.json", p["sample"]["sample_sha256"]),
            ("reader.json", p["reading"]["rubric_sha256"]),
            ("allocation.json", p["allocation"]["sha256"]),
        ):
            require(sha((data / name).read_bytes()) == checksum, f"Изменился файл {name}")
        rows = load(data / "sample.json")
        require(rows == draw(p["sample"]["seed_ascii"], p["sample"]["per_group"]), "Ошибка выборки")
        self.rows = {r["item"]: r for r in rows}
        previous = load(data.parent / "qwen3_address_pilot/addresses.json")["rows"]
        seen = {r["address_bytes_sha256"] for r in previous}
        require(all(address_digest(r) not in seen for r in rows), "Адрес уже был в пилоте")
        self.reader = load(data / "reader.json")
        self.allocation = load(data / "allocation.json")
        self.controls = self.load_controls()
        self.items = list(self.rows) + list(self.controls)
        pairs = self.allocation["generation_pairs"]
        require(sorted(i for pair in pairs for i in pair) == sorted(self.rows), "Очередь генерации")
        for pair in pairs:
            require(sorted(self.rows[i]["group"] for i in pair) == ["far", "near"], "Состав пары")
        aliases = set()
        for panel in PANELS:
            assignment = self.allocation["panels"][panel]
            require(sorted(r["item"] for r in assignment) == sorted(self.items), "Состав панели")
            for row in assignment:
                alias = row["id"]
                require(re.fullmatch("[0-9a-f]{32}", alias) and alias not in aliases, "Метка карточки")
                aliases.add(alias)
        self.alphabet = "".join(load(ALPHABET)["alphabet"])
        self.weights_sha = load(data.parent / "qwen3_address_pilot/protocol.json")["gguf_sha256"]

    def check_health(self, health):
        require(health["edition"] == self.protocol["generator"]["edition"], "Другое издание")
        require(health["alphabet_sha256"] == sha(self.alphabet.encode()), "Другой алфавит")
        require(health["gguf_sha256"] == self.weights_sha, "Другие веса модели")

    def load_controls(self):
        spec = self.protocol["controls"]
        old = self.data / spec["source"]
        for name, expected in spec["files_sha256"].items():
            require(sha((old / name).read_bytes()) == expected, f"Изменился архивный файл {name}")
        key = load(old / "key.json")
        pages = {}
        for line in (old / "pages.jsonl").read_bytes().splitlines():
            row = json.loads(line)
            entry = key[row["id"]]
            if entry["arm"] == "control":
                name = entry["control"]
                page = row["first"] + row["second"]
                require(len(row["first"]) == len(row["second"]) == 2048, name)
                require(sha(page.encode()) == entry["sha256"] == spec["expected"][name]["sha256"], name)
                pages[name] = page
        require(set(pages) == set(spec["expected"]), "Неполный комплект контролей")
        return pages

    def runtime(self):
        info = load(self.data / "runtime.json")
        require(info["protocol_sha256"] == PROTOCOL_HASH, "Издание от другого протокола")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", info["image_id"]), "Нужен полный Docker image ID")
        return info

    def page_ok(self, item, record, runtime):
        page = record["page"]
        require(record["item"] == item and record["protocol_sha256"] == PROTOCOL_HASH, item)
        require(record["image_id"] == runtime["image_id"], f"Другой образ у {item}")
        self.check_health(record["health"])
        require(record["address_sha256"] == address_digest(self.rows[item]), f"Другой адрес у {item}")
        require(len(page) == 4096 and set(page) <= set(self.alphabet), f"Длина или алфавит у {item}")
        require(sha(page.encode()) == record["sha256"], f"Изменился текст {item}")


def pin_image(study, args):
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", args.image_id), "Нужен полный Docker image ID")
    save(study.data / "runtime.json", {"protocol_sha256": PROTOCOL_HASH, "image_id": args.image_id})


def inspect_container(node, name, port, runtime):
    require(re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", name), "Некорректное имя контейнера")
    require(re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.@-]*", node), "Некорректный SSH-узел")
    fields = "[{{json .Id}},{{json .Image}},{{json .State.Running}},{{json .NetworkSettings.Ports}}]"
    command = ["docker", "inspect", "--type", "container", "--format", fields, name]
    if node != "local":
        command = ["ssh", "-T", "-o", "BatchMode=yes", node, shlex.join(command)]
    raw = subprocess.check_output(command, timeout=30)
    ident, image, running, ports = json.loads(raw)
    require(running is True and image == runtime["image_id"], f"Узел {node} не обслуживает закреплённый образ")
    bindings = (ports or {}).get("8081/tcp") or []
    require(any(p["HostIp"] in (LOOPBACK, "0.0.0.0") and p["HostPort"] == str(port)
                for p in bindings), f"На {node} контейнер не обслуживает 127.0.0.1:{port}")
    return ident


@contextmanager
def endpoint(node, service_port, local_port=None):
    if node == "local" or local_port:
        yield f"http://{LOOPBACK}:{local_port or service_port}"
        return
    with socket.socket() as reserve:
        reserve.bind((LOOPBACK, 0))
        port = reserve.getsockname()[1]
    forward = f"{LOOPBACK}:{port}:{LOOPBACK}:{service_port}"
    command = ["ssh", "-NT", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
               "-L", forward, node]
    with subprocess.Popen(command, stdin=subprocess.DEVNULL) as tunnel:
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and tunnel.poll() is None:
                try:
                    with socket.create_connection((LOOPBACK, port), timeout=0.5):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise ValueError(f"Не открылся SSH-туннель к {node}")
            yield f"http://{LOOPBACK}:{port}"
        finally:
            tunnel.terminate()


def generate(study, args):
    from qwen_reference import ReferenceClient

    runtime = study.runtime()
    pairs = study.allocation["generation_pairs"]
    slot, slots = (int(s) for s in args.shard.split("/"))
    require(1 <= slot <= slots <= len(pairs), "Номер части должен лежать в 1..N")
    items = [i for pair in pairs[slot - 1::slots] for i in pair]
    locks = args.work / "locks"
    initial = inspect_container(args.node, args.container, args.port, runtime)
    with lock(locks / f"engine-{initial}"):
        with endpoint(args.node, args.port, args.local_port) as url:
            client = ReferenceClient(endpoint=url)
            health = client.health()
            study.check_health(health)
            for item in items:
                path = args.work / "generated" / f"{item}.json"
                with lock(locks / item, wait=True):
                    if path.exists():
                        study.page_ok(item, load(path), runtime)
                        continue
                    require(inspect_container(args.node, args.container, args.port, runtime) == initial, "Смена контейнера")
                    start = time.monotonic()
                    try:
                        page = client.unrank(int(study.rows[item]["address"], 0))
                    except Exception as exc:
                        save(args.work / "failures" / f"{item}-{time.time_ns()}.json",
                             {"item": item, "node": args.node, "port": args.port, "container_id": initial,
                              "image_id": runtime["image_id"], "elapsed_s": round(time.monotonic()-start, 3),
                              "received_utc": datetime.now(timezone.utc).isoformat(),
                              "exception": type(exc).__name__})
                        raise
                    elapsed = round(time.monotonic() - start, 3)
                    require(inspect_container(args.node, args.container, args.port, runtime) == initial, "Смена контейнера")
                    row = {"item": item, "image_id": runtime["image_id"], "container_id": initial,
                           "node": args.node, "port": args.port, "health": health, "protocol_sha256": PROTOCOL_HASH,
                           "address_sha256": address_digest(study.rows[item]), "elapsed_s": elapsed,
                           "received_utc": datetime.now(timezone.utc).isoformat(),
                           "sha256": sha(page.encode()), "page": page}
                    study.page_ok(item, row, runtime)
                    save(path, row)
                    print(f"{item}  {elapsed:.1f} с  {row['sha256']}", flush=True)


def pack(study, args):
    runtime = study.runtime()
    generated, missing = {}, {}
    for item in study.rows:
        path = args.work / "generated" / f"{item}.json"
        if not path.exists():
            require(args.missing_reason, f"Ожидается страница {item}")
            missing[item] = args.missing_reason
            continue
        record = load(path)
        study.page_ok(item, record, runtime)
        write_once(args.work / "raw" / f"{item}.txt", record["page"].encode())
        generated[item] = record
    corpus = {"runtime": runtime, "generated": generated, "missing": missing}
    save(study.data / "corpus.json", corpus)
    for panel in PANELS:
        for position, row in enumerate(study.allocation["panels"][panel], 1):
            if row["item"] not in missing:
                path = args.work / "packets" / panel / f"{position:02d}-{row['id']}.json"
                save(path, packet_for(study, corpus, row))


def corpus_for(study):
    corpus = load(study.data / "corpus.json")
    generated, missing = corpus["generated"], corpus["missing"]
    require(corpus["runtime"] == study.runtime(), "Изменился образ корпуса")
    require(set(generated).isdisjoint(missing) and set(generated) | set(missing) == set(study.rows),
            "Неполный или посторонний состав корпуса")
    for item, record in generated.items():
        study.page_ok(item, record, corpus["runtime"])
    return corpus


def packet_for(study, corpus, row):
    item = row["item"]
    page = study.controls[item] if item in study.controls else corpus["generated"][item]["page"]
    return {**study.reader, "card": {"id": row["id"], "first": page[:2048], "second": page[2048:]}}


def packet_digest(packet):
    return sha(json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def pin_readers(study, args):
    require(args.a.strip() and args.b.strip(), "Укажите обе модели читателей")
    save(study.data / "readers.json", {"protocol_sha256": PROTOCOL_HASH, "a": args.a, "b": args.b})


def read_panel(study, args):
    """One stateless, tool-free request per card. Only the anonymous payload leaves here."""
    from openai import OpenAI

    panels = load(study.data / "readers.json")
    require(panels["protocol_sha256"] == PROTOCOL_HASH, "Читатели от другого протокола")
    model = panels[args.panel]
    corpus = corpus_for(study)
    api = OpenAI(max_retries=0, timeout=300)
    with lock(args.work / "locks" / f"panel-{args.panel}"):
        for row in study.allocation["panels"][args.panel]:
            if row["item"] in corpus["missing"]:
                continue
            packet = packet_for(study, corpus, row)
            path = args.work / "votes" / args.panel / (row["id"] + ".json")
            if path.exists():
                validate_receipt(load(path), row["id"], model, packet)
                continue
            result = api.responses.create(
                model=model, instructions=packet["instructions"],
                input=[{"role": "user", "content": [{"type": "input_text",
                        "text": json.dumps(packet["card"], ensure_ascii=False)}]}], tools=[], store=False,
                text={"format": {"type": "json_schema", "name": "reading",
                                 "schema": packet["schema"], "strict": True}},
            )
            save(path, {"id": row["id"], "reader": model, "actual_model": result.model,
                        "response_id": result.id, "status": result.status,
                        "packet_sha256": packet_digest(packet), "raw": result.output_text})
            print(row["id"], result.status, flush=True)


def record_vote(study, args):
    """Receive the unchanged JSON response from a separately run, isolated session."""
    model = load(study.data / "readers.json")[args.panel]
    row = next((r for r in study.allocation["panels"][args.panel] if r["id"] == args.id), None)
    require(row is not None, "Метка отсутствует в очереди этой панели")
    packet = packet_for(study, corpus_for(study), row)
    require(load(args.packet) == packet, "Ответ предъявлен к другой карточке или рубрике")
    require(args.model == model, "Модель не совпала с закреплённым читателем")
    require(args.session.strip(), "Не указано обозначение отдельного сеанса")
    path = args.work / "votes" / args.panel / (args.id + ".json")
    save(path, {"id": args.id, "reader": model, "actual_model": args.model,
                "response_id": args.session, "status": "completed",
                "packet_sha256": packet_digest(packet), "raw": args.response.read_bytes().decode()})


def validate_receipt(receipt, ident, model, packet):
    require(receipt["id"] == ident and receipt["reader"] == model, "Другая карточка или читатель")
    require(receipt["packet_sha256"] == packet_digest(packet), "Изменился выданный пакет")
    require(isinstance(receipt["raw"], str) and receipt["actual_model"] and receipt["response_id"],
            "Неполная квитанция сеанса")


def check_flag(card, reading, flag):
    if not isinstance(reading, dict) or reading.get("id") != card["id"]:
        return None, "ответ без метки этой карточки"
    decision = reading.get(flag)
    reason = reading.get("paragraph_reason" if flag == "readable" else "through_reason")
    if type(decision) != bool or not isinstance(reason, str) or not reason.strip():
        return None, "отсутствует решение или обоснование"
    parts = ({"paragraph_quote": card["first"] + card["second"]} if flag == "readable"
             else {"first_quote": card["first"], "second_quote": card["second"]})
    for name, text in parts.items():
        quote = reading.get(name)
        if decision:
            if not isinstance(quote, str) or not quote.strip():
                return None, f"отсутствует цитата в поле {name}"
            if quote not in text:
                return None, f"цитата из поля {name} не найдена в предъявленном отрывке"
            length = len(quote.strip())
            if not 12 <= length <= 240:
                return None, f"цитата дословная, длина в знаках — {length} при допустимых 12–240"
        elif quote != "":
            return None, f"при отрицательном ответе заполнено поле {name}"
    return decision, ""


def wilson(k, n):
    z = NormalDist().inv_cdf(0.975)
    p = k / n
    denom = 1 + z*z/n
    middle = (p + z*z/(2*n)) / denom
    delta = z * math.sqrt((p*(1-p) + z*z/(4*n))/n) / denom
    return [max(0.0, middle-delta), min(1.0, middle+delta)]


def counts(pairs):
    n = len(pairs)
    known = [pair for pair in pairs if None not in pair]
    yes = known.count((True, True))
    unknown = n - len(known)
    return {
        "n": n, "both_yes": yes, "disagree": sum(a != b for a, b in known),
        "both_no": known.count((False, False)), "unknown": unknown,
        "panels": {panel: {"yes": sum(p[i] is True for p in pairs),
                           "no": sum(p[i] is False for p in pairs),
                           "unknown": sum(p[i] is None for p in pairs)} for i, panel in enumerate(PANELS)},
        "possible_fraction": [yes/n, (yes+unknown)/n],
        "wilson95": None if unknown else wilson(yes, n),
    }


def difference(near, far):
    nlo, nhi = near["possible_fraction"]
    flo, fhi = far["possible_fraction"]
    result = {"possible_pp": [100*(nlo-fhi), 100*(nhi-flo)], "pp": None, "newcombe95_pp": None}
    if not (near["unknown"] or far["unknown"]):
        nl, nu = near["wilson95"]
        fl, fu = far["wilson95"]
        delta = nlo - flo
        result["pp"] = 100*delta
        result["newcombe95_pp"] = [
            100*max(-1, delta - math.hypot(nlo-nl, fu-flo)),
            100*min(1, delta + math.hypot(nu-nlo, flo-fl)),
        ]
    return result


def collect(study, args):
    corpus = corpus_for(study)
    readers = load(study.data / "readers.json")
    require(readers["protocol_sha256"] == PROTOCOL_HASH, "Читатели от другого протокола")
    votes = {}
    session_ids = set()
    for panel in PANELS:
        directory = args.work / "votes" / panel
        rows = study.allocation["panels"][panel]
        expected = {r["id"] for r in rows if r["item"] not in corpus["missing"]}
        require({p.stem for p in directory.glob("*.json")} <= expected, "Посторонний ответ в панели")
        votes[panel] = {}
        for row in rows:
            ident = row["id"]
            path = directory / (ident + ".json")
            if ident not in expected or not path.exists():
                reason = corpus["missing"].get(row["item"]) or args.missing_reason
                require(reason, f"Ожидается ответ панели {panel} на карточку {ident}")
                votes[panel][ident] = {"missing": reason}
                continue
            receipt = load(path)
            validate_receipt(receipt, ident, readers[panel], packet_for(study, corpus, row))
            require(receipt["response_id"] not in session_ids, "Две карточки с одним сеансом")
            session_ids.add(receipt["response_id"])
            votes[panel][ident] = receipt
    save(study.data / "judgments.json", votes)
    return votes


def analyze(study, votes):
    corpus = corpus_for(study)
    readers = load(study.data / "readers.json")
    require(readers["protocol_sha256"] == PROTOCOL_HASH, "Читатели от другого протокола")
    by_item = {item: {} for item in study.items}
    sessions = set()
    for panel in PANELS:
        assignment = study.allocation["panels"][panel]
        require(set(votes[panel]) == {r["id"] for r in assignment}, "Состав голосов панели")
        for row in assignment:
            receipt = votes[panel][row["id"]]
            outcome = {}
            if "missing" in receipt:
                require(bool(receipt["missing"]), "Пропуск без основания")
                for flag in FLAGS:
                    outcome[flag] = {"raw_vote": None, "value": None, "issue": receipt["missing"]}
            else:
                packet = packet_for(study, corpus, row)
                validate_receipt(receipt, row["id"], readers[panel], packet)
                require(receipt["response_id"] not in sessions, "Повтор сеанса")
                sessions.add(receipt["response_id"])
                try:
                    reading = json.loads(receipt["raw"])
                except ValueError:
                    reading = None
                for flag in FLAGS:
                    if receipt["status"] != "completed":
                        value, issue = None, "сеанс не завершён"
                    else:
                        value, issue = check_flag(packet["card"], reading, flag)
                    raw = reading.get(flag) if isinstance(reading, dict) and reading.get("id") == row["id"] else None
                    outcome[flag] = {"raw_vote": raw if type(raw) == bool else None, "value": value, "issue": issue}
                    if value:
                        fields = (("paragraph_quote", "paragraph_reason") if flag == "readable"
                                  else ("first_quote", "second_quote", "through_reason"))
                        outcome[flag].update({key: reading[key] for key in fields})
            by_item[row["item"]][panel] = outcome
    summary, effects = {}, {}
    for flag in FLAGS:
        pairs = {item: tuple(by_item[item][p][flag]["value"] for p in PANELS) for item in study.rows}
        summary[flag] = {group: counts([pair for item, pair in pairs.items()
                                        if study.rows[item]["group"] == group]) for group in ("near", "far")}
        effects[flag] = difference(summary[flag]["near"], summary[flag]["far"])
    inputs = {f: sha((study.data / f).read_bytes()) for f in
              ("protocol.json", "runtime.json", "readers.json", "corpus.json", "judgments.json")}
    return {"input_sha256": inputs, "summary": summary, "effect": effects, "by_item": by_item}


def number(value):
    return f"{value:.1f}".replace(".", ",")


def interval(values, scale=1):
    return "…".join(number(x*scale) for x in values)


def report(study, result, votes):
    groups = {"near": "Малые", "far": "Далёкие"}
    labels = {"readable": "Один понятный абзац", "through": "Развитие между половинами"}
    corpus = corpus_for(study)
    lines = ["# Слепое чтение одного контейнерного издания Qwen", ""]
    for flag, label in labels.items():
        groups_result = result["summary"][flag]
        effect = result["effect"][flag]
        a, b = (groups_result[g]["both_yes"] for g in groups)
        lines += [f"## {label}", "", f"Положительную оценку обоих читателей с проверенными цитатами "
                  f"получили {a}/8 малых и {b}/8 далёких страниц."]
        if effect["pp"] is None:
            lines += [f"С учётом неизвестных исходов разность долей лежит в пределах "
                      f"{interval(effect['possible_pp'])} п. п."]
        else:
            lines += [f"Разность долей (малые минус далёкие) составляет {number(effect['pp'])} п. п. "
                      f"Приближённый 95%-й интервал Ньюкомба — {interval(effect['newcombe95_pp'])} п. п."]
        lines += ["", "| Группа | Оба за | Оба против | Разногласия | Неизвестно | "
                  "Панель A, да/нет/? | Панель B, да/нет/? | Диапазон доли с учётом пропусков | 95% по Уилсону |",
                  "|---|---:|---:|---:|---:|---|---|---|---|"]
        for group, name in groups.items():
            tally = groups_result[group]
            panels = ["/".join(str(tally["panels"][panel][f]) for f in ("yes", "no", "unknown"))
                      for panel in PANELS]
            band = interval(tally["wilson95"], 100) + "%" if tally["wilson95"] else "—"
            lines.append(f"| {name} | {tally['both_yes']} | {tally['both_no']} | {tally['disagree']} "
                         f"| {tally['unknown']} | {panels[0]} | {panels[1]} "
                         f"| {interval(tally['possible_fraction'], 100)}% | {band} |")
        for group, name in groups.items():
            if groups_result[group]["unknown"]:
                items = [i for i, row in study.rows.items() if row["group"] == group]
                raw_yes = [sum(result["by_item"][i][panel][flag]["raw_vote"] is True for i in items)
                           for panel in PANELS]
                lines += ["", f"**{name}.** Исходное «да» поставлено на {raw_yes[0]}/8 страниц в панели A "
                          f"и на {raw_yes[1]}/8 в панели B."]
                for item in items:
                    for panel in PANELS:
                        issue = result["by_item"][item][panel][flag]["issue"]
                        if issue:
                            lines.append(f"Для страницы {item} в панели {panel.upper()} исход неизвестен — {issue}.")
        for group, name in groups.items():
            first = next((item for item, r in study.rows.items() if r["group"] == group and
                          all(result["by_item"][item][p][flag]["value"] is True for p in PANELS)), None)
            if first:
                evidence = result["by_item"][first]["a"][flag]
                lines += ["", f"**{name}, первая зачтённая страница по порядку выборки ({first}).**"]
                keys = ["paragraph_quote"] if flag == "readable" else ["first_quote", "second_quote"]
                for key in keys:
                    lines += ["", "    " + evidence[key].replace("\n", "\n    ")]
                lines += ["", evidence["paragraph_reason" if flag == "readable" else "through_reason"]]
        lines.append("")
    lines += ["## Контроли", "", "Каждый результат приведён в порядке «абзац / связь половин». "
              "Знак вопроса означает пропуск или неподтверждённое свидетельство.", "",
              "| Контроль | Ожидалось | Панель A | Панель B |", "|---|---|---|---|"]
    words = {True: "да", False: "нет", None: "?"}
    for item, expected in study.protocol["controls"]["expected"].items():
        observed = result["by_item"][item]
        cells = [" / ".join(words[expected[f]] for f in FLAGS)]
        cells.extend(" / ".join(words[observed[p][f]["value"]] for f in FLAGS) for p in PANELS)
        lines.append(f"| {item} | {' | '.join(cells)} |")
    for panel in PANELS:
        matches = [sum(result["by_item"][i][panel][f]["value"] is expected[f]
                       for i, expected in study.protocol["controls"]["expected"].items()) for f in FLAGS]
        lines += ["", f"У панели {panel.upper()} совпали с ожидаемыми {matches[0]}/4 решений об абзаце "
                  f"и {matches[1]}/4 решений о развитии."]
    lines += ["", "## Генерация и слепая выдача", "",
              f"Открыты {len(corpus['generated'])} из 16 новых адресов издания "
              f"`{study.protocol['generator']['edition']}`. Для всех страниц закреплён образ "
              f"`{corpus['runtime']['image_id']}`. В выборке малых адресов четыре чётных и четыре нечётных. "
              "Далёкие адреса равномерно выбраны из верхней половины полного диапазона по заранее заданному seed. "
              "Каждый первичный ответ сохранён целиком вместе с SHA-256 и длительностью.",
              "", "Каждая панель получила отдельные случайные метки и свой порядок выдачи. "
              "Проверка цитат использовала оригинальные кодовые точки, включая пробелы. "
              "Предварительная регистрация опубликована в Git до открытия отложенных адресов. "
              "[Публичная регистрация](https://github.com/megamen32/topology-of-the-space-of-all-texts/commit/06e74f7476f50a76975009c9cfc127cb9d747d55)"]
    endpoints = {}
    for row in corpus["generated"].values():
        node = "88" if row["node"] == "local" else row["node"]
        key = node, row["port"]
        endpoints[key] = endpoints.get(key, 0) + 1
    if endpoints:
        lines += ["",
                  "| Узел | Порт на узле | Страниц |", "|---|---:|---:|"]
        for (node, port), count in sorted(endpoints.items()):
            lines.append(f"| {node} | {port} | {count} |")
    models = [", ".join(sorted({r["actual_model"] for r in votes[p].values() if "actual_model" in r}))
              or "нет полученных ответов" for p in PANELS]
    lines += ["", "## Границы вывода", "", f"В панели A использовалась модель {models[0]}, "
              f"в панели B — {models[1]}. Каждая карточка предъявлялась в отдельном сеансе. "
              "Два ИИ-голоса относятся к одной и той же странице.",
              "В каждой группе восемь адресов, и одна страница меняет долю на 12,5 п. п. "
              "Интервалы приближённые. Выборка описывает эти два диапазона одного издания. "
              "Для вывода о человеческом чтении или о других областях библиотеки нужны отдельные данные.",
              "", "Полные тексты, обе исходные оценки, результаты проверки буквальных цитат и "
              "предварительно зафиксированная методика хранятся рядом. "
              "[Корпус](corpus.json) · [Ответы читателей](judgments.json) · "
              "[Подсчёт](result.json) · [Протокол](protocol.json)", ""]
    return "\n".join(lines).encode()


def reduce(study, args):
    votes = collect(study, args)
    result = analyze(study, votes)
    save(study.data / "result.json", result)
    write_once(study.data / "result.md", report(study, result, votes))


def verify(study, args):
    votes = load(study.data / "judgments.json")
    result = analyze(study, votes)
    require(result == load(study.data / "result.json"), "Расхождение в сводке")
    require(report(study, result, votes) == (study.data / "result.md").read_bytes(), "Расхождение в отчёте")
    print("Исходные решения, цитаты и опубликованные итоги сверены.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=WORK, help="закрытый каталог организатора (BABEL_STUDY_WORK)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(action=lambda s, a: print(
        f"Проверены {len(s.rows)} адресов, {len(s.controls)} контроля и две очереди."))
    pin = sub.add_parser("pin-image", help="закрепить ID образа после допуска координатора")
    pin.add_argument("image_id")
    pin.set_defaults(action=pin_image)
    run = sub.add_parser("generate", help="получить одну часть очереди через службу адресов")
    run.add_argument("--node", default="local", help="local или SSH-узел с Docker")
    run.add_argument("--container", required=True, help="имя проверенной реплики")
    run.add_argument("--port", type=int, default=PORT, help="согласованный порт реплики на узле")
    run.add_argument("--local-port", type=int, help="порт уже проверенного координатором SSH-туннеля")
    run.add_argument("--shard", default="1/1", help="номер части, считая с 1, и число частей")
    run.set_defaults(action=generate)
    make = sub.add_parser("pack")
    make.add_argument("--missing-reason", help="окончательная причина отсутствия страниц")
    make.set_defaults(action=pack)
    readers = sub.add_parser("pin-readers", help="закрепить модели панелей до первого чтения")
    readers.add_argument("--a", required=True)
    readers.add_argument("--b", required=True)
    readers.set_defaults(action=pin_readers)
    read = sub.add_parser("read-panel", help="отправить очередной панели отдельные анонимные запросы Responses API")
    read.add_argument("panel", choices=PANELS)
    read.set_defaults(action=read_panel)
    record = sub.add_parser("record", help="принять ответ отдельного внешнего сеанса")
    record.add_argument("panel", choices=PANELS)
    record.add_argument("id")
    record.add_argument("--model", required=True)
    record.add_argument("--session", required=True)
    record.add_argument("--packet", type=Path, required=True)
    record.add_argument("--response", type=Path, required=True)
    record.set_defaults(action=record_vote)
    summary = sub.add_parser("reduce")
    summary.add_argument("--missing-reason", help="окончательная причина отсутствия ответов")
    summary.set_defaults(action=reduce)
    sub.add_parser("verify").set_defaults(action=verify)
    args = parser.parse_args()
    if args.command in ("generate", "pack", "read-panel", "record", "reduce"):
        args.work.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.action(Study(DATA), args)


if __name__ == "__main__":
    main()
