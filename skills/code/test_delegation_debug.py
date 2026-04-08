import re

text = "I'll dispatch a subagent to handle this"

# Test progressive pattern building - using raw strings properly
patterns_to_test = [
    (r"\bI'll\s+dispatch", "Just verb"),
    (r"\bI'll\s+dispatch\s+", "Verb + space"),
    (r"\bI'll\s+dispatch\s+(?:the\s+)?", "Verb + space + optional 'the'"),
    (r"\bI'll\s+dispatch\s+(?:the\s+)?subagent\b", "Full match with 'subagent'"),
    (r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the\s+)?(?:Task\s+tool|agent|subagent)\b", "Full pattern"),
]

print("Testing pattern matching step by step:")
for pattern, desc in patterns_to_test:
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        print(f"{desc:40s} -> '{match.group()}' (span {match.span()})")
    else:
        print(f"{desc:40s} -> NO MATCH")

print("\n--- Testing with shorter text ---")
short_text = "I'll dispatch a subagent"
for pattern, desc in patterns_to_test:
    match = re.search(pattern, short_text, re.IGNORECASE)
    if match:
        print(f"{desc:40s} -> '{match.group()}' (span {match.span()})")
    else:
        print(f"{desc:40s} -> NO MATCH")

print("\n--- Character analysis ---")
print(f"Text: {repr(text)}")
print(f"Length: {len(text)}")
print("Characters around 'subagent':")
idx = text.find("subagent")
if idx >= 0:
    print(f"  Before: {repr(text[max(0,idx-5):idx])}")
    print(f"  After: {repr(text[idx+9:idx+15])}")
