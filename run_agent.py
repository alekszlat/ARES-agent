from myagent import Agent, LlamaCPP, LlamaPrompt
from agentio import PiperConfig, PiperTTS
import asyncio

async def run_agent():
    model = LlamaCPP.from_path('./models/llama-3.2-3b-instruct-q4_k_m.gguf')
    prompt = LlamaPrompt()
    agent = Agent(name="Helper", model=model, prompt=prompt)
    tts = PiperTTS(PiperConfig(model_path="./models/en_GB-northern_english_male-medium.onnx"))

    agent.register_mcp(path="./run_server.py")

    async with agent:
        while (prompt := input('(prompt) ')) != 'bye':
            response = await agent.chat(prompt)

            for r in response:
                if r.type == 'text':
                    print(f"(assistant) {r.data}")
                    tts.speak(r.data)
                elif r.type == 'tool-calling':
                    print(f"(assistant) tool calling {r.data}")
                elif r.type == 'tool-result':
                    print(f"(assistant) tool result {r.data}")

if __name__ == '__main__':
    asyncio.run(run_agent())