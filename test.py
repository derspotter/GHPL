from openai import OpenAI

client = OpenAI(
  api_key="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"
)

response = client.responses.create(
  model="gpt-4o-mini",
  input="write a haiku about ai",
  store=True,
)

print(response.output_text);
