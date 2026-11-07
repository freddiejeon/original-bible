"""히브리어·그리스어 단어를 로마자와 한글 발음으로 바꾼다.

히브리어: 학습용 표준 읽기. 중복 자음은 한 번만 표기한다.
그리스어: 에라스무스식.
"""
import hashlib
import re
import unicodedata as ud

# ---------- 공통: 음소 토큰 → 한글 ----------
# 토큰: ('C', 로마자, 한글키) 또는 ('V', 로마자, 모음키 목록)
ONSET = {'g': 0, 'n': 2, 'd': 3, 'r': 5, 'l': 5, 'm': 6, 'b': 7, 's': 9, '': 11,
         'z': 12, 'ts': 14, 'k': 15, 't': 16, 'p': 17, 'h': 18, 'y': 11, 'sh': 9}
CODA = {'n': 4, 'l': 8, 'm': 16, 'ng': 21}
CLUSTER_L = {'프': '플', '크': '클', '브': '블', '그': '글', '스': '슬', '쉬': '쉴', '츠': '츨', '드': '들', '르': '를', '트': '틀', '즈': '즐', '흐': '흘'}
JUNG = {'a': 0, 'e': 5, 'o': 8, 'u': 13, 'i': 20, 'wi': 16, 'yu': 17}
Y_JUNG = {'a': 2, 'e': 7, 'o': 12, 'u': 17, 'i': 20, 'wi': 16, 'yu': 17}
LONE = {'b': '브', 'g': '그', 'd': '드', 'z': '즈', 'k': '크', 'p': '프', 't': '트', 'ts': '츠',
        'r': '르', 's': '스', 'h': '흐', 'sh': '쉬', 'y': '이', '': '', 'l': '을', 'n': '은', 'm': '음'}


def _syl(on, jung, coda=0):
    return 0xAC00 + on * 588 + jung * 28 + coda


def to_hangul(tokens):
    out = []  # 코드포인트 또는 문자열
    i, n = 0, len(tokens)
    while i < n:
        kind, _, key = tokens[i]
        if kind == 'C':
            nxt = tokens[i + 1] if i + 1 < n else None
            if nxt and nxt[0] == 'V':
                vowels = nxt[2]
                # 모음 사이의 l은 앞 음절에 ㄹ 받침을 더한다: 엘로힘, 알레테이아
                if key == 'l' and out and isinstance(out[-1], int) and (out[-1] - 0xAC00) % 28 == 0:
                    out[-1] += 8
                elif key == 'l' and out and out[-1] in CLUSTER_L:   # 플, 클, 블: 플레로마
                    out[-1] = CLUSTER_L[out[-1]]
                jung = 16 if key == 'sh' and vowels[0] == 'i' else (Y_JUNG if key in ('y', 'sh') else JUNG)[vowels[0]]
                out.append(_syl(ONSET[key], jung))
                out += [_syl(11, JUNG[v]) for v in vowels[1:]]
                i += 2
                continue
            nxt_key = nxt[2] if nxt and nxt[0] == 'C' else None
            open_prev = out and isinstance(out[-1], int) and (out[-1] - 0xAC00) % 28 == 0
            if key in CODA and open_prev:
                out[-1] += CODA[key]
            elif key == 'l' and out and isinstance(out[-1], int) and (out[-1] - 0xAC00) % 28 == 8:
                pass                                   # 겹자음 ll: 끝 ㄹ 하나로 줄인다
            elif key == nxt_key and key == 's':
                pass                                   # 겹자음 ss: 메시아스
            elif key == nxt_key and key in ('b', 'p') and open_prev:
                out[-1] += 17                          # 겹자음 bb, pp: 랍비, 필립포스
            elif key == 'y':
                out.append(_syl(11, 20))
            elif LONE[key]:
                out.append(LONE[key])
            i += 1
        else:
            out += [_syl(11, JUNG[v]) for v in key]
            i += 1
    return ''.join(chr(c) if isinstance(c, int) else c for c in out)


def to_latin(tokens):
    return ''.join(t[1] for t in tokens)


# ---------- 히브리어 ----------
SHEVA, HSEG, HPAT, HQAM, HIRIQ, TSERE, SEGOL, PATAH, QAMETS, HOLAM, HOLAM_H, QUBUTS = (
    'ְ', 'ֱ', 'ֲ', 'ֳ', 'ִ', 'ֵ', 'ֶ', 'ַ', 'ָ', 'ֹ', 'ֺ', 'ֻ')
