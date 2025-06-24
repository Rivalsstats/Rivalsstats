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
{data}

Produce one single social-media post (max 210 characters) that:
- uses no emojis
- uses no em-dashes (—); use simple hyphens (-) if needed
- is funny and engaging, includes a dad joke or pun
- invites people to click or reply
- includes at least #MarvelRivals, #Meta, #Tierlist
- stays under 210 characters total

Output only the post text (no explanation, Comments or Quotation marks).
"""


def generate_post(client, data, url):
    prompt = PROMPT_TEMPLATE.format(data=data).strip()

    resp = client.chat.completions.create(
        model="deepseek/deepseek-r1:free",
        messages=[{"role":"user","content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    # strip any extraneous quotes or markdown
    cleanText = re.sub(r"^['\"]|['\"]$", "", text)
    if len(cleanText)+len(url) <250:
        return f"{cleanText} {url}"
    elif len(cleanText <=250):
         return cleanText
    else :
        raise ValueError("Generated post is too long, please adjust the input data.")
    

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-key",     required=True)
    p.add_argument("--data",        required=True)
    p.add_argument("--url",        required=True)
    args = p.parse_args()

    client = get_openai_client(args.api_key)
    post = generate_post(client, args.data, args.url)
    print(post)

if __name__ == "__main__":
    main()
