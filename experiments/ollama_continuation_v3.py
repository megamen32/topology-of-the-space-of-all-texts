"""Causal continuation for the v3 Qwen edition. The long excerpt goes only to the scene reader."""
import json

EDITION = "babel-qwen3-1.7b-ollama0.32.1-gpu-b128-v3"
CHAT = "<|im_start|>user\n{task}\n/no_think<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n{tail}"
EXCERPT = "<passage>\n{text}\n</passage>"
OMISSION = "\n[…]\n"
PARAGRAPH = "\n\n"
ESCAPES = (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"))
END_MARKS = ".!?…»”’\"')"
STATE_FIELDS = ("actor", "place", "prop", "last")
BEAT_FIELDS = ("cue", "deed", "impact")
HEAD_BYTES, END_BYTES = 1360, 2720
FIELD_BYTES, VOICE_BYTES = 256, 210
WORD_ANCHOR, WORD_LIMIT = 18, 12
MAX_SCENES = 4
READ_OPTIONS = {"num_ctx": 6144, "num_predict": 224}
PLAN_OPTIONS = {"num_predict": 240, "repeat_penalty": 1.06, "repeat_last_n": 96}
PROSE_OPTIONS = {"num_predict": 1024, "temperature": 0.49, "top_k": 32, "top_p": 0.90,
                 "repeat_penalty": 1.13, "repeat_last_n": 192, "frequency_penalty": 0.10}
READ = ("A continuity editor needs a factual note about the very LAST moment of this passage. "
        "Give brief English phrases, keeping proper names. actor: whose viewpoint and name or role; "
        "last: their last visible act or movement; place: where that leaves them NOW; prop: one "
        "specific established object relevant at the cut. Leave unknown details open.")
PLAN = ("The story so far, in a continuity editor's notes: {actor}, {place}. Object: {prop}. "
        "Last event: {last}.\nAssigned action for the NEXT minute: {tactic}\n"
        "Stage a plausible encounter here. Fill three JSON fields in chronological order, one short "
        "sentence each. cue: what the character now sees or hears that calls for this act; deed: how "
        "they actually perform the assigned action using what is at hand; impact: an observable result "
        "of that deed that changes what somebody can do. Supply precise, ordinary physical details.")
TACTICS = (
    "Compare an identifying mark on something at hand against a second detail, then correct a mix-up.",
    "Show what the character has found to a person who needs it. Have that person put it to use immediately.",
    "Reach for something about to slip away and use something in the scene to retrieve it.",
    "Answer a signal from nearby with a specific sign or gesture that changes another person's course.",
)
AFTERMATH = "Act on the physical result of the last event. Another person notices the change and responds to it."
WRITE = {
    "ru": "Пиши продолжение по-русски, в том же лице и времени. Рабочие пометы редактора даны "
          "по-английски. Герой: {actor}. Место: {place}.\nГерой замечает: {cue}\nПоступок: {deed}\n"
          "Что из этого выходит: {impact}\nДопиши начатую фразу и разверни эту сцену в четырёх абзацах, "
          "около 350 слов. Покажи всё в действии, вплоть до движений рук и короткой реплики. Только проза.",
    "en": "Continue in English in the same voice and tense. Character: {actor}. Place: {place}.\n"
          "What catches their attention: {cue}\nWhat they do: {deed}\nWhat comes of it: {impact}\n"
          "Finish the line already on the page and play the scene in real time, in four paragraphs "
          "of fiction, about 350 words. Show the precise movements and a short exchange of dialogue.",
}


def object_format(fields):
    return {"type": "object", "properties": {k: {"type": "string"} for k in fields},
            "additionalProperties": False, "required": list(fields)}


def escaped(text):
    for char, entity in ESCAPES:
        text = text.replace(char, entity)
    return text.encode("utf-8", "ignore")


def read_fields(answer, fields):
    try:
        card = json.loads(answer)
    except (ValueError, RecursionError):
        card = {}
    if not isinstance(card, dict):
        card = {}
    result = {}
    for name in fields:
        value = card.get(name)
        compact = " ".join(value.split()) if isinstance(value, str) else ""
        result[name] = escaped(compact)[:FIELD_BYTES].decode("utf-8", "ignore")
    return result


def finish_word(source):
    """Only restore the end of a word witnessed after exactly the same context in U."""
    if not source[-1].isalpha():
        return ""
    anchor = source[-WORD_ANCHOR:]
    pos = source.rfind(anchor, 0, len(source) - len(anchor))
    if pos < 0:
        return ""
    start = pos + len(anchor)
    end = start
    while end < len(source) and source[end].isalpha() and end - start < WORD_LIMIT:
        end += 1
    return source[start:end] if end < len(source) and not source[end].isalpha() else ""


def compose(source, language, generate, size, key):
    """generate returns the raw JSON for cards and alphabet-normalized text for prose."""
    result = finish_word(source)
    for scene in range(MAX_SCENES):
        context = (source + result)[-size:]
        data = escaped(result if scene and result.strip() else context)
        if len(data) > HEAD_BYTES + END_BYTES:
            head = data[:HEAD_BYTES].decode("utf-8", "ignore")
            tail = data[-END_BYTES:].decode("utf-8", "ignore")
            excerpt = head + OMISSION + tail
        else:
            excerpt = data.decode("utf-8")
        task = EXCERPT.format(text=excerpt) + "\n" + READ
        answer = generate("read", CHAT.format(task=task, tail=""))
        state = read_fields(answer, STATE_FIELDS)
        tactic = AFTERMATH if scene else TACTICS[key[4] % len(TACTICS)]
        task = PLAN.format(**state, tactic=tactic)
        answer = generate("plan", CHAT.format(task=task, tail=""))
        beats = read_fields(answer, BEAT_FIELDS)
        separator = PARAGRAPH if context[-1] in END_MARKS else ""
        task = WRITE[language].format(**state, **beats)
        voice = escaped(context)[-VOICE_BYTES:].decode("utf-8", "ignore") + separator
        prose = generate("write", CHAT.format(task=task, tail=voice))
        if prose.strip():
            if separator or context[-1].isspace():
                prose = prose.lstrip()
            result += (separator + prose)[:size - len(result)]
            if len(result) == size:
                break
    return result


STAGES = {"read": READ_OPTIONS, "plan": PLAN_OPTIONS, "write": PROSE_OPTIONS}
CARD_FORMATS = {"read": object_format(STATE_FIELDS), "plan": object_format(BEAT_FIELDS)}
PROMPTS = {
    "chat": CHAT, "excerpt": EXCERPT, "omission": OMISSION, "read_join": "\n", "escapes": ESCAPES,
    "read": READ, "plan": PLAN, "assigned_actions": TACTICS, "aftermath": AFTERMATH, "write": WRITE,
    "response_formats": CARD_FORMATS, "end_marks": END_MARKS, "paragraph": PARAGRAPH,
}
RULES = {
    "stages_per_scene": list(STAGES), "max_scenes": MAX_SCENES, "key_byte_for_action": 4,
    "word_anchor_symbols": WORD_ANCHOR, "max_word_completion_symbols": WORD_LIMIT,
    "word_boundary": "on a letter, use the nearest earlier nonoverlapping exact anchor in U; "
                     "accept only a complete run of letters bounded by a nonletter",
    "context": "last half-page of U + accepted text; after the first scene the reader uses accepted "
               "text if nonblank; escape before UTF-8 slicing and discard incomplete boundary bytes",
    "excerpt_head_bytes": HEAD_BYTES, "excerpt_tail_bytes": END_BYTES, "max_field_bytes": FIELD_BYTES,
    "card_values": "JSON object, string fields only, collapse whitespace; absent or invalid fields are empty",
    "action": "first scene uses key[4] modulo number of actions; later scenes use aftermath",
    "voice_tail_bytes": VOICE_BYTES, "paragraph_boundary": "append paragraph if last source symbol is in end_marks",
    "append": "skip blank prose; lstrip after separator or source whitespace; take up to remaining symbols",
}
