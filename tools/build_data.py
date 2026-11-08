"""공개 원본 자료를 앱용 데이터로 변환한다.

사용법: python build_data.py <원본 폴더> <출력 폴더>
원본 폴더: 책별 WLC xml(Gen.xml, Exod.xml…), 책별 MorphGNT txt(Jn.txt…), heb.js, grc.js, {korean,kjv}-{권}-{장}.json
"""
import json
import re
import sys
import unicodedata as ud
import xml.etree.ElementTree as ET
from pathlib import Path

import pron

RAW, OUT = Path(sys.argv[1]), Path(sys.argv[2])
HERE = Path(__file__).parent
GLOSS_PATH = HERE / 'glosses_ko.json'
GLOSS = json.loads(GLOSS_PATH.read_text(encoding='utf-8')) if GLOSS_PATH.exists() else {}

# ---------- 히브리어 형태 코드 ----------
H_STEM = {'q': '칼', 'N': '니팔', 'p': '피엘', 'P': '푸알', 'h': '히필', 'H': '호팔', 't': '히트파엘',
          'o': '폴렐', 'O': '폴랄', 'r': '히트폴렐', 'm': '포엘', 'M': '포알', 'Q': '칼 수동',
          'k': '팔렐', 'K': '풀랄', 'l': '필펠', 'L': '폴팔', 'f': '히트팔펠', 'D': '니트파엘', 'j': '페알랄', 'i': '필렐',
          'u': '호트파알', 'c': '티프일', 'v': '히슈타펠', 'w': '니트팔렐', 'y': '니트포엘', 'z': '히트포엘'}
H_CONJ = {'p': '완료', 'q': '와우 연속 완료', 'i': '미완료', 'w': '와우 연속 미완료', 'h': '권유형', 'j': '지시형',
          'v': '명령형', 'r': '능동 분사', 's': '수동 분사', 'a': '부정사 절대형', 'c': '부정사 연계형'}
H_P = {'1': '1인칭', '2': '2인칭', '3': '3인칭'}
H_G = {'m': '남성', 'f': '여성', 'c': '공성', 'b': '양성'}
H_N = {'s': '단수', 'p': '복수', 'd': '쌍수'}
H_S = {'a': '절대형', 'c': '연계형', 'd': '한정형'}
H_ADJ = {'a': '형용사', 'c': '기수사', 'o': '서수사', 'g': '민족 형용사'}
H_PRON = {'d': '지시대명사', 'f': '부정대명사', 'i': '의문대명사', 'p': '인칭대명사', 'r': '관계대명사'}
H_PART = {'a': '긍정 불변화사', 'd': '정관사', 'e': '권유 불변화사', 'i': '의문 불변화사', 'j': '감탄사',
          'm': '지시 불변화사', 'n': '부정어', 'o': '목적격 표지', 'r': '관계사'}
H_SUF = {'d': '방향 접미사', 'h': '첨가 헤', 'n': '첨가 눈', 'p': '대명사 접미사'}
H_PREFIX = {'b': ('전치사 베', '~에'), 'c': ('접속사 베', '그리고'), 'd': ('정관사 하', '그'), 'k': ('전치사 케', '~처럼'),
            'l': ('전치사 레', '~에게'), 'm': ('전치사 민', '~로부터'), 's': ('관계사 쉐', '~하는'), 'i': ('의문사 하', '~인가')}


def pgn(code):
    """인칭·성·수 문자열을 차례로 풀어 쓴다."""
    parts = [H_P.get(code[0])] if code[:1] in H_P else []
    rest = code[1:] if parts else code
    if rest[:1] in H_G:
        parts.append(H_G[rest[0]])
    if rest[1:2] in H_N:
        parts.append(H_N[rest[1]])
    return parts


