#!/usr/bin/env python3
"""Compare tokenizer performance and token IDs between HF and model-local tokenizers.

Usage examples:
  python3 performance_evaluation/tokenizer_compare.py --prompt "Hello world" --tokenizer hf
  python3 performance_evaluation/tokenizer_compare.py --prompts-file prompts.txt --model-path ./models/qwen3 --tokenizer model

Outputs a CSV into `performance_evaluation/results/` with timings and token lists.
"""
import argparse
import time
import csv
import os
from datetime import datetime
from transformers import AutoTokenizer


def load_tokenizer(mode, model_path=None):
    if mode == "hf":
        # Default small tokenizer to ensure availability if no model path given
        return AutoTokenizer.from_pretrained("gpt2")
    elif mode == "model":
        if not model_path:
            raise ValueError("--model-path is required when --tokenizer model is selected")
        # Try to load tokenizer from model path (may require trust_remote_code)
        try:
            return AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        except Exception:
            # Fallback to HF gpt2 if model-local tokenizer fails
            return AutoTokenizer.from_pretrained("gpt2")
    else:
        raise ValueError("Unsupported tokenizer mode: %s" % mode)


def ensure_out_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def run_once(tokenizer, text):
    t0 = time.perf_counter()
    try:
        token_ids = tokenizer.encode(text)
    except Exception:
        # Some tokenizers prefer call form
        token_ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    t_encode = time.perf_counter() - t0

    t0 = time.perf_counter()
    try:
        decoded = tokenizer.decode(token_ids, skip_special_tokens=True)
    except Exception:
        decoded = tokenizer.convert_tokens_to_string(tokenizer.convert_ids_to_tokens(token_ids))
    t_decode = time.perf_counter() - t0

    return token_ids, t_encode, t_decode, decoded


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tokenizer", choices=["hf", "model"], default="hf",
                   help="Which tokenizer to use: 'hf' (HF hub gpt2) or 'model' (load from --model-path)")
    p.add_argument("--model-path", help="Path or repo id to load model-local tokenizer")
    p.add_argument("--prompt", help="Single prompt to test")
    p.add_argument("--prompts-file", help="File with one prompt per line")
    p.add_argument("--repeat", type=int, default=1, help="Repeat tokenization N times and record the first run time")
    p.add_argument("--out-dir", default="performance_evaluation/results", help="Output directory for CSV results")
    args = p.parse_args()

    if not args.prompt and not args.prompts_file:
        p.error("Either --prompt or --prompts-file must be provided")

    tokenizer = load_tokenizer(args.tokenizer, args.model_path)

    prompts = []
    if args.prompt:
        prompts.append(args.prompt)
    if args.prompts_file:
        with open(args.prompts_file, "r") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    prompts.append(ln)

    out_dir = ensure_out_dir(args.out_dir)
    fname = os.path.join(out_dir, f"tokenizer_compare_{args.tokenizer}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv")

    with open(fname, "w", newline='', encoding='utf-8') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=["prompt", "tokenizer", "encode_time_s", "num_tokens", "tokens", "decode_time_s", "decoded_preview"])
        writer.writeheader()

        for prompt in prompts:
            # Optionally repeat to warm caches; only record the last measurement
            token_ids = None
            t_enc = None
            t_dec = None
            decoded = None
            for i in range(max(1, args.repeat)):
                token_ids, t_enc, t_dec, decoded = run_once(tokenizer, prompt)

            writer.writerow({
                "prompt": prompt,
                "tokenizer": args.tokenizer,
                "encode_time_s": f"{t_enc:.6f}",
                "num_tokens": len(token_ids),
                "tokens": " ".join(str(x) for x in token_ids[:200]),
                "decode_time_s": f"{t_dec:.6f}",
                "decoded_preview": decoded[:200]
            })

    print(f"Wrote results to {fname}")


if __name__ == '__main__':
    main()
