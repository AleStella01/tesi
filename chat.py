import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_name = "swap-uniba/LLaMAntino-2-chat-13b-hf-UltraChat-ITA"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto"
)

prompt = "### Utente:\nCiao, chi sei?\n### Assistente:\n"

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

output = model.generate(
    **inputs,
    max_new_tokens=200,
    do_sample=True,
    temperature=0.7
)

print(tokenizer.decode(output[0], skip_special_tokens=True))