QATAN, DAGESH, SHIN, SIN = 'ׇ', 'ּ', 'ׁ', 'ׂ'
VOWELS = {HSEG: 'e', HPAT: 'a', HQAM: 'o', HIRIQ: 'i', TSERE: 'e', SEGOL: 'e', PATAH: 'a',
          QAMETS: 'a', HOLAM: 'o', HOLAM_H: 'o', QUBUTS: 'u', QATAN: 'o'}
LONG_V = {QAMETS, TSERE, HOLAM, HOLAM_H}
CONS = {'א': ("'", ''), 'ב': ('v', 'b'), 'ג': ('g', 'g'), 'ד': ('d', 'd'), 'ה': ('h', 'h'), 'ו': ('v', 'b'),
        'ז': ('z', 'z'), 'ח': ('ch', 'h'), 'ט': ('t', 't'), 'י': ('y', 'y'), 'כ': ('kh', 'k'), 'ך': ('kh', 'k'),
        'ל': ('l', 'l'), 'מ': ('m', 'm'), 'ם': ('m', 'm'), 'נ': ('n', 'n'), 'ן': ('n', 'n'), 'ס': ('s', 's'),
        'ע': ("'", ''), 'פ': ('f', 'p'), 'ף': ('f', 'p'), 'צ': ('ts', 'ts'), 'ץ': ('ts', 'ts'), 'ק': ('q', 'k'),
        'ר': ('r', 'r'), 'ת': ('t', 't')}
HARD = {'ב': 'b', 'כ': 'k', 'ך': 'k', 'פ': 'p', 'ף': 'p'}
BEGAD = 'בגדכךפףת'


def _he_letters(word):
    letters = []
    for ch in ud.normalize('NFD', word):
        if ch in CONS or ch == 'ש':
            letters.append({'c': ch, 'm': set()})
        elif letters and 'ְ' <= ch <= 'ׇ':
            letters[-1]['m'].add(ch)
    return letters