def hebrew_morph(code):
    """형태 코드 조각 하나를 (품사, [분석]) 으로 바꾼다."""
    pos, rest = code[0], code[1:]
    if pos == 'V':
        stem, conj, tail = rest[0], rest[1], rest[2:]
        out = [H_STEM[stem], H_CONJ[conj]]
        if conj in 'rs':       # 분사: 성·수·상태
            out += [H_G.get(tail[:1]), H_N.get(tail[1:2]), H_S.get(tail[2:3])]
        elif conj in 'ac':
            pass
        else:
            out += pgn(tail)
        return '동사', [x for x in out if x]
    if pos == 'N':
        kind = rest[0]
        if kind == 'p':
            return '고유명사', [x for x in (H_G.get(rest[1:2]), H_N.get(rest[2:3])) if x]
        label = {'c': '명사', 'g': '민족 명사'}[kind]
        return label, [x for x in (H_G.get(rest[1:2]), H_N.get(rest[2:3]), H_S.get(rest[3:4])) if x]
    if pos == 'A':
        return H_ADJ[rest[0]], [x for x in (H_G.get(rest[1:2]), H_N.get(rest[2:3]), H_S.get(rest[3:4])) if x]
    if pos == 'P':
        return H_PRON[rest[0]], pgn(rest[1:])
    if pos == 'R':
        return '전치사', ['정관사 결합'] if rest[:1] == 'd' else []
    if pos == 'C':
        return '접속사', []
    if pos == 'D':
        return '부사', []
    if pos == 'T':
        return H_PART[rest[0]], []
    if pos == 'S':
        return H_SUF[rest[0]], pgn(rest[1:])
    raise ValueError(code)


SUFFIX_GLOSS = {'1cs': '나의', '2ms': '너의', '2fs': '너의', '3ms': '그의', '3fs': '그녀의', '1cp': '우리의',
                '2mp': '너희의', '2fp': '너희의', '3mp': '그들의', '3fp': '그들의'}


def load_js_dict(path, var):
    src = path.read_text(encoding='utf-8')
    return json.JSONDecoder().raw_decode(src, src.index('{', src.index(f'var {var}')))[0]


LEX_HE = load_js_dict(RAW / 'heb.js', 'strongsHebrewDictionary')
LEX_GR = load_js_dict(RAW / 'grc.js', 'strongsGreekDictionary')
used, missing = {}, {}


def lex_entry(sid, lex):
    e = lex[sid]
    used[sid] = {'lemma': e.get('lemma'), 'def': e.get('strongs_def') or e.get('kjv_def'), 'kjv': e.get('kjv_def'),
                 'ko': GLOSS.get(sid, '')}
    if sid not in GLOSS:
        missing[sid] = f"{e.get('lemma')} | {(e.get('strongs_def') or '').strip()[:60]} | {(e.get('kjv_def') or '')[:40]}"
    return GLOSS.get(sid, '')


def strip_marks(t):
    return ''.join(c for c in ud.normalize('NFD', t) if not ('֑' <= c <= '֯' or c in 'ֽֿ‍⁠'))


# OSHB에서 형태 부호와 표제어 수가 맞지 않는 곳: 삿 8:24 מִכֶּם, 13:14 צִוִּיתִיהָ, 21:24 הַהִיא
OSHB_FIX = {('HR/Sp2mp', 'm/4480 a'): ('HR/Sp2mp', '4480 a'), ('HVpp1cs/Pp3fs', '6680'): ('HVpp1cs/Sp3fs', '6680'),
            ('HTd/Sp3fs', 'd/1931'): ('HTd/Pp3fs', 'd/1931')}


