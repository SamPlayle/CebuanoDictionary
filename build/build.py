#!/usr/bin/env python3
"""Parse Wolff's Cebuano dictionary (Gutenberg #40074 HTML) into a compact
search database for the offline app.

usage: build.py 40074-h.htm out.json
"""
import re, sys, html, json, unicodedata, collections, itertools

SRC, OUT = sys.argv[1], sys.argv[2]
t = open(SRC, encoding='utf-8').read().replace('\r', '')
start = t.index('<h2 id="xd20e4596" class="main">A</h2>')
end = t.index('<h2 id="xd20e530606"')          # BIBLIOGRAPHY
addenda_at = t.index('<h2 id="xd20e519770"')    # ADDENDA
body = t[start:end]

VOW = set('aiu')


def strip_marks(s):
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def norm(s):
    """Spelling key: no accents, e→i, o→u, Spanish letters → Wolff's."""
    s = strip_marks(html.unescape(s)).lower()
    s = re.sub(r'\(.*?\)', '', s)          # (→) (←)
    s = re.sub(r'[0-9₀-₉]', '', s)
    s = s.replace('ñ', 'ny').replace('ch', 'ts').replace('qu', 'k')
    s = s.translate(str.maketrans('eocfvzjq', 'iukpbsdk'))
    s = s.replace('x', 'ks')
    return re.sub(r'[^a-z]', '', s)


def text_of(frag):
    return html.unescape(re.sub(r'<[^>]+>', '', frag))


# ---------------------------------------------------------------- clean HTML
def clean(p):
    p = re.sub(r'<span class="pagenum">.*?</span>', '', p, flags=re.S)
    p = re.sub(r'<a class="noteref".*?</a>', '', p, flags=re.S)
    p = re.sub(r'\s+', ' ', p)
    p = re.sub(r'=\s+"', '="', p)
    p = re.sub(r'<(\w+)\s+>', r'<\1>', p)
    p = re.sub(r'<span class="corr"[^>]*>', '<span>', p)
    p = re.sub(r'\s+', ' ', p)
    return p.strip()


def compact(p):
    """Rewrite to short custom tags the app styles:
    c = Cebuano bold form, n = sense number, x = Cebuano example,
    o = part of speech / italic, r = grammar code, k = small caps,
    g = Latin binomial. Links keep href=#id."""
    out = []
    stack = []
    pos = 0
    for m in re.finditer(r'<(/?)([a-z0-9]+)([^>]*)>', p):
        out.append(p[pos:m.start()])
        pos = m.end()
        close, tag, attrs = m.group(1), m.group(2), m.group(3)
        if close:
            out.append(stack.pop() if stack else '')
            continue
        if tag == 'b':
            if 'lang="ceb"' in attrs:
                o, c = '<c>', '</c>'
            elif 'la-x-bio' in attrs:
                o, c = '<g>', '</g>'
            else:
                o, c = '<n>', '</n>'
        elif tag == 'i':
            o, c = ('<x>', '</x>') if 'lang="ceb"' in attrs else ('<o>', '</o>')
        elif tag == 'span':
            if 'class="rm"' in attrs:
                o, c = '<r>', '</r>'
            elif 'class="sc"' in attrs:
                o, c = '<k>', '</k>'
            else:
                o, c = '', ''
        elif tag == 'a':
            h = re.search(r'href="#([^"]+)"', attrs)
            o, c = (f'<a href="#{h.group(1)}">', '</a>') if h else ('', '')
        elif tag in ('sub', 'sup'):
            o, c = f'<{tag}>', f'</{tag}>'
        elif tag == 'br':
            out.append(' ')
            continue
        else:
            o, c = '', ''
        out.append(o)
        stack.append(c)
    out.append(p[pos:])
    s = ''.join(out)
    s = html.unescape(s).replace('&', '&amp;') if False else s
    # turn entities into characters, keeping markup-significant ones escaped
    s = re.sub(r'&(?!lt;|gt;|amp;|quot;)(#?\w+);', lambda m: html.unescape(m.group(0)), s)
    s = re.sub(r'<(\w+)>\s*</\1>', '', s)
    return s.strip()


