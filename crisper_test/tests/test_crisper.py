import re, sys
from collections import Counter
from textwrap import wrap
from crisperwhisper import CrisperWhisperModel

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "data/audio/audio.mp3"
LONG_PAUSE = 1.0
W = 46

model = CrisperWhisperModel("small", backend="transformers")
result = model.transcribe(AUDIO, language="en", word_timestamps=True)

words = [(w.word.strip(), w.start, w.end) for w in result.words]
tag = lambda t: t.startswith("[") and t.endswith("]")
clean = lambda t: re.sub(r"[^a-z0-9']", "", t.lower())

FILLER_TAGS = {"um", "uh", "er", "erm", "hmm", "mm", "ah"}
PHRASES = {("you", "know"), ("i", "mean"), ("kind", "of"), ("sort", "of")}

tw = [(clean(t), s, e) for t, s, e in words if not tag(t) and clean(t)]

fillers = Counter(clean(t) for t, s, e in words if tag(t) and clean(t) in FILLER_TAGS)
for i in range(len(tw) - 1):
    if (tw[i][0], tw[i + 1][0]) in PHRASES:
        fillers[tw[i][0] + " " + tw[i + 1][0]] += 1

word_reps = Counter(tw[i][0] + " " + tw[i][0] for i in range(len(tw) - 1) if tw[i][0] == tw[i + 1][0])
phrase_reps = Counter(" ".join((tw[i][0], tw[i + 1][0])) for i in range(len(tw) - 3) if (tw[i][0], tw[i + 1][0]) == (tw[i + 2][0], tw[i + 3][0]))

pauses = [(words[i][2], words[i + 1][1]) for i in range(len(words) - 1) if words[i + 1][1] - words[i][2] >= LONG_PAUSE]

duration = tw[-1][2] - tw[0][1]
minutes = duration / 60
wpm = round(len(tw) / minutes)
n_fill = sum(fillers.values())
n_wrep = sum(word_reps.values())
n_prep = sum(phrase_reps.values())

mmss = lambda x: f"{int(x // 60):02d}:{int(duration_ := x % 60):02d}"
ts = lambda x: f"{int(x // 60):02d}:{x % 60:04.1f}"
times = lambda n: f"{n} time" if n == 1 else f"{n} times"

def line(s=""):
    print("│ " + s.ljust(W - 1) + "│")

def row(a, b):
    line(f"{a:<24}{b}")

def sep():
    print("├" + "─" * W + "┤")

rate = (n_fill + n_wrep + n_prep) / minutes
if rate < 2:
    fluency = "Your speech demonstrates excellent fluency."
elif rate < 5:
    fluency = "Your speech demonstrates good overall fluency."
else:
    fluency = "Your speech needs more fluency practice."

parts = [fluency]
if n_fill >= 3:
    parts.append("Frequent filler words were detected. Try replacing them with short pauses.")
if n_wrep + n_prep >= 3:
    parts.append("Repeated words and expressions were detected. Organize your thoughts before continuing.")
if len(pauses) >= 5:
    parts.append("Several long pauses were found. Practice your transitions between points.")
if wpm < 110:
    parts.append("Your speaking rate is slow. Try to speak a little faster.")
elif wpm > 160:
    parts.append("Your speaking rate is fast. Slow down so the audience can follow.")
else:
    parts.append("Your speaking rate is in a comfortable range.")

print("┌" + "─" * W + "┐")
line("PUBLIC SPEAKING EVALUATION".center(W - 1))
sep()
row("Speech Duration", mmss(duration))
row("Total Words", len(tw))
row("Speaking Rate", f"{wpm} WPM")
sep()
line("DISFLUENCY ANALYSIS")
line()
row("Filler Words", n_fill)
row("Repeated Words", n_wrep)
row("Repeated Phrases", n_prep)
row("Long Pauses", len(pauses))
sep()
line("FILLER WORDS")
line()
for k, v in fillers.most_common(8):
    row(f'"{k}"', times(v))
if not fillers:
    line("None detected")
sep()
line("REPETITIONS")
line()
for k, v in (word_reps + phrase_reps).most_common(8):
    row(f'"{k}"', times(v))
if not (word_reps or phrase_reps):
    line("None detected")
sep()
line("LONG PAUSES")
line()
for a, b in pauses[:10]:
    line(f"{ts(a)} – {ts(b)}")
if len(pauses) > 10:
    line("...")
if not pauses:
    line("None detected")
sep()
line("FEEDBACK")
line()
for l in wrap(" ".join(parts), W - 3):
    line(l)
print("└" + "─" * W + "┘")