def hebrew(word, info=None, force=None):
    """모음 부호가 붙은 히브리어 단어(접두사 구분 '/' 없이)를 토큰으로 바꾼다.

    force: {글자 번호: 'o' | 'a' | 'e'}. 형태 분석으로 정한 읽기(카메츠 하투프 o, 긴 카메츠 a, 소리 나는 슈와 e)를
    규칙보다 앞세운다. 번호는 자음 글자 기준(0부터)이다.
    """
    L = _he_letters(word)
    n = len(L)
    # 하나님의 이름은 기록된 자음대로 읽지 않고 전통 읽기를 적는다
    if n >= 4 and ''.join(x['c'] for x in L[-4:]) == 'יהוה':
        if HIRIQ in L[-2]['m']:
            return hebrew(word[:word.index('י')]) + hebrew('אֱלֹהִים')
        prefix = hebrew(word[:word.index('י')]) if n > 4 else []
        rest = [('C', 'd', 'd'), ('V', 'o', ['o']), ('C', 'n', 'n'), ('V', 'a', ['a']), ('V', 'i', ['i'])]
        return prefix + rest if prefix and prefix[-1][1] == 'a' else prefix + [('V', 'a', ['a'])] + rest
    # 1단계: 글자별 역할 판별 (모음 문자, 묵음)
    for i, x in enumerate(L):
        c, m = x['c'], x['m']
        prev = L[i - 1] if i else None
        prev_vowel = prev and any(v in prev['m'] for v in VOWELS)
        x['v'] = next((VOWELS[v] for v in VOWELS if v in m), None)
        x['raw_v'] = next((v for v in VOWELS if v in m), None)
        x['silent'] = False
        if c == 'ו' and i == 0 and DAGESH in m and not x['v'] and SHEVA not in m:   # 접속사 슈렉 וּ
            x['init_u'] = True
        elif c == 'ו' and not m and prev and HIRIQ in prev['m'] and i == n - 2 and L[i + 1]['c'] == 'א':  # 모세오경의 הִוא (히)
            x['silent'] = True
        elif c == 'ו' and i and not prev_vowel and not (prev and prev.get('silent')):
            if DAGESH in m and not x['v'] and SHEVA not in m:      # 슈렉
                prev['v2'] = 'u'
                x['silent'] = True
            elif HOLAM in m and DAGESH not in m:                   # 홀렘 와우
                prev['v2'] = 'o'
                x['silent'] = True
                x['v'] = None
        elif c == 'י' and i and not x['v'] and SHEVA not in m and DAGESH not in m and prev:
            if prev['m'] & {HIRIQ, TSERE, SEGOL}:                  # 모음 문자 요드
                x['silent'] = True
            elif QAMETS in prev['m'] and i == n - 2 and L[i + 1]['c'] == 'ו' and not L[i + 1]['m'] & {DAGESH, HOLAM}:  # -ָיו = -av (הָיוֹ 는 하요)
                x['silent'] = True
        elif c == 'ה' and i == n - 1 and not x['v'] and DAGESH not in m:
            x['silent'] = True
        elif c == 'א' and not x['v'] and SHEVA not in m:
            nx = L[i + 1] if i + 1 < n else None
            carries_vav = nx and nx['c'] == 'ו' and (HOLAM in nx['m'] or DAGESH in nx['m'])
            x['silent'] = not carries_vav

    # כָּל 의 카메츠는 짧은 o로 읽는다
    for i, x in enumerate(L):
        if x['c'] == 'כ' and QAMETS in x['m'] and i + 1 < n and L[i + 1]['c'] == 'ל' and i + 2 == n \
                and all(p['c'] in 'ובלהכמש' for p in L[:i]):
            x['v'] = 'o'
        # 원문에 표시되지 않은 카메츠 하투프: לְאָכְלָה (오클라), יָקְטָן (욕탄). 동사 אָכְלוּ (아켈루)는 제외
        nx, nx2 = (L[i + 1] if i + 1 < n else None), (L[i + 2] if i + 2 < n else None)
        for root in ('אכל', 'יקט', 'יקש', 'ערל', 'אזנ', 'עני', 'גפר', 'אמנה', 'בשמ', 'בצרה', 'מתנ', 'שלחך', 'צפנת', 'נקב', 'נכר', 'אשר', 'בטנ', 'יחנ', 'קדק'):
            if x['c'] == root[0] and QAMETS in x['m'] and nx and SHEVA in nx['m'] \
                    and ''.join(y['c'] for y in L[i:i + len(root)]) == root \
                    and not (root == 'אכל' and i + 3 < n and DAGESH in L[i + 3]['m']):
                x['v'] = 'o'
        # 전치사 뒤 부정사 + 접미사: לְהָרְגֶךָ (레호르게카), בְּבָרְחֲךָ (베보르하카), כְּשָׁמְעָם (케숌암)
        if i and QAMETS in x['m'] and nx and SHEVA in nx['m']                 and ''.join(y['c'] for y in L[i - 1:i + 3]) in ('להרג', 'בברח', 'כשמע', 'בשמע'):
            x['v'] = 'o'
        # 그돌라오멜: כְּדָרְלָעֹמֶר, 14:17은 슈와 없이 כְּדָרלָעֹמֶר
        if x['c'] == 'ד' and QAMETS in x['m'] and ''.join(y['c'] for y in L[i:i + 3]) == 'דרל':
            x['v'] = 'o'
        if QAMETS in x['m'] and nx:
            # 하텝 카메츠 앞: אָהֳלוֹ (오홀로), מָחֳרָת (모호라트)
            if HQAM in nx['m']:
                x['v'] = 'o'
            # 휴지형 완료 어미 앞은 카메츠 그대로, 슈와만 묵음: אָכָלְתָּ (아칼타), יָדָעְתִּי (야다티), וָאָרְדְּ (바아르드)
            elif SHEVA in nx['m'] and nx2 and (nx2['c'] == 'ת' and DAGESH in nx2['m'] and ''.join(y['c'] for y in L[i + 3:]) in ('', 'י', 'ם', 'ן')
                                               or i + 2 == n - 1 and SHEVA in nx2['m']):
                nx['closed'] = True
            # 휴지형 완료 1인칭 복수: שָׁמָעְנוּ (샤마누). 어근 눈인 וְיֵאָמְנוּ 는 제외
            elif SHEVA in nx['m'] and i and i + 3 == n - 1 and nx2['c'] == 'נ' and (L[i - 1]['m'] & {QAMETS, PATAH} or ''.join(y['c'] for y in L).endswith('מהמהנו')):
                nx['closed'] = True
            # 닫힌 음절(슈와 뒤 약한 다게쉬) 또는 부정사 + 3남단 접미사: הָפְכִּי (호프키), שָׁמְעוֹ (숌오)
            elif SHEVA in nx['m'] and nx2 and (nx2['c'] in BEGAD and DAGESH in nx2['m']
                                               or i + 3 == n - 1 and L[i + 3]['c'] == 'ו' and HOLAM in L[i + 3]['m'] and not (i and TSERE in L[i - 1]['m'])):
                x['v'] = 'o'
        # 끝 겹슈와의 앞 슈와는 묵음: צָחָקְתְּ, וַתֵּבְךְּ / 휴지형 אֲנָחְנוּ (아나흐누)
        x['closed'] = x.get('closed') or (SHEVA in x['m'] and i == n - 2 and SHEVA in L[n - 1]['m']) \
            or (x['c'] == 'ח' and ''.join(y['c'] for y in L).endswith('נחנו'))
        # 약한 다게쉬 앞 슈와는 묵음: קָטֹנְתִּי (카톤티). 어두 슈와와 וּשְׁתֵּי 는 제외
        if i and SHEVA in x['m'] and DAGESH not in x['m'] and nx and nx['c'] in BEGAD and DAGESH in nx['m'] and not L[i - 1].get('init_u'):
            x['closed'] = True
    # 와우 연속 미완료 중공 동사의 끝 카메츠는 짧은 o: וַיָּקָם (바야콤)
    if n == 4 and L[0]['c'] == 'ו' and PATAH in L[0]['m'] and QAMETS in L[1]['m'] and DAGESH in L[1]['m'] and QAMETS in L[2]['m']:
        L[2]['v'] = 'o'
    cons = ''.join(x['c'] for x in L)
    # 휴지형 카메츠 뒤라도 닫힌 음절: מִלְמָעְלָה (밀마알라), וְיָשְׁפֵה (베야쉬페)
    for i, x in enumerate(L):
        if SHEVA in x['m'] and i and QAMETS in L[i - 1]['m'] and cons[i - 1:i + 3] in ('מעלה', 'ישפה'):
            x['closed'] = True
    # 두 강세 형태 פָּנָֽיַ: 끝 요드의 파타는 읽지 않는다 (파나이)
    if n >= 3 and cons[-1] == 'י' and PATAH in L[-1]['m'] and QAMETS in L[-2]['m']:
        L[-1]['v'] = None
    for i, v in (force or {}).items():
        if v == 'e':
            L[i]['vocal'] = True
        else:
            L[i]['v'] = v

    if info is not None:
        info.extend(L)

    # 2단계: 토큰 생성
    tokens = []
    last_vowel, last_sheva_silent = None, False
    for i, x in enumerate(L):
        c, m = x['c'], x['m']
        if x.get('init_u'):
            tokens.append(('V', 'u', ['u']))
            last_vowel = 'long'
            continue
        if x['silent']:
            # 묵음 글자는 앞 음절 모음의 길이만 남긴다
            if c in 'וי':
                last_vowel = 'long'
            continue
        dag = DAGESH in m
        if c == 'ש':
            lat = key = 's' if SIN in m else 'sh'
        elif c in HARD and (dag):
            lat = key = HARD[c]
        else:
            lat, key = CONS[c]
        vowel = x['v']
        # 뒤에 묵음 글자만 남았으면 끝 글자로 본다: שָׁוְא (샤브)
        final = i == n - 1 or (i == n - 2 and L[n - 1]['silent'] and L[n - 1]['c'] == 'א')
        if not vowel and SHEVA in m and not final:
            vocal = x.get('vocal') or not x['closed'] and (
                i == 0
                or (dag and last_vowel is not None and tokens)   # 강 다게쉬
                or (i + 1 < n and L[i + 1]['c'] == c)            # 같은 자음 사이: 힌네니 → 히네니
                or (c == 'י' and L[i - 1]['c'] == 'ה' and PATAH in L[i - 1]['m'] and (i == 1 or i == 2 and L[0]['c'] == 'ו'))   # 정관사 뒤 הַיְ, וְהַיְ
                or (last_vowel == 'long' and c != 'י')          # 카메츠 뒤 요드 슈와는 묵음: 라일라, 하이타
                or last_sheva_silent
                or (c == 'י' and i == 1 and L[0]['c'] == 'ו')   # 와우 연속형 וַיְ
            )
            # 카메츠 뒤 슈와 중 어근 닫힌 음절 예외는 데이터에서 별도 점검
            if vocal:
                vowel = 'e'
                last_sheva_silent = False
            else:
                last_sheva_silent = True
        else:
            last_sheva_silent = False

        # 끝 글자 푸르티브 파타 (ַח, ַע, ַהּ)
        if final and PATAH in m and c in 'חעה':
            tokens.append(('V', 'a', ['a']))
            if c != 'ע':
                tokens.append(('C', lat, key))
            last_vowel = 'short'
            continue
        # 첫 글자 알레프·아인의 ' 은 적지 않는다
        if lat == "'" and not tokens:
            lat = ''
        if lat == "'" and not vowel and not x.get('v2'):
            continue
        tokens.append(('C', lat, key))
        v2 = x.get('v2')
        if v2:
            tokens.append(('V', v2, [v2]))
            last_vowel = 'long'
        elif vowel:
            tokens.append(('V', vowel, [vowel]))
            raw = x['raw_v']
            last_vowel = 'long' if raw in LONG_V and vowel != 'o' or raw in (HOLAM, HOLAM_H) else 'short'
            if SHEVA in m:
                last_vowel = 'vocal'
        elif SHEVA not in m or final:
            pass
    return tokens


