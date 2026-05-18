# Static site prototype

No Pyodide. The student is small enough to run as plain JavaScript.

Open:

```bash
python3 -m http.server 8088 -d /home/roomhacker/babel-experiments/site
```

Then browse:

```text
http://192.168.2.75:8088/
```

Production path:

```text
Python research scripts -> exported JSON/bin model -> JS runtime -> static GitHub Pages
```