# ---------------------------------------------------------------- affixes
def nasal(prefix_stem, root):
    """prefix_stem is e.g. 'pa' for paN-. Returns spellings of paN-+root."""
    P = prefix_stem
    r0 = root[0]
    rest = root[1:]
    outs = set()
    if r0 in 'bp':
        outs |= {P + 'm' + rest, P + 'm' + root}
    elif r0 in 'ts':
        outs |= {P + 'n' + rest, P + 'n' + root}
    elif r0 == 'd':
        outs |= {P + 'n' + root, P + 'n' + rest}
    elif r0 == 'k':
        outs |= {P + 'ng' + rest, P + 'ng' + root}
    elif r0 == 'g':
        outs |= {P + 'ng' + root, P + 'ng' + rest}
    elif r0 in 'mn':
        outs |= {P + root, P + 'ng' + root}
    else:   # vowel (glottal), h, l, r, y, w, ng
        outs |= {P + 'ng' + root}
    return outs


def add_suffix(root, suf):
    outs = {root + suf}
    if root[-1] in VOW:
        outs.add(root + 'h' + suf)
        if suf[0] in VOW and root[-1] == suf[0]:
            outs.add(root[:-1] + suf)
    else:
        # syncope of the last vowel: dakup+an → dakpan, sulud+un → sudlun
        m = re.match(r'^(.*[aiu])([^aiu]+)([aiu])([^aiu])$', root)
        if m and len(m.group(2)) == 1:
            outs.add(m.group(1) + m.group(2) + m.group(4) + suf)
            outs.add(m.group(1) + m.group(4) + m.group(2) + suf)  # metathesis
    return outs


def add_infix(root, inf):
    if root[0] in VOW:
        return {inf + root}
    m = re.match(r'^(ng|[^aiu])(.*)$', root)
    return {m.group(1) + inf + m.group(2)}


INFIX = {'in': ['in'], 'um': ['um'], 'r': ['ar', 'al', 'ra'], 'l': ['al'],
         'ar': ['ar'], 'al': ['al']}


def parse_affix(label):
    """'paN-an' → list of (prefix, infixes, suffix, nasal)."""
    lab = strip_marks(label).replace(' ', '')
    lab = re.sub(r'\(.*?\)', '', lab)
    lab = re.sub(r'[0-9]', '', lab)
    res = []
    for alt in re.split(r'[,/]', lab):
        if '-' not in alt or not re.fullmatch(r'[a-zN-]+', alt):
            continue
        if alt.startswith('C'):
            continue
        parts = alt.split('-')
        # parts: prefix, *infix, suffix   ('' where absent)
        if len(parts) < 2:
            continue
        pre, suf = parts[0], parts[-1]
        mids = [x for x in parts[1:-1] if x]
        if len(parts) == 3 and pre == '' and suf == '':   # -in-
            pass
        if not re.fullmatch(r'[a-zN]*', pre) or 'N' in suf:
            continue
        res.append((pre, mids, suf))
    return res


def derive(root, pre, mids, suf):
    forms = {root}
    for mid in mids:
        nxt = set()
        for f in forms:
            for inf in INFIX.get(mid, [mid]):
                nxt |= add_infix(f, inf)
        forms = nxt
    if suf:
        forms = set(itertools.chain.from_iterable(add_suffix(f, suf) for f in forms))
    if pre:
        p = norm(pre.replace('N', '')) if 'N' not in pre else None
        nxt = set()
        for f in forms:
            if 'N' in pre:
                stem = norm(pre[:pre.index('N')])
                after = norm(pre[pre.index('N') + 1:])
                nxt |= nasal(stem, after + f) if not after else nasal(stem, f)
            else:
                nxt.add(p + f)
        forms = nxt
    return {f for f in forms if f != root}


