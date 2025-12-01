from myagent import LlamaCPP

# Initialize the model from a specified path
def request(prompt: str, n_predict: int = 64) -> str:
    model_path = "models/llama-3.2-3b-instruct-q4_k_m.gguf"
    model = LlamaCPP.from_path(model_path=model_path)
    response = model.generate(prompt, max_tokens=n_predict)
    return response

def main():
    prompt = "Explain the theory of relativity in simple terms."
    response = request(prompt)
    print("Response:", response)


if __name__ == "__main__":
    main()
