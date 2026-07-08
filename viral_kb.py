"""
Viral content knowledge base.

A distilled, reusable playbook of short-form content patterns (hook formulas,
video structure, phrasing, funnel, formats, titles) that the agents use to
generate scripts along proven lines. Brand-neutral — swap the examples for
your own niche.
"""

# ═══════════════════════════════════════════════
# A. HOOK FORMULAS (copy and adapt)
# ═══════════════════════════════════════════════

HOOK_FORMULAS = """
TYPE 1 — "Classic masterclass" (highest-reach format):
Formula: Greeting + Promise + Social proof + Contents + Bonus

Pattern:
"Hey. In this video, [the full breakdown / we'll cover] how to [RESULT]. [Without X, without Y, without Z — remove the barriers]."

TYPE 2 — "Origin story + social proof" (slots in right after the promise):
A short, credible personal proof point right after the promise dramatically
increases retention. Define your own (a result, a timeline, an unusual angle).

TYPE 3 — "Provocation / experiment":
- "If everything I owned were taken away and I had $1,000 left — here's what I'd do"
- "What to do when everything is falling apart"
"""

# ═══════════════════════════════════════════════
# B. VIDEO STRUCTURE (second by second)
# ═══════════════════════════════════════════════

VIDEO_STRUCTURE = """
[0:00-0:03] HOOK
- Promise the result + remove barriers ("no code, no experience, from scratch")
- Creator's social proof / signature angle
- List the contents ("we'll cover N steps: [list]")
- Promise a bonus ("checklist / file at the end")

[0:03-0:07] PROBLEM
- "95% still do this by hand and lose money"
- Concrete pain points with numbers
- Amplify: "while you do this manually, competitors already automated it"

[0:07-0:25] SOLUTION (step by step)
- Step 1 -> explanation + demo + mini-case
- Between steps — short client cases (name + BEFORE + AFTER + numbers)
- Transition phrases: "moving on", "step N"
- "For example" — used to reset attention

[0:25-0:30] CTA
- NEVER hard-sell
- "Checklist of 50 processes — link in bio"
- Soft: "free teardown coming soon, follow so you don't miss it"
"""

# ═══════════════════════════════════════════════
# C. PHRASE TEMPLATES
# ═══════════════════════════════════════════════

PHRASES = """
SOCIAL PROOF (adapt to your brand):
- "I've automated dozens of businesses over the past year"
- "My clients save from X to Y a month"
- "A year ago I didn't know what [tool] was. Now I automate businesses with it"

PROBLEM STATISTICS:
- "95% of entrepreneurs still [do it manually]"
- "90% of businesses lose clients because of [slow replies]"
- "99% of people don't even know this can be automated"

TRANSITIONS:
- "moving on"
- "next step"
- "for example"
- "let me show you"
- "okay"

CTA (soft):
- "Checklist of 50 processes to automate — grab it in the bio"
- "The channel has a file with ready-made templates — link in bio"
- "Follow — a free teardown is coming soon"

CLIENT-CASE PATTERN:
[Name/Niche] + [BEFORE — the pain, cost in numbers] + [what was done] + [AFTER — concrete savings]
Example: "A shop owner spent 4 hours a day answering DMs by hand. Built them a bot — now it's 0 minutes. 120 hours a month saved."
"""

# ═══════════════════════════════════════════════
# D. FUNNEL
# ═══════════════════════════════════════════════

FUNNEL = """
Reels/TikTok (free content: cases, demos, tutorials)
    | CTA: "Checklist — link in bio"
Telegram / newsletter channel (subscribe for the lead magnet)
    | Content: cases, mini-tutorials, tips
Free teardown / mini-course
    | Sales
Paid service / product
"""

# ═══════════════════════════════════════════════
# E. 7 CONTENT FORMATS
# ═══════════════════════════════════════════════

FORMATS = """
1. CASE — "I automated [process]" (2/week)
   Structure: hook-problem -> BEFORE -> what I did (show screen) -> AFTER -> CTA

2. PAIN — "N things [audience] still does by hand" (2/week)
   Structure: provocative hook -> pain #1 + fix -> pain #2 + fix -> pain #3 + fix -> CTA

3. DEMO — screen recording of a bot/workflow (1/week)
   Structure: "look what this bot does" -> screen recording -> CTA

4. PRICING — "How much does a bot cost?" (1/week)
   Structure: question-hook -> 3 price tiers -> comparison with alternative -> CTA

5. FEAR — "The mistake that costs [amount]" (1/week)
   Structure: fear-hook -> the mistake + numbers -> fix -> CTA

6. TRANSFORMATION — "Before/After"
   Structure: show the BEFORE (manual, slow) -> AFTER (automated, instant)

7. TUTORIAL — "How to [result] in [timeframe]"
   Structure: step by step, each step a mini-demo
"""

# ═══════════════════════════════════════════════
# F. TITLES THAT WORK
# ═══════════════════════════════════════════════

TITLE_FORMULAS = """
Top formulas:

1. "The full playbook for [result]"
   -> "The full playbook for automating a business from scratch"

2. "N steps/tips/rules" — numbers = clickability
   -> "7 processes AI does better than a human"

3. Case with numbers
   -> "How I saved a client $5K/month with one bot"

4. "(from scratch)" — reliably increases reach
   -> "How to start earning with automation (from scratch)"

5. "Without X, without Y" — barrier removal
   -> "no code", "no experience", "no team"

WHAT DOESN'T WORK:
- News-driven topics
- Narrow, niche topics with no broad hook
- Ads with no value
"""

# ═══════════════════════════════════════════════
# G. CASE TEMPLATE (fill with your own real cases)
# ═══════════════════════════════════════════════

CASE_TEMPLATE = """
Keep a running list of your real client cases and insert them between steps in
scripts. Each case follows the pattern:

[Client / niche] — "[what the situation was BEFORE — the pain, hours or money lost].
[What was built / automated]. [Concrete result AFTER — numbers]."

Strong cases carry a script far more than any hook. Prefer specifics and numbers.
"""

# Assembled KB for agent prompts
VIRAL_KB = f"""
VIRAL SHORT-FORM CONTENT PLAYBOOK:

{HOOK_FORMULAS}

{VIDEO_STRUCTURE}

{PHRASES}

{FUNNEL}

{FORMATS}

{TITLE_FORMULAS}

{CASE_TEMPLATE}
"""
