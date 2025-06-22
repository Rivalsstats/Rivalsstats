#!/usr/bin/env python3
import os
import argparse
import re
from openai import OpenAI

def get_openai_client(api_key: str):
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

PROMPT_TEMPLATE = """
You are a witty social-media manager with a dad-joke sense of humor for a Marvel Rivals stats site.
Given these inputs:
- date: {date}
- Biggest Gain: {pos_hero} {pos_shift}% (Winrate: {pos_winrate}%)
- Biggest Loss: {neg_hero} {neg_shift}% (Winrate: {neg_winrate}%)
- url: https://rivalsstats.com/

Produce one single social-media post (max 250 characters) that:
- uses no emojis
- uses no em-dashes (—); use simple hyphens (-) if needed
- is funny and engaging, includes a dad joke or pun
- invites people to click or reply
- includes at least #MarvelRivals, #Meta, #Tierlist
- stays under 250 characters total

Output only the post text (no explanation).
"""


def generate_post(client, args):
    prompt = PROMPT_TEMPLATE.format(
        date=args.date,
        pos_hero=args.pos_hero,
        pos_shift=args.pos_shift,
        pos_winrate=args.pos_winrate,
        neg_hero=args.neg_hero,
        neg_shift=args.neg_shift,
        neg_winrate=args.neg_winrate,
    ).strip()

    resp = client.chat.completions.create(
        model="deepseek/deepseek-r1:free",
        messages=[{"role":"user","content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    # strip any extraneous quotes or markdown
    return re.sub(r"^['\"]|['\"]$", "", text)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-key",     required=True)
    p.add_argument("--date",        required=True)
    p.add_argument("--pos-hero",    required=True)
    p.add_argument("--pos-shift",   required=True)
    p.add_argument("--pos-winrate", required=True)
    p.add_argument("--neg-hero",    required=True)
    p.add_argument("--neg-shift",   required=True)
    p.add_argument("--neg-winrate", required=True)
    args = p.parse_args()

    client = get_openai_client(args.api_key)
    post = generate_post(client, args)
    print(post)

if __name__ == "__main__":
    main()
