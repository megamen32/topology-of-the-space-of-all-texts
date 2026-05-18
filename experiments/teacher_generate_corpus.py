#!/usr/bin/env python3
from pathlib import Path
import json, urllib.request, time
ROOT=Path('/home/roomhacker/babel-experiments')
OUT=ROOT/'datasets/processed/teacher_qwen4b_samples.txt'
URL='http://192.168.2.5:11434/api/generate'
PROMPTS=[
 'Напиши фрагмент переписки друзей с эмодзи и мемным интернет стилем.',
 'Напиши поток русско-английских интернет комментариев.',
 'Сгенерируй хаотичный но живой чат с эмодзи, ссылками и сленгом.',
]
OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('w',encoding='utf-8') as f:
    for i in range(200):
        prompt=PROMPTS[i%len(PROMPTS)]
        payload={'model':'qwen3:4b-instruct','prompt':prompt,'stream':False,'options':{'num_predict':256,'temperature':0.95}}
        req=urllib.request.Request(URL,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=300) as r:
            obj=json.loads(r.read().decode())
        txt=obj.get('response','').replace('\r',' ')
        f.write(txt+'\n')
        if i%10==0:
            print('generated',i,flush=True)
print('done',OUT)