def clean(word):
    """강세·표시 부호와 막켑을 뺀 형태. 음성 파일의 기준이다."""
    return ud.normalize('NFC', re.sub('[͏֑-ֽ֯־ֿ׀׃-׆‍⁠/]', '', ud.normalize('NFD', word)))


def audio_name(word):
    return hashlib.sha1(clean(word).encode()).hexdigest()[:12]


def spoken(word, force=None):
    """음성 합성에 넘길 글자. 하나님의 이름은 전통 읽기로, 카메츠 하투프는 현대 음성이 오로 읽도록 홀렘으로 바꾼다."""
    w = ud.normalize('NFD', clean(word))
    L = _he_letters(w)
    if ''.join(x['c'] for x in L).endswith('יהוה'):
        pre = w[:w.index('י')]
        if HIRIQ in L[-2]['m']:
            return ud.normalize('NFC', pre + 'אֱלֹהִים')
        return ud.normalize('NFC', pre + ('אדֹנָי' if PATAH in pre else 'אֲדֹנָי'))
    info = []
    hebrew(w, info, force)
    out, i = [], -1
    for ch in w:
        if ch in CONS or ch == 'ש':
            i += 1
        if ch == PATAH and i == len(info) - 1 and info[i]['c'] == 'י' and info[i]['v'] is None:
            continue                                   # פָּנָֽיַ 의 끝 파타
        out.append(HOLAM if ch in (QAMETS, QATAN) and info[i]['v'] == 'o' else ch)
    return ud.normalize('NFC', ''.join(out))