MORPH = set('pa ka ma na hi ha di ti tag tig taga ig i gi ni pag mag nag maka naka paka '
            'pina pasi pahi paki pakig pala kina ika tali pati in um r l an un a ay anan '
            'unun anay ka sing'.split())


def is_affix(part):
    s = re.sub(r'\(.*?\)|[0-9]', '', strip_marks(part)).strip()
    if not re.fullmatch(r'[a-zN-]+', s) or '-' not in s:
        return False
    if s.startswith('-') or s.endswith('-') or 'N' in s:
        return True
    return all(x in MORPH for x in s.split('-'))


# ---------------------------------------------------------------- l-dropping
def l_variants(k):
    """Dialect variants Wolff says are implied by an l-form (§5.21)."""
    outs = set()
    rules = [
        (r'(?<=([aiu]))l(?=\1)', lambda m: ''),        # balay → baay → bay
        (r'(?<=a)l(?=u)|(?<=u)l(?=a)', lambda m: 'w'),  # lalum → lawum
        (r'(?<=[^aiu])l(?=[aiu])', lambda m: ''),      # kinahanglan → kinahangan
        (r'al$', lambda m: 'aw'), (r'ul$', lambda m: 'u'),
        (r'(?<=[aiu])l(?=[aiu])', lambda m: 'y'),      # tingali → tingayi
    ]
    for pat, rep in rules:
        sites = list(re.finditer(pat, k))
        for n in range(1, min(len(sites), 3) + 1):
            for combo in itertools.combinations(sites, n):
                s, last = [], 0
                for m in combo:
                    s.append(k[last:m.start()]); s.append(rep(m)); last = m.end()
                s.append(k[last:])
                v = ''.join(s)
                v = re.sub(r'([aiu])\1', r'\1', v)   # collapse the long vowel
                outs.add(v)
    # alu → u (dalunggan → dunggan)
    if 'alu' in k:
        outs.add(k.replace('alu', 'u', 1))
    outs.discard(k)
    return outs


# ---------------------------------------------------------------- English
def english_segments(p):
    """Definition text with the Cebuano examples and their translations
    removed, split into short glosses. Returns [(sub_label, gloss)]."""
    s = re.sub(r'<span class="rm"[^>]*>.*?</span>', ' ', p, flags=re.S)
    s = re.sub(r'<span class="corr"[^>]*>|</span>|<span[^>]*>', '', s)
    s = re.sub(r'<a [^>]*>|</a>', '', s)
    # example + following translation (up to next tag)
    s = re.sub(r'<i lang="ceb">.*?</i>[^<]*', ' ¦ ', s, flags=re.S)
    s = re.sub(r'<b lang="la-x-bio">.*?</b>', ' ', s, flags=re.S)
    segs = []
    label = ''
    for m in re.finditer(r'<b[^>]*lang="ceb"[^>]*>(.*?)</b>|<b>.*?</b>|<i>.*?</i>|<[^>]+>|([^<]+)', s, re.S):
        if m.group(1) is not None:
            label = text_of(m.group(1)).strip()
            if not segs and not label.startswith('—'):
                label = ''      # the head word itself
            continue
        txt = m.group(2)
        if not txt:
            continue
        txt = html.unescape(txt)
        txt = re.sub(r'\(.*?\)', ' ', txt)
        for chunk in re.split(r'[;¦]|\.(?:\s|$)|:\s', txt):
            for g in chunk.split(','):
                g = re.sub(r'\s+', ' ', g).strip(' .=-—')
                g = re.sub(r'^(k\.o\.|s\.t\.|s\.o\.)$', '', g)
                if len(g) > 1 and re.search(r'[a-zA-Z]{2}', g):
                    segs.append((label, g))
    return segs


