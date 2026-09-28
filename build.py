"""Build site/data.js from the Sam iMessage thread.

Only aggregated stats plus the hand-picked quotes/hashtags below end up in the
published site. The raw export (data/raw.json) stays local (gitignored).

    python3 build.py          # re-export from Messages + rebuild data.js
"""
import collections
import datetime
import json
import re
import sqlite3
import statistics
from pathlib import Path

CHAT_ID = 480
ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw.json"
OUT = ROOT / "data.js"

# --- Hand-curated bits (edit freely; this is what's public) -----------------
QUOTES = [
    "ur such a binx bams",
    "beech!!!! have a nice call with cislak!!!",
    "#soulmating with my binx!!!!!",
    "the name ella is objectively so binx!",
    "whats on ur agenda today cheechuuu",
    "our kids r so binxy",
    "u cheech muffin",
    "ur such a freaking trinxie i love u so much 😘",
    "omg cuddles ur so binx 😂😂😂😂😂😂😂😂😂😂😂",
    "i have a huge update from this weekend can't believe i forgot to tell u… i used my ironing board",
    "i love you, you are the man of my dreams, keep going 💪",
    "beech ur dead to me",
    "i'm coming for you, your cheechoo, your beechoo, and ur meemoo 😘",
    "remember when u said u want to work on ur physical comedy and im like jams u have more physical comedy than anyone i know 😂",
    "what r u up to tonight beechito poopsie? any roboting? 😘",
    "ur such a sweet pea munchkin 😘",
]
HASHTAGS = [
    "#soulmates", "#winning", "#cricket", "#hadassah", "#hadassah is my religion",
    "#hadassah is also iconic", "#friendship", "#besties", "#cuddle bunnies",
    "#cuddling with my cuddles", "#i love my cheech", "#bims is so smart",
    "#fancy building alert", "#favorite activity alert", "#flex urself",
    "#social jam jams", "#dates with my best friend", "#sleepover party",
    "#soulmating with my binx", "#i love ur sayings", "#ben is a binxy",
    "#i know what my binxy likes", "#missing just salad", "#glass house",
    "#normal start times", "#texting uncle tim", "#gossiping with my jinx",
    "#favors with my minxie", "#im not scared of ur darkness", "#hi ben",
    "#hanging w my binx", "#ur perfect", "#montreal",
]
PET_NAMES = [
    "bams", "binx", "monk", "monkey", "cuddles", "munchk", "jim", "doodles",
    "cheech", "beech", "poop", "jam", "jinx", "jimothy", "bims", "love muffin",
    "meemoo", "sweetheart", "beeboops", "minxie", "peepoo", "treetroo",
    "zeezoo", "mrim", "cheechoo", "heehoos", "jeejoopsies", "bichito",
]
STOP = set("""
i me my myself we our ours you your yours ur u he him his she her hers it its they them their
a an the and but or if so as of at by for with about to from in on up down out off over under
is am are was were be been being have has had do does did doing will would can could should shall
just not no yes this that these those there here then than too very also what which who whom when
where why how all any both each few more most other some such only own same s t m ll re ve d don
im i'm its it's that's im cant can't don't didn't dont wont won't isn't r w get got go going gonna
like know think one really want need make now today tonight tomorrow day night time oh ok okay
lol haha yeah yea ya im i'll ill i've ive let's lets see say said could'nt well much many still
https www com
""".split())
# ---------------------------------------------------------------------------


def export():
    """Pull the thread out of ~/Library/Messages/chat.db into data/raw.json."""
    db = sqlite3.connect(Path.home() / "Library/Messages/chat.db")
    rows = db.execute(
        """select m.date, m.is_from_me, m.text, m.attributedBody,
                  m.associated_message_type, m.cache_has_attachments
           from message m join chat_message_join cmj on cmj.message_id = m.ROWID
           where cmj.chat_id = ? order by m.date""",
        (CHAT_ID,),
    ).fetchall()

    def decode(blob):
        # Newer macOS stores text only inside an NSAttributedString blob.
        if not blob:
            return None
        try:
            b = blob.split(b"NSString")[1][5:]
            if b[0] == 0x81:
                n = int.from_bytes(b[1:3], "little")
                return b[3:3 + n].decode("utf-8", "ignore")
            return b[1:1 + b[0]].decode("utf-8", "ignore")
        except Exception:
            return None

    out = [
        {"ts": d / 1e9 + 978307200, "me": bool(me), "text": t or decode(ab),
         "reaction": amt, "att": att}
        for d, me, t, ab, amt, att in rows
    ]
    RAW.parent.mkdir(exist_ok=True)
    RAW.write_text(json.dumps(out))
    return out


def norm(s):
    return (s or "").replace("’", "'").replace("￼", "").lower()


def words(s):
    return re.findall(r"[a-z][a-z']*", norm(s))


