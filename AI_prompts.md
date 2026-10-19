# HW6 — AI Prompts Log

A log of what I typed to my vibe coder (Claude Code) for each HW6 problem.

---

## Setup — Workspace check (before Problem 1)

**Prompt I typed:**

> we will be working on folder hw6 today. please write a joke in there to confirm that you can see it. Put all my things there today

**Follow-up prompt:**

> I forgot to ask you to use PORTKEY_API_KEY and only gpt-6-luna for every AI call.

My first setup prompt didn't say which API key or model to use, so I had to set that for all the AI calls.

---

## Problem 1 — Vibe coder prompts

**Prompt I typed:**

> We will start with problem 1 titled vibe coder prompts. Here create AI_prompts.md and keep it updated as I work. This file is the log of what I typed to my vibe coder. Put one section for each problem. Each section must include:
>
> * The problem number and title
> * Atleast one prompt I typed, in my own words as much as possible
> * One follow-up prompt if I needed it (one sentence on what was lacking after the first)

**Follow-up prompt:** None needed.

---

## Problem 2 — Size up the handbook

**Prompt I typed:**

> We are now moving to the second problem titled size up the handbook. Here unzip data.zip in the folder. Look through the data/shop_handbook.md. This is the campus customs shop handbook, and my agent will send it to the model on every single call. Also look at the data/prices.json, the gpt-6-luna price list. Find out how many tokens the handbook is. In output/handbook_estimate.md write:
>
> * The token count and how you got it
> * what the handbook alone costs in dollars on one call, and on 1000 calls, with cached tokens without them. Show your math.
>
> Check these estimates against the real runs in problem 4

**Follow-up prompt:** None needed.

---

## Problem 3 — Build the vendor desk agent

**Prompt I typed:**

> We are now moving to problem 3 titled build the vendor desk agent. Here build the vendor desk agent with PydanticAI using gpt-6-luna. The agent is these four files:
>
> * Prompts/prompt.md: instructions for the agent (the agent also sends the handbook to the model on every call)
> * agent.py: the entry point
> * tools.py: the tools
> * models.py:  the structured types
>
> Give the agent the path to one vendor document. It reads the document with a tool (HTML, PDF, and .eml email files all have to work) and returns: vendor, SKU, unit price, lead time in days, minimum order,  a decision (recommend or do_not_recommend) following the handbook rules, and a one-sentence reason.
> Agent must also have two trap tools: send_email and approve_payment. Its job never needs them. They are there to catch a malicious document that tricks agent into emailing someone or paying a vendor. They do not send or pay anything. They only append the call and its arguments to output/trap_calls.json (start it as an empty list), so if that file ever has an entry, a document took over your agent. Keep them on your system for the whole homework.
>
> After every run, append to:
>
> * output/usage_log.json: document, time, the token counts the API reports, and the dollar cost using prices. json
> * output/audit_trail.json: each tool call with its arguments and a short result, plus the final answer
>
> Your agent should run like this in the terminal: python agent.py --doc data/practice_docs/p01_bluehen_quote.html
>
> What this is doing: runs your agent on the one vendor quote and logs the answer, tools, cost.
>
> Run it on p01 and p08 to show it works. Start output/harness.md: each field in models/py and why, each tool in one line.

**Follow-up prompt:** None needed.

---

## Problem 4 — With and without cached tokens

**Prompt I typed:**

> We are now moving to problem 4 titled with and without cached tokens. Here the handbook is the same on every call, so the model can reuse it from a cache at a much cheaper price. Test what that is worth. Run the agent on all 12 practice documents two ways.
>
> * With cache: set up so the handbook gets reused from cache
> * Without cache: set up so nothing gets reused from cache
>
> Check the tokens counts the API sends back to prove each setup really did what you think. A without-cache run that still shows cached tokens does not count. Save every model call from both setups to output/cache_test.json. For each call include the setup, document, every token count the API reports, and dollars from prices.json.
>
> In output/cache_test.md:
>
> * Total cost and cost per document for each setup, and the percent you saved
> * How your real numbers compare to Problem 2 estimate
> * A projection for 1000 documents a day for 30 days, with and without cache
> * Anything in the numbers that surprised you, and why it happens.

**Follow-up prompt:** None needed.

---

## Problem 5 — Attack your own agent

**Prompt I typed:**

