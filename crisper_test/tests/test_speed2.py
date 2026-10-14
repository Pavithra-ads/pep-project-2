import sys, time, torch
torch.set_num_threads(4)
from crisperwhisper import CrisperWhisperModel
t = time.perf_counter()
m = CrisperWhisperModel('small', backend='transformers', compute_type='float32', device='cpu')
print('load', round(time.perf_counter() - t, 1), 's', flush=True)
t = time.perf_counter()
r = m.transcribe(sys.argv[1], language='en', word_timestamps=True)
print('transcribe', round(time.perf_counter() - t, 1), 's for', round(r.duration, 1), 's of audio', flush=True)
print(r.text[:200])
