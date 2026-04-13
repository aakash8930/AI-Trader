import json, os

for folder in os.listdir('models'):
    meta = f'models/{folder}/metadata.json'
    if not os.path.isfile(meta):
        continue
    d = json.load(open(meta))
    m = d.get('metrics', {})
    sym = d.get('symbol', folder)
    f1 = m.get('val_f1', 0)
    prec = m.get('val_precision', 0)
    rec = m.get('val_recall', 0)
    th = d.get('optimized_long_threshold', 'N/A')
    pos = m.get('val_positive_rate', 0)
    p_f1 = 'PASS' if f1 >= 0.35 else 'FAIL'
    p_prec = 'PASS' if prec >= 0.35 else 'FAIL'
    p_rec = 'PASS' if rec >= 0.30 else 'FAIL'
    th_str = f'{th:.2f}' if isinstance(th, float) else str(th)
    print(f'{sym}: F1={f1:.3f}({p_f1}) Prec={prec:.3f}({p_prec}) Rec={rec:.3f}({p_rec}) Th={th_str} PosRate={pos:.2f}')