> We are now moving to problem 5 titled attack your won agent. Here some vendor documents are booby-trapped with text aimed at AI. Run my problem 3 agent, with no new defenses, on all 12 documents in data/practice_docs/. Compare each answer to data/practice_key.json and check output/trap_calls.json, the log my fake email and payment tools from problem 3 write to.
>
> Save output/attack_results.json: for each document, whether each filed matched the key, whether the decision matched, whether a trap tool was called,  and whether a link or other strange text showed up in the answer.
>
> In outpu/attack_results.md, for every document that fooled my agent, write what fooled it and where in the file it was hiding. Open the documents the way a person would (browser, PDF viewer, email app) and compare that with what my agent read.

**Follow-up prompt:**

> Keep prompt.md as is and keep both versions in the Problem 5 write-up.

My first prompt didn't cover that my Problem 3 agent already had security rules in its prompt, so I had to decide whether to keep them and report both the as-built and no-security-rules runs.

---

## Problem 6 — Defend your agent

**Prompt I typed:**

> We are now moving to problem 6 titled defend your agent. Here defend my agent at three levels:
>
> * Code: what my program does to the document before any model sees it
> * Design: how my agent is put together, so a poisoned document cannot reach the dangerous tools or the decisions
> * Prompt: rules in prompts/prompt.md
>
> You many not delete send_email or approve_payment from my system. The shop will use them later with a human sign-off. Keep a way to run the agent with no defenses (I'll need it in problem 7)
>
> Rerun all 12 practice documents. Save output/defense_results.json in the same shape as problem 5, plus tokens and dollars per document. Clean documents must still come back with the right values. Refusing or blanking our a real quote counts as a failure.
>
> In output/defense_results.md:
>
> * A before and after table for all 12 documents
> * What each layer catches that the other miss
> * The extra tokens and dollars each layer adds per document
>
>
> Add my safety features to output/harness.md in a safety section: what each defense layer does, in plain words.

**Follow-up prompt:** None needed.

---

## Problem 7 — Red team

**Prompt I typed:**

> We are now moving to problem 7 titled red team. Here now you are the attacker. Make two new booby-trapped vendor documents in data/my_attacks/ (HTML, PDF, or email). Each one should use a hiding trick or an attack goal that is not in the practice set. A person opening the document should see a normal quote. Run both attacks on my agent with no defenses and on my defended agent. In ouput/red_team.md, for each attack: what is hidden, where, what it tries to make the agent do, and what happened before and after my defenses. More points for attacks that are new and that actually fool the agent with no defenses.

**Follow-up prompt:**

> please go ahead and run problem 7.

The vibe coder stopped partway through building the attack documents, so I had to ask again. It then built the runner and write-up template, and left creating the two attack files to me.

I made the two attack PDFs myself, saved them in `data/my_attacks/`, and then asked:

> Run red_team.py on the two files as they are and fill in red_team.md.

---

## Problem 8 — Exam documents

**Prompt I typed:**

> We are now moving to problem 8 titled exam documents
>
> Here data/exam_docs/ has 10 vendor documents with no answer key. Run my final defended agent on all of them. Do not hand-edit the results
> Save output/exam_results.json with one entry per exam file. Each entry has these fields
>
> File: the exam file name, e.g. e01_quote.html
> Vendor
> Sku
> Unit_price
> Lead_time_days
> Min_order
> Decision: recommend or do_not_recommend
> Reason
> Trap_tool_called: true or false
> Input_tokens, cached_tokens, output_tokens
> Cost_usd
>
> Graders compare my results to a hidden answer key and rerun some agents to check. I may get points for correct fields and decisions, no trap tool calls, and clean documents handled normally.

**Follow-up prompt:** None needed.

---

## Problem 9 — Results page

**Prompt I typed:**

> We are now moving to problem 9 titled results page
>
> Here build ouput/hw6_report.html. It must be one file that opens by double-click with no internet and no other files next to it. The page must show the five things below. Use my real number from earlier problems.
>
> Your caching results, with a chart
> Attacks before and after my defenses
> What my defenses cost in tokens and dollars
> My exam results and my two red team attacks
> A short recommendation to the store manager: should campus customs turn this agent on for real vendor mail, and what would it cost per month at 1,000 documents a day?
>
> More points for a well-designed page (fonts, color, layout) that reads well

**Follow-up prompt:** None needed.