def hebrew_word(el):
    text = ''.join(el.itertext())
    pieces = text.split('/')
    morph, lemma = OSHB_FIX.get((el.get('morph'), el.get('lemma')), (el.get('morph'), el.get('lemma')))
    assert morph[0] in 'HA', morph
    codes = morph[1:].split('/')
    lemmas = [x.strip() for x in lemma.split('/')]
    segs, glosses, li = [], [], 0
    for i, code in enumerate(codes):
        if code == 'Sp3fs' and i < len(pieces) and strip_marks(pieces[i]).endswith('ךְ'):   # OSHB 오표기 (창 24:17, 24:23)
            code = 'Sp2fs'
        pos, parse = hebrew_morph(code)
        seg = {'x': pieces[i] if i < len(pieces) else '', 'pos': pos, 'parse': parse}
        if code[0] == 'S':
            seg['ko'] = SUFFIX_GLOSS.get(code[2:5], '')
            if code[1] == 'p' and seg['ko']:
                glosses.append(seg['ko'])
        else:
            lem = lemmas[li] if li < len(lemmas) else ''
            li += 1
            if lem in H_PREFIX:
                seg['name'], seg['ko'] = H_PREFIX[lem]
                glosses.append(seg['ko'])
            else:
                sid = 'H' + re.match(r'\+?(\d+)', lem).group(1)
                seg['sid'] = sid
                seg['ko'] = lex_entry(sid, LEX_HE)
                glosses.append(seg['ko'])
        segs.append(seg)
    plain = text.replace('/', '')
    word = {'t': plain, 'segs': segs, 'gl': ' '.join(g.split(',')[0] for g in glosses if g),
            '_ctx': (pieces, codes, [s.get('sid') for s in segs])}
    set_pron(word)
    if morph[0] == 'A':
        word['note'] = '아람어입니다. 라반이 쓴 말로, 야곱이 히브리어로 부른 갈르엣과 같은 뜻인 "증거의 무더기"입니다.'
    if any(s.get('sid') == 'H3068' for s in segs):
        word['note'] = '하나님의 이름입니다. 유대 전통은 이 이름을 소리 내지 않고 아도나이(주)로 읽었고, 개역 성경은 여호와로 옮깁니다.'
    if any(s.get('sid') == 'H3069' for s in segs):
        word['note'] = '하나님의 이름입니다. 바로 앞에 아도나이(주)가 있으면 겹치지 않도록 엘로힘으로 읽었고, 개역 성경은 여호와로 옮깁니다.'
    return word


# 카메츠+슈와가 늘 카메츠 하투프(o)인 낱말: 첫 어근 글자의 카메츠를 o로 읽는다
HATUF_SID = {'H6944', 'H2451', 'H5797', 'H2706', 'H3801', 'H4888', 'H4893', 'H7141', 'H7145', 'H2670', 'H6195', 'H70', 'H551'}
O_MARKS = {pron.HOLAM, pron.HOLAM_H, pron.QATAN, pron.HQAM, pron.QUBUTS}


def lemma_has_o(sid, letters, j):
    """표제어의 같은 자리 글자(j번째)가 o 모음을 가지는가: חֹק, עֹז, קִנָּמוֹן. דֹּדָתְךָ 의 둘째 ד 는 아니다"""
    lem = pron._he_letters(LEX_HE[sid].get('lemma') or '') if sid in LEX_HE else []
    if j < 0 or j >= len(lem) or j >= len(letters) or lem[j]['c'] != letters[j]['c']:
        return False
    return bool(lem[j]['m'] & O_MARKS) or j + 1 < len(lem) and lem[j + 1]['c'] == 'ו' and pron.HOLAM in lem[j + 1]['m']


# 칼 미완료가 a 모음인 동사: 접미사가 붙어도 카메츠가 길다 (יִשְׁאָלְךָ 이쉬알레카, יִירָשְׁךָ 이라셰카, אִיעָצְךָ 이아체카)
A_CLASS_SID = {'H7592', 'H3423', 'H3289'}


