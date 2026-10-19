"""Count the tokens in data/shop_handbook.md with tiktoken (o200k_base, the GPT-4o/GPT-5-family tokenizer)."""
from pathlib import Path

import tiktoken

HERE = Path(__file__).parent
text = (HERE / "data" / "shop_handbook.md").read_text(encoding="utf-8")

for name in ["o200k_base", "cl100k_base"]:
    print(f"{name}: {len(tiktoken.get_encoding(name).encode(text)):,} tokens")
print(f"characters: {len(text):,}  (chars / 4 rule of thumb: {len(text) / 4:,.0f})")