# ---------- 그리스어 ----------
G_V = {'α': ('a', 'a'), 'ε': ('e', 'e'), 'η': ('ē', 'e'), 'ι': ('i', 'i'), 'ο': ('o', 'o'), 'υ': ('y', 'wi'), 'ω': ('ō', 'o')}
G_D = {'αι': ('ai', ['a', 'i']), 'ει': ('ei', ['e', 'i']), 'οι': ('oi', ['o', 'i']), 'ου': ('ou', ['u']),
       'αυ': ('au', ['a', 'u']), 'ευ': ('eu', ['yu']), 'ηυ': ('ēu', ['e', 'u']), 'υι': ('yi', ['wi'])}
G_C = {'β': ('b', 'b'), 'γ': ('g', 'g'), 'δ': ('d', 'd'), 'ζ': ('z', 'z'), 'θ': ('th', 't'), 'κ': ('k', 'k'),
       'λ': ('l', 'l'), 'μ': ('m', 'm'), 'ν': ('n', 'n'), 'π': ('p', 'p'), 'ρ': ('r', 'r'), 'σ': ('s', 's'),
       'ς': ('s', 's'), 'τ': ('t', 't'), 'φ': ('ph', 'p'), 'χ': ('ch', 'k')}
ROUGH, DIAER = '̔', '̈'