def pron_hints(pieces, codes, sids, maqqef):
    """형태 분석으로 카메츠 하투프 등 규칙만으로 정하기 어려운 읽기를 글자 번호별로 정한다."""
    force, start, keep_long = {}, 0, False
    nseg = len(pieces)
    for k, code in enumerate(codes):
        L = pron._he_letters(pieces[k]) if k < nseg else []
        sid = sids[k] if k < len(sids) else None
        qs = [j for j in range(len(L)) if pron.QAMETS in L[j]['m']]
        first_qs = next((j for j in qs if j + 1 < len(L) and pron.SHEVA in L[j + 1]['m']), None)
        if code[0] == 'V' and len(code) > 2:
            stem, conj = code[1], code[2]
            if stem == 'q' and conj == 'c' and first_qs is not None:          # 칼 부정사 연계형: לְשָׁכְנִי (레쇼크니)
                force[start + first_qs] = 'o'
            elif stem == 'q' and conj == 'v' and first_qs is not None:        # 칼 명령형 + 접미사: הָרְגֵנִי (호르게니)
                force[start + first_qs] = 'o'
            elif stem == 'q' and conj in 'iwhj' and first_qs is not None and k + 1 < len(codes) and codes[k + 1][0] == 'S' \
                    and sid not in A_CLASS_SID:
                force[start + first_qs] = 'o'                                 # 칼 미완료 + 접미사: נֶאֱסָרְךָ (네에소르카, 삿 15:13)
            elif stem in 'Hu' and qs and qs[0] == 0:                           # 호팔 접두 모음: מָשְׁזָר (모쉬자르)
                j = qs[0]
                force[start + j] = 'o'
                if j + 1 < len(L) and L[j + 1]['c'] in 'אהחע' and pron.QAMETS in L[j + 1]['m']:
                    force[start + j + 1] = 'o'                                # תָעָבְדֵם (토오브뎀)
            elif (conj in 'pqrs' or stem in 'Npt') and first_qs is not None:  # 분사·완료·니팔·피엘·히트파엘의 긴 카메츠: מְשָׁרְתוֹ, הִמָּכְרוֹ, לְשָׁרְתוֹ
                force[start + first_qs] = 'a'
            if conj in 'pqrs':
                keep_long = True
        elif code[0] in 'NA' and sid:
            if sid in HATUF_SID and qs and qs[0] == 0:                        # קָדְשֶׁךָ, קָֽדָשִׁים (코다쉼)
                force[start] = 'o'
            elif first_qs is not None and lemma_has_o(sid, L, first_qs):
                force[start + first_qs] = 'o'                                 # 표제어가 o인 명사: אָבְנַיִם (오브나임)
            if k == nseg - 1 and not lemma_has_o(sid, L, len(L) - 2):
                keep_long = True                                              # הָעָם־ 은 그대로 (하암)
        elif code[0] == 'D' and sid in HATUF_SID and qs and qs[0] == 0:      # 부사: אָמְנָם (옴남)
            force[start] = 'o'
        if code[0] == 'R' and code[1:2] == 'd' and k + 1 < nseg:               # 전치사+관사 뒤 요드 슈와: בַּיְאֹר (바예오르)
            nl = pron._he_letters(pieces[k + 1])
            if nl and nl[0]['c'] == 'י' and pron.SHEVA in nl[0]['m']:
                force[start + len(L)] = 'e'
        start += len(L)
    if maqqef and not keep_long:                                                                 # 막켑 앞 닫힌 끝 음절: חָק־ (호크), שְׁמָר־ (셰모르)
        L = pron._he_letters(''.join(pieces))
        n = len(L)
        if n >= 2 and pron.QAMETS in L[n - 2]['m'] and not any(v in L[n - 1]['m'] for v in pron.VOWELS)                 and not (L[n - 1]['c'] in 'אהו' and pron.DAGESH not in L[n - 1]['m']) and force.get(n - 2) != 'a':
            force[n - 2] = 'o'
    return force


def set_pron(word, maqqef=False):
    pieces, codes, sids = word['_ctx']
    plain = ''.join(pieces)
    force = pron_hints(pieces, codes, sids, maqqef)
    toks = pron.hebrew(plain, force=force)
    word['tr'], word['hg'] = pron.to_latin(toks), pron.to_hangul(toks)
    base = pron.hebrew(plain)
    # 읽기가 규칙만의 결과와 다르면 음성 파일도 따로 만든다
    if base != toks:
        word['sp'] = pron.spoken(plain, force)
        word['a'] = pron.audio_name(word['sp'])
    else:
        word.pop('sp', None)
        word['a'] = pron.audio_name(plain)