def build(raw):
    msgs = [m for m in raw if m["reaction"] == 0]
    who = lambda m: "ben" if m["me"] else "sam"
    dt = lambda m: datetime.datetime.fromtimestamp(m["ts"])
    by = {p: [m for m in msgs if who(m) == p] for p in ("sam", "ben")}
    text = {p: [norm(m["text"]) for m in by[p] if m["text"]] for p in by}

    def count_re(p, pattern):
        return sum(len(re.findall(pattern, s)) for s in text[p])

    # Word clouds
    clouds = {}
    for p in by:
        c = collections.Counter(w.strip("'") for s in text[p] for w in words(s))
        clouds[p] = [[w, n] for w, n in c.most_common(400)
                     if w not in STOP and len(w) > 2][:70]

    # Pet names
    pets = []
    for n in PET_NAMES:
        pat = r"\b" + n + r"\w*"
        s, b = count_re("sam", pat), count_re("ben", pat)
        pets.append({"name": n, "sam": s, "ben": b})
    # "monk" also matches "monkey": subtract to keep them distinct
    mk = next(p for p in pets if p["name"] == "monkey")
    mo = next(p for p in pets if p["name"] == "monk")
    mo["sam"] -= mk["sam"]; mo["ben"] -= mk["ben"]
    jm = next(p for p in pets if p["name"] == "jimothy")
    ji = next(p for p in pets if p["name"] == "jim")
    ji["sam"] -= jm["sam"]; ji["ben"] -= jm["ben"]
    pets.sort(key=lambda p: -(p["sam"] + p["ben"]))

    # Rhythm
    hours = {p: [0] * 24 for p in by}
    for m in msgs:
        hours[who(m)][dt(m).hour] += 1
    first_day = dt(msgs[0]).date()
    ndays = (dt(msgs[-1]).date() - first_day).days + 1
    daily = {p: [0] * ndays for p in by}
    for m in msgs:
        daily[who(m)][(dt(m).date() - first_day).days] += 1
    weekday = {p: [0] * 7 for p in by}
    for m in msgs:
        weekday[who(m)][dt(m).weekday()] += 1

    # Who texts first each morning (day boundary at 5am)
    first = collections.Counter()
    seen = set()
    for m in msgs:
        k = (dt(m) - datetime.timedelta(hours=5)).date()
        if k not in seen:
            seen.add(k)
            first[who(m)] += 1

    # Reply speed
    gaps = {"sam": [], "ben": []}
    for a, b in zip(msgs, msgs[1:]):
        if a["me"] != b["me"]:
            g = (b["ts"] - a["ts"]) / 60
            if g < 12 * 60:
                gaps[who(b)].append(g)

    tb = {2000: "love", 2003: "laugh", 2004: "emphasize", 2001: "like"}
    taps = {p: collections.Counter() for p in by}
    for m in raw:
        if m["reaction"] in tb:
            taps[who(m)][tb[m["reaction"]]] += 1

    emoji = {}
    for p in by:
        c = collections.Counter(ch for s in text[p] for ch in s
                                if ord(ch) > 0x2500 and ch not in "️￼")
        emoji[p] = c.most_common(8)

    per = {}
    for p in by:
        per[p] = {
            "messages": len(by[p]),
            "avgLen": round(statistics.mean(len(m["text"] or "") for m in by[p])),
            "photos": sum(1 for m in by[p] if m["att"]),
            "loveYou": count_re(p, r"love (you|u)\b"),
            "cryLaugh": sum(s.count("😂") for s in text[p]),
            "kiss": sum(s.count("😘") for s in text[p]),
            "omg": count_re(p, r"\bomg\b"),
            "bams": count_re(p, r"\bbam+s\b"),
            "u": count_re(p, r"\bu\b"),
            "you": count_re(p, r"\byou\b"),
            "urSuchA": count_re(p, r"\bur such an? "),
            "cantWait": count_re(p, r"can'?t wait"),
            "perf": count_re(p, r"\bperf\b"),
            "hashtags": count_re(p, r"#\w"),
            "startsBams": sum(1 for s in text[p] if s.startswith("bams")),
            "firstOfDay": first[p],
            "replyMin": round(statistics.median(gaps[p]), 1),
            "taps": dict(taps[p]),
        }

    # "ur such a ___" completions from Sam
    such = collections.Counter(
        m.group(1) for s in text["sam"]
        for m in re.finditer(r"ur such an? (?:freaking |sweet |little |super )?([a-z]+)", s))

    return {
        "range": [first_day.isoformat(), dt(msgs[-1]).date().isoformat()],
        "days": ndays,
        "total": len(msgs),
        "reactions": sum(1 for m in raw if m["reaction"]),
        "per": per,
        "clouds": clouds,
        "pets": [p for p in pets if p["sam"] + p["ben"] > 0],
        "hours": hours,
        "daily": daily,
        "weekday": weekday,
        "emoji": emoji,
        "urSuchA": such.most_common(14),
        "quotes": QUOTES,
        "hashtags": HASHTAGS,
    }


if __name__ == "__main__":
    import sys
    raw = json.loads(RAW.read_text()) if "--cached" in sys.argv and RAW.exists() else export()
    data = build(raw)
    OUT.write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print(f"wrote {OUT} — {data['total']} messages over {data['days']} days")