def greek(word):
    chars = []
    for ch in ud.normalize('NFD', word.lower()):
        if ud.category(ch) == 'Mn':
            if chars:
                chars[-1][1].add(ch)
        elif ch in G_V or ch in G_C or ch in 'ξψ':
            chars.append([ch, set()])
    tokens, i, n = [], 0, len(chars)
    while i < n:
        c, m = chars[i]
        nxt = chars[i + 1] if i + 1 < n else None
        if c in G_V:
            pair = c + nxt[0] if nxt else ''
            if pair in G_D and DIAER not in nxt[1]:
                if ROUGH in m or ROUGH in nxt[1]:
                    tokens.append(('C', 'h', 'h'))
                lat, vs = G_D[pair]
                tokens.append(('V', lat, vs))
                i += 2
                continue
            if ROUGH in m:
                tokens.append(('C', 'h', 'h'))
            elif c == 'ι' and i == 0 and nxt and nxt[0] in G_V:   # 첫머리 반모음: 예수스, 요안네스
                tokens.append(('C', 'i', 'y'))
                i += 1
                nc = nxt[0] + (chars[i + 1][0] if i + 1 < n else '')
                if nc in G_D:
                    lat, vs = G_D[nc]
                    tokens.append(('V', lat, vs))
                    i += 2
                else:
                    lat, key = G_V[nxt[0]]
                    tokens.append(('V', lat, [key]))
                    i += 1
                continue
            lat, key = G_V[c]
            tokens.append(('V', lat, [key]))
        elif c == 'ξ':
            tokens += [('C', 'x', 'k'), ('C', '', 's')]
        elif c == 'ψ':
            tokens += [('C', 'ps', 'p'), ('C', '', 's')]
        elif c == 'γ' and nxt and nxt[0] in 'γκχξ':
            tokens.append(('C', 'n', 'ng'))
        elif c == 'ρ' and ROUGH in m:
            tokens.append(('C', 'rh', 'r'))
        else:
            tokens.append(('C', *G_C[c]))
        i += 1
    return tokens