HEB_ROOTS = {}
OSIS = '{http://www.bibletechnologies.net/2003/OSIS/namespace}'


def to_translation_ref(book, c, v):
    """히브리어 성경의 장:절을 번역본(개역한글·KJV) 번호로 바꾼다."""
    if book == 'Gen':   # 히브리어 32:1이 번역본의 31:55이고 32장은 한 칸씩 당겨진다
        return (31, 55) if (c, v) == (32, 1) else (32, v - 1) if c == 32 else (c, v)
    if book == 'Exod':  # 히브리어 7:26~29가 번역본 8:1~4, 21:37이 22:1이다
        if c == 7 and v >= 26:
            return 8, v - 25
        if c == 21 and v == 37:
            return 22, 1
        return (c, v + 4) if c == 8 else (c, v + 1) if c == 22 else (c, v)
    if book == 'Lev':   # 히브리어 5:20~26이 번역본 6:1~7, 6장은 일곱 칸 밀린다
        if c == 5 and v >= 20:
            return 6, v - 19
        return (c, v + 7) if c == 6 else (c, v)
    if book == 'Num':   # 히브리어 17:1~15가 번역본 16:36~50, 25:19는 26:1 앞부분, 30:1이 29:40이다
        if c == 17:
            return (16, v + 35) if v <= 15 else (17, v - 15)
        if c == 25 and v == 19:
            return 26, 1
        if c == 30:
            return (29, 40) if v == 1 else (30, v - 1)
    if book == 'Deut':  # 히브리어 13:1이 번역본 12:32, 23:1이 22:30, 28:69가 29:1이다
        if c in (13, 23):
            return (c - 1, 32 if c == 13 else 30) if v == 1 else (c, v - 1)
        if c == 28 and v == 69:
            return 29, 1
        if c == 29:
            return 29, v + 1
    return c, v


def parse_hebrew(src, ch):
    if src not in HEB_ROOTS:
        HEB_ROOTS[src] = ET.parse(RAW / src).getroot()
    verses = {}
    for vs in HEB_ROOTS[src].iter(OSIS + 'verse'):
        osis = vs.get('osisID').split('.')
        he_ch, he_v = int(osis[1]), int(osis[2])
        v_ch, v_n = to_translation_ref(osis[0], he_ch, he_v)
        if v_ch != ch:
            continue
        words, ketiv = [], None
        for el in vs:
            tag = el.tag.split('}')[1]
            if tag == 'seg' and words and el.get('type') == 'x-maqqef':
                words[-1]['t'] += el.text
                set_pron(words[-1], maqqef=True)
            elif tag == 'w' and el.get('type') == 'x-ketiv':
                ketiv = ''.join(el.itertext()).replace('/', '')   # 기록된 글자. 읽는 형태(케레)를 본문에 쓴다
            elif tag == 'w':
                words.append(hebrew_word(el))
            elif tag == 'note' and el.get('type') == 'variant' and ketiv:
                for w in el.iter(OSIS + 'w'):
                    words.append(hebrew_word(w))
                words[-1]['note'] = f'기록된 글자(케티브)는 {ketiv}이고, 본문에는 읽는 형태(케레)를 보여 줍니다.'
                ketiv = None
        if (v_ch, v_n) != (he_ch, he_v):
            words[0]['note'] = f'히브리어 성경에서는 {he_ch}:{he_v}절입니다. 번역본과 절 번호가 다릅니다.'
        for w in words:
            w.pop('_ctx', None)
        if v_n in verses:   # 민수기 26:1은 히브리어 25:19와 26:1을 합친다
            words[0]['note'] = f'여기부터 히브리어 성경 {he_ch}:{he_v}절입니다. 앞부분은 히브리어 성경에서 앞 절입니다.'
        verses.setdefault(v_n, []).extend(words)
    return verses