# ---------------------------------------------------------------- parse
paras = list(re.finditer(r'<p>(.*?)</p>', body, re.S))
entries = []
ids = {}
head = collections.defaultdict(list)
sub = collections.defaultdict(list)
der = collections.defaultdict(list)
var = collections.defaultdict(list)
exw = collections.defaultdict(collections.Counter)
eng = []

for pm in paras:
    raw = pm.group(1)
    p = clean(raw)
    m = re.match(r'<b([^>]*)lang="ceb"[^>]*>(.*?)</b>', p, re.S)
    if not m:
        continue
    idx = len(entries)
    hid = re.search(r'id="([^"]+)"', m.group(1))
    if hid:
        ids[hid.group(1)] = idx
    headtxt = text_of(m.group(2)).strip()
    heads = [h.strip() for h in headtxt.split(',') if h.strip()]
    hkeys = []
    for h in heads:
        k = norm(h)
        if k and k not in hkeys:
            hkeys.append(k)
    for k in hkeys:
        head[k].append(idx)
    is_add = (start + pm.start()) >= addenda_at
    entries.append([compact(p), 1 if is_add else 0])

    roots = [k for k in hkeys if k]
    # sub-entries: written-out forms and affix labels
    for sm in list(re.finditer(r'<b[^>]*lang="ceb"[^>]*>(.*?)</b>', p, re.S))[1:]:
        lab = text_of(sm.group(1)).strip()
        hw = re.sub(r'[0-9]', '', text_of(re.sub(r'<sub>.*?</sub>', '', m.group(2)))).split(',')[0].strip()
        for part in re.split(r',\s*', lab):
            part = part.strip().replace('—', hw).strip()
            if not part:
                continue
            if is_affix(part):
                for pre, mids, suf in parse_affix(part):
                    for r in roots:
                        for f in derive(r, pre, mids, suf):
                            der[f].append((idx, re.sub(r'\(.*?\)', '', part)))
            else:
                k = norm(part)
                if k and k not in hkeys:
                    sub[k].append((idx, part))
    # dialect l-variants of head words
    for k in hkeys:
        for v in l_variants(k):
            var[v].append(idx)
    # words in Cebuano examples
    for xm in re.finditer(r'<i lang="ceb">(.*?)</i>', p, re.S):
        for w in re.findall(r"[^\s,.!?;:()\"“”‘’'—]+", text_of(xm.group(1))):
            k = norm(w)
            if len(k) > 2:
                exw[k][idx] += 1
    eng.append(english_segments(p))


def dedup(lst):
    seen, out = set(), []
    for x in lst:
        key = json.dumps(x)
        if key not in seen:
            seen.add(key); out.append(x)
    return out


# resolve links to entry numbers
def fix_links(h):
    return re.sub(r'<a href="#([^"]+)">',
                  lambda m: f'<a data-e="{ids[m.group(1)]}">' if m.group(1) in ids else '<a>', h)


for e in entries:
    e[0] = fix_links(e[0])

# English: store per entry list of [labelIndex?, gloss]; keep label only if not head
eng_out = []
for i, segs in enumerate(eng):
    row, cur = [], ''
    for lab, g in segs:
        if lab != cur:
            row.append([lab]); cur = lab
        row.append(g)
    eng_out.append(row)

# example index: only keep reasonably specific words
ex_out = {}
for k, c in exw.items():
    if len(c) <= 25:
        ex_out[k] = [i for i, _ in c.most_common()]

db = {
    'e': entries,
    'h': {k: v for k, v in head.items()},
    's': {k: dedup([list(x) for x in v]) for k, v in sub.items()},
    'd': {k: dedup([list(x) for x in v]) for k, v in der.items() if k not in head},
    'v': {k: sorted(set(v)) for k, v in var.items() if k not in head},
    'x': ex_out,
    'g': eng_out,
}
json.dump(db, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('entries', len(entries), 'heads', len(head), 'sub', len(sub), 'der', len(db['d']),
      'var', len(db['v']), 'ex', len(ex_out), 'ids', len(ids))