if __name__ == '__main__':
    tests = [
        (hebrew, 'בְּרֵאשִׁית', 'bereshit', '베레쉬트'), (hebrew, 'בָּרָא', 'bara', '바라'),
        (hebrew, 'אֱלֹהִים', 'elohim', '엘로힘'), (hebrew, 'אֵת', 'et', '에트'),
        (hebrew, 'הַשָּׁמַיִם', 'hashamayim', '하샤마임'), (hebrew, 'וְאֵת', "ve'et", '베에트'),
        (hebrew, 'הָאָרֶץ', "ha'arets", '하아레츠'), (hebrew, 'וַיֹּאמֶר', 'vayomer', '바요메르'),
        (hebrew, 'יְהִי', 'yehi', '예히'), (hebrew, 'אוֹר', 'or', '오르'), (hebrew, 'וַיְהִי', 'vayehi', '바예히'),
        (hebrew, 'טוֹב', 'tov', '토브'), (hebrew, 'רָקִיעַ', 'raqia', '라키아'), (hebrew, 'יוֹם', 'yom', '욤'),
        (hebrew, 'לַיְלָה', 'layla', '라일라'), (hebrew, 'עֶרֶב', 'erev', '에레브'), (hebrew, 'בֹקֶר', 'voqer', '보케르'),
        (hebrew, 'רוּחַ', 'ruach', '루아흐'), (hebrew, 'כָּל', 'kol', '콜'), (hebrew, 'מַיִם', 'mayim', '마임'),
        (greek, 'ἐν', 'en', '엔'), (greek, 'ἀρχῇ', 'archē', '아르케'), (greek, 'ἦν', 'ēn', '엔'),
        (greek, 'ὁ', 'ho', '호'), (greek, 'λόγος', 'logos', '로고스'), (greek, 'καὶ', 'kai', '카이'),
        (greek, 'πρὸς', 'pros', '프로스'), (greek, 'θεόν', 'theon', '테온'), (greek, 'ἄνθρωπος', 'anthrōpos', '안트로포스'),
        (greek, 'ἀλήθεια', 'alētheia', '알레테이아'), (greek, 'Χριστός', 'christos', '크리스토스'),
        (greek, 'ἄγγελος', 'angelos', '앙겔로스'), (greek, 'εὐθὺς', 'euthys', '유튀스'), (greek, 'οὐ', 'ou', '우'),
        (greek, 'υἱός', 'hyios', '휘오스'), (greek, 'Ἰησοῦς', 'iēsous', '예수스'), (greek, 'Ἰωάννης', 'iōannēs', '요안네스'),
        (greek, 'πνεῦμα', 'pneuma', '프뉴마'), (greek, 'πλήρης', 'plērēs', '플레레스'), (greek, 'ῥαββί', 'rhabbi', '랍비'),
        (greek, 'Φίλιππος', 'philippos', '필립포스'), (greek, 'Μεσσίαν', 'messian', '메시안'), (greek, 'εὑρίσκει', 'heuriskei', '휴리스케이'),
        (greek, 'βασιλεὺς', 'basileus', '바실류스'), (greek, 'ἀλλ’', 'all', '알'), (greek, 'σὰρξ', 'sarx', '사르크스'),
        (hebrew, 'יְהוָה', 'adonai', '아도나이'), (hebrew, 'לַיהוָה', 'ladonai', '라도나이'), (hebrew, 'הַכְּרֻבִים', 'hakeruvim', '하케루빔'),
        (hebrew, 'הִנְנִי', 'hineni', '히네니'), (hebrew, 'הִוא', 'hi', '히'), (hebrew, 'וַיָּקָם', 'vayaqom', '바야콤'),
        (hebrew, 'יָקְטָן', 'yoqtan', '요크탄'), (hebrew, 'הַיְבוּסִי', 'hayevusi', '하예부시'), (hebrew, 'לְאָכְלָה', "le'okhla", '레오클라'),
        (hebrew, 'וּבֵין', 'uven', '우벤'), (hebrew, 'וּנְקֵבָה', 'uneqeva', '우네케바'), (hebrew, 'לָיְלָה', 'layla', '라일라'),
        (hebrew, 'וְהָיוּ', 'vehayu', '베하유'), (hebrew, 'לְאָכְלָה', "le'okhla", '레오클라'), (hebrew, 'וּבְכָל', 'uvekhol', '우베콜'),
        (hebrew, 'לִמְאוֹרֹת', "lim'orot", '림오로트'), (hebrew, 'זַרְעוֹ', "zar'o", '자르오'), (greek, 'ἑαυτοῦ', 'heautou', '헤아우투'),
        (hebrew, 'אָהֳלוֹ', 'oholo', '오홀로'), (hebrew, 'מִמָּחֳרָת', 'mimochorat', '미모호라트'), (hebrew, 'לְאָרְכָּהּ', "le'orkah", '레오르카흐'),
        (hebrew, 'הָפְכִּי', 'hofki', '호프키'), (hebrew, 'וּכְשָׁמְעוֹ', "ukheshom'o", '우케숌오'), (hebrew, 'בְּאָזְנֵי', "be'ozne", '베오즈네'),
        (hebrew, 'עָנְיֵךְ', 'onyekh', '온예크'), (hebrew, 'עָרְלָתוֹ', 'orlato', '오를라토'), (hebrew, 'גָּפְרִית', 'gofrit', '고프리트'),
        (hebrew, 'אָמְנָה', 'omna', '옴나'), (hebrew, 'יָקְשָׁן', 'yoqshan', '요크샨'), (hebrew, 'כְּדָרְלָעֹמֶר', "kedorla'omer", '케도를라오메르'),
        (hebrew, 'אָכְלוּ', 'akhelu', '아켈루'), (hebrew, 'אָכְלָם', 'okhlam', '오클람'), (hebrew, 'הָיוֹ', 'hayo', '하요'),
        (hebrew, 'צָחָקְתְּ', 'tsachaqt', '차하크트'), (hebrew, 'וַתֵּבְךְּ', 'vatevk', '바테브크'), (hebrew, 'אֲנָחְנוּ', 'anachnu', '아나흐누'),
        (hebrew, 'תִּשְׁלַח', 'tishlach', '티쉴라흐'), (hebrew, 'וְהָרְגוּ', 'veharegu', '베하레구'), (hebrew, 'אָכָלְתָּ', 'akhalta', '아칼타'),
        (hebrew, 'לֻקָּחְתָּ', 'luqachta', '루카흐타'), (hebrew, 'רָחְבָּהּ', 'rochbah', '로흐바흐'),
        (hebrew, 'יָדָעְתִּי', 'yadati', '야다티'), (hebrew, 'שָׁמָעְנוּ', 'shamanu', '샤마누'), (hebrew, 'קָטֹנְתִּי', 'qatonti', '카톤티'),
        (hebrew, 'כֻּתָּנְתּוֹ', 'kutonto', '쿠톤토'), (hebrew, 'וּשְׁתֵּי', 'ushete', '우셰테'), (hebrew, 'בָּשְׂמַת', 'bosmat', '보스마트'),
        (hebrew, 'לְהָרְגֶךָ', 'lehorgekha', '레호르게카'), (hebrew, 'כְּשָׁמְעָם', "keshom'am", '케숌암'), (hebrew, 'בָּטְנִים', 'botnim', '보트님'),
        (hebrew, 'נָחְנוּ', 'nachnu', '나흐누'), (hebrew, 'וְיֵאָמְנוּ', "veye'amenu", '베예아메누'), (hebrew, 'בְּהֵאָבְקוֹ', "behe'aveqo", '베헤아베코'),
        (hebrew, 'וָאָרְדְּ', "va'ard", '바아르드'), (hebrew, 'יָחְנְךָ', 'yochnekha', '요흐네카'), (hebrew, 'הִתְמַהְמָהְנוּ', 'hitmahmahnu', '히트마흐마흐누'),
        (hebrew, 'לַשָּׁוְא', 'lashav', '라샤브'), (hebrew, 'מִלְמָעְלָה', 'milmala', '밀말라'), (hebrew, 'וְיָשְׁפֵה', 'veyashfe', '베야쉬페'),
        (hebrew, 'פָּנָיַ', 'panay', '파나이'), (hebrew, 'וְהַיְבוּסִי', 'vehayevusi', '베하예부시'),
        # 형태 분석 힌트(build_data.pron_hints): 칼 부정사, 호팔, 표제어 o, 막켑, 분사의 긴 카메츠, 전치사+관사 뒤 요드
        (lambda w: hebrew(w, force={1: 'o'}), 'לְשָׁכְנִי', 'leshokhni', '레쇼크니'),
        (lambda w: hebrew(w, force={0: 'o'}), 'מָשְׁזָר', 'moshzar', '모쉬자르'),
        (lambda w: hebrew(w, force={0: 'o', 1: 'o'}), 'תָעָבְדֵם', "to'ovdem", '토오브뎀'),
        (lambda w: hebrew(w, force={0: 'o'}), 'חָכְמָה', 'chokhma', '호크마'),
        (lambda w: hebrew(w, force={1: 'o'}), 'שְׁמָר', 'shemor', '셰모르'),
        (lambda w: hebrew(w, force={1: 'a'}), 'מְשָׁרְתוֹ', 'meshareto', '메샤레토'),
        (lambda w: hebrew(w, force={1: 'e'}), 'בַּיְאֹר', "baye'or", '바예오르'),
    ]
    bad = 0
    for fn, w, lat, ko in tests:
        t = fn(w)
        got = (to_latin(t), to_hangul(t))
        if got != (lat, ko):
            bad += 1
            print('틀림', w, got, '기대', (lat, ko))
    if spoken('לְחָק', {1: 'o'}) != ud.normalize('NFC', 'לְחֹק') or spoken('פָּנָיַ') != ud.normalize('NFC', 'פָּנָי'):
        bad += 1
        print('틀림 spoken force')
    for w, want in [('אָהֳלוֹ', 'אֹהֳלוֹ'), ('כָּל־', 'כֹּל'), ('יְהוָה֙', 'אֲדֹנָי'), ('וַיהוָה', 'וַאדֹנָי'), ('יֱהוִה֙', 'אֱלֹהִים'), ('בָּרָ֣א', 'בָּרָא')]:
        if spoken(w) != ud.normalize('NFC', want):
            bad += 1
            print('틀림', w, spoken(w), '기대', want)
    print(f'{len(tests) + 7 - bad}/{len(tests) + 7} 통과')