# ---------- 그리스어 형태 코드 ----------
G_POS = {'A-': '형용사', 'C-': '접속사', 'D-': '부사', 'I-': '감탄사', 'N-': '명사', 'P-': '전치사', 'RA': '정관사',
         'RD': '지시대명사', 'RI': '의문·부정대명사', 'RP': '인칭대명사', 'RR': '관계대명사', 'V-': '동사', 'X-': '불변화사'}
G_PER = {'1': '1인칭', '2': '2인칭', '3': '3인칭'}
G_TENSE = {'P': '현재', 'I': '미완료', 'F': '미래', 'A': '부정과거', 'X': '현재완료', 'Y': '과거완료'}
G_VOICE = {'A': '능동태', 'M': '중간태', 'P': '수동태'}
G_MOOD = {'I': '직설법', 'D': '명령법', 'S': '가정법', 'O': '희구법', 'N': '부정사', 'P': '분사'}
G_CASE = {'N': '주격', 'G': '속격', 'D': '여격', 'A': '대격', 'V': '호격'}
G_NUM = {'S': '단수', 'P': '복수'}
G_GEN = {'M': '남성', 'F': '여성', 'N': '중성'}
G_DEG = {'C': '비교급', 'S': '최상급'}
G_MAPS = [G_PER, G_TENSE, G_VOICE, G_MOOD, G_CASE, G_NUM, G_GEN, G_DEG]


def nokey(t):
    return ''.join(c for c in ud.normalize('NFD', t) if ud.category(c) != 'Mn').lower()


GR_EXACT, GR_LOOSE = {}, {}
for sid, e in LEX_GR.items():
    lem = ud.normalize('NFC', e.get('lemma', ''))
    GR_EXACT.setdefault(lem, sid)
    GR_LOOSE.setdefault(nokey(lem), sid)
# MorphGNT 표제어와 스트롱 사전 표기가 다른 경우
GR_FIX = json.loads((HERE / 'greek_lemma_fix.json').read_text(encoding='utf-8')) if (HERE / 'greek_lemma_fix.json').exists() else {}
unmatched = {}


def parse_greek(src, ch):
    verses = {}
    for line in (RAW / src).read_text(encoding='utf-8').splitlines():
        ref, pos, code, punct, _word, _norm, lemma = line.split(' ')
        if int(ref[2:4]) != ch:
            continue
        lemma = ud.normalize('NFC', lemma)
        sid = GR_FIX.get(lemma) or GR_EXACT.get(lemma) or GR_LOOSE.get(nokey(lemma))
        ko = ''
        if sid:
            ko = lex_entry(sid, LEX_GR)
        else:
            unmatched[lemma] = 1
        parse = [m[c] for m, c in zip(G_MAPS, code) if c in m]
        toks = pron.greek(_word)
        verses.setdefault(int(ref[4:]), []).append({
            't': re.sub('[⸀-⹿]', '', punct), 'segs': [{'x': _word, 'pos': G_POS[pos], 'parse': parse, 'sid': sid, 'lemma': lemma, 'ko': ko}],
            'tr': pron.to_latin(toks), 'hg': pron.to_hangul(toks), 'gl': ko.split(',')[0]})
    return verses


def side_text(name, book, ch):
    d = json.loads((RAW / f'{name}-{book}-{ch}.json').read_text(encoding='utf-8'))
    return {v['verse']: v['text'].strip() for v in d['verses']}


PARTS = [
    {'file': 'gen-01-11', 'title': '창세기 1~11장', 'name': '창세기', 'book': 1, 'lang': 'he', 'chs': range(1, 12), 'parse': parse_hebrew, 'src': 'Gen.xml'},
    {'file': 'gen-12-25', 'title': '창세기 12~25장', 'name': '창세기', 'book': 1, 'lang': 'he', 'chs': range(12, 26), 'parse': parse_hebrew, 'src': 'Gen.xml'},
    {'file': 'gen-26-50', 'title': '창세기 26~50장', 'name': '창세기', 'book': 1, 'lang': 'he', 'chs': range(26, 51), 'parse': parse_hebrew, 'src': 'Gen.xml'},
    {'file': 'exo-01-18', 'title': '출애굽기 1~18장', 'name': '출애굽기', 'book': 2, 'lang': 'he', 'chs': range(1, 19), 'parse': parse_hebrew, 'src': 'Exod.xml'},
    {'file': 'exo-19-40', 'title': '출애굽기 19~40장', 'name': '출애굽기', 'book': 2, 'lang': 'he', 'chs': range(19, 41), 'parse': parse_hebrew, 'src': 'Exod.xml'},
    {'file': 'lev-01-27', 'title': '레위기 1~27장', 'name': '레위기', 'book': 3, 'lang': 'he', 'chs': range(1, 28), 'parse': parse_hebrew, 'src': 'Lev.xml'},
    {'file': 'num-01-19', 'title': '민수기 1~19장', 'name': '민수기', 'book': 4, 'lang': 'he', 'chs': range(1, 20), 'parse': parse_hebrew, 'src': 'Num.xml'},
    {'file': 'num-20-36', 'title': '민수기 20~36장', 'name': '민수기', 'book': 4, 'lang': 'he', 'chs': range(20, 37), 'parse': parse_hebrew, 'src': 'Num.xml'},
    {'file': 'deu-01-11', 'title': '신명기 1~11장', 'name': '신명기', 'book': 5, 'lang': 'he', 'chs': range(1, 12), 'parse': parse_hebrew, 'src': 'Deut.xml'},
    {'file': 'deu-12-34', 'title': '신명기 12~34장', 'name': '신명기', 'book': 5, 'lang': 'he', 'chs': range(12, 35), 'parse': parse_hebrew, 'src': 'Deut.xml'},
    {'file': 'jos-01-24', 'title': '여호수아 1~24장', 'name': '여호수아', 'book': 6, 'lang': 'he', 'chs': range(1, 25), 'parse': parse_hebrew, 'src': 'Josh.xml'},
    {'file': 'jdg-01-21', 'title': '사사기 1~21장', 'name': '사사기', 'book': 7, 'lang': 'he', 'chs': range(1, 22), 'parse': parse_hebrew, 'src': 'Judg.xml'},
    {'file': 'rut-01-04', 'title': '룻기 1~4장', 'name': '룻기', 'book': 8, 'lang': 'he', 'chs': range(1, 5), 'parse': parse_hebrew, 'src': 'Ruth.xml'},
    {'file': 'jhn-01', 'title': '요한복음 1장', 'name': '요한복음', 'book': 43, 'lang': 'gr', 'chs': [1], 'parse': parse_greek, 'src': 'Jn.txt'},
]

manifest = []
for part in PARTS:
    used.clear()
    chapters = []
    for ch in part['chs']:
        words = part['parse'](part['src'], ch)
        ko, en = side_text('korean', part['book'], ch), side_text('kjv', part['book'], ch)
        assert set(ko) == set(en) == set(words), (part['name'], ch, len(ko), len(en), len(words))
        chapters.append({'id': f"{part['name']} {ch}장", 'lang': part['lang'],
                         'verses': [{'n': n, 'ko': ko[n], 'en': en[n], 'w': words[n]} for n in sorted(words)]})
    path = OUT / f"{part['file']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'chapters': chapters, 'lex': used}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    manifest.append({'file': part['file'], 'title': part['title'], 'chapters': [c['id'] for c in chapters]})
    print(part['title'], '절', sum(len(c['verses']) for c in chapters), '표제어', len(used), 'KB', path.stat().st_size // 1024)
(OUT.parent / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

print('스트롱 미연결 헬라어:', list(unmatched))
print('뜻풀이 없음:', len(missing))
if missing:
    (HERE / '_missing.txt').write_text('\n'.join(f'{k} {v}' for k, v in sorted(missing.items(), key=lambda x: (x[0][0], int(x[0][1:])))), encoding='utf-8')